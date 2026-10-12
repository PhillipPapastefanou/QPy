"""Observation loading, model-output extraction, and assembly of the stacked
observation vector / obs-error variances / ensemble perturbation matrix that
qpy_calibrate.fourdenvar needs.

This generalises the ad hoc RMSE pattern already used in
science/phillip/DE-Hai/bench/post_process_complete_single.py (merge model
output on the obs CSV's date index, compute RMSE) to: (a) an arbitrary list
of metrics/variables/observation files, and (b) many ensemble members at
once, aligned onto a common set of observation timestamps so they can be
stacked into one linear-algebra problem.
"""
import glob
import os
import re

import numpy as np
import pandas as pd

from src.postprocessing.py.qnc_output_parser import QNC_output_parser
from src.postprocessing.py.qnc_ncdf_reader import QNC_ncdf_reader

_OBS_CACHE = {}
_FIXED_TIME_UNITS_DIRS = set()

_TIME_UNITS_RE = re.compile(
    r"^(seconds since)\s+(\d{4})\s*-\s*(\d{2})\s*-\s*(\d{2})\s+(\d{2})(?::(\d{2}))?\s*$"
)


def _fix_fluxnetdata_time_units(run_dir):
    """QUINCY's dedicated fluxnet-timestep writer builds its time-units
    string as int2string(year)//'-01-01 00:00', and Fortran's int2string
    left-pads with spaces -- so files like *_fluxnetdata_timestep.nc end up
    with a 'units' attribute such as 'seconds since 1905       -01-01 00'
    (extra whitespace around the year, and missing the ':00' minutes). This
    can't be parsed by QPy's date parser, even though the underlying time
    *values* are written correctly. Fix it in place, once per run
    directory, before reading."""
    if run_dir in _FIXED_TIME_UNITS_DIRS:
        return
    _FIXED_TIME_UNITS_DIRS.add(run_dir)

    import netCDF4

    for path in glob.glob(os.path.join(run_dir, "*fluxnetdata*.nc")):
        try:
            with netCDF4.Dataset(path, "r+") as ds:
                if "time" not in ds.variables:
                    continue
                units = getattr(ds.variables["time"], "units", "")
                m = _TIME_UNITS_RE.match(units)
                if m:
                    prefix, year, month, day, hour, minute = m.groups()
                    fixed = f"{prefix} {year}-{month}-{day} {hour}:{minute or '00'}"
                    if fixed != units:
                        ds.variables["time"].units = fixed
        except Exception as exc:
            print(f"[LAVENDAR] warning: could not normalize time units in {path}: {exc}")


def typical_sigma(metric):
    """A single representative observation-error std for a metric, used
    after calibration to judge whether the achieved RMSE is actually a good
    fit (as opposed to just "the ensemble stopped moving"). For an absolute
    `sigma` (or a range constraint, which derives one automatically in
    MetricSpec) this is just metric.sigma; for `relative_sigma` it's
    approximated from the mean magnitude of the observations themselves."""
    if metric.sigma is not None:
        return float(metric.sigma)
    df_obs = load_observations(metric)
    scale = float(np.mean(np.abs(df_obs[metric.obs_column])))
    return float(metric.relative_sigma) * max(scale, 1e-6)


def rmse(model_vals, obs_vals):
    if len(model_vals) == 0:
        return float("nan")
    return float(np.sqrt(np.mean((np.asarray(model_vals) - np.asarray(obs_vals)) ** 2)))


def load_observations(metric):
    """Read+cache one metric's observation CSV as a single-column DataFrame
    indexed by datetime, with NaNs dropped (and, if
    metric.clip_negative_obs_to_zero, negative values clipped to 0 -- the
    convention the existing DE-Hai analysis scripts use for sap-flow J0.5,
    a physically non-negative quantity whose sensor readings dip slightly
    below 0 from noise)."""
    key = (metric.obs_file, metric.obs_column, metric.obs_index_col, metric.clip_negative_obs_to_zero)
    if key not in _OBS_CACHE:
        df = pd.read_csv(metric.obs_file, index_col=metric.obs_index_col, parse_dates=True)
        if metric.obs_column not in df.columns:
            raise ValueError(f"Column '{metric.obs_column}' not found in {metric.obs_file}")
        df = df[[metric.obs_column]].dropna()
        if metric.clip_negative_obs_to_zero:
            df[metric.obs_column] = df[metric.obs_column].clip(lower=0.0)
        _OBS_CACHE[key] = df
    return _OBS_CACHE[key]


def read_model_series(run_dir, category, variable):
    """Read one output variable from one QUINCY run directory as a
    single-column DataFrame indexed by datetime ('date')."""
    _fix_fluxnetdata_time_units(run_dir)
    parser = QNC_output_parser(run_dir)
    parser.Read()
    # Prefer, in order: the fluxnet-diagnostic output (real calendar dates,
    # possibly sub-daily), then the regular transient output. Never fall
    # back to "spinup" -- its dates are not the real simulation calendar and
    # would silently merge against the wrong period of the observations.
    for key in ("fluxnetdata", "transient"):
        if key in parser.Available_outputs:
            output = parser.Available_outputs[key]
            break
    else:
        raise RuntimeError(
            f"No 'transient' or 'fluxnetdata' output found in {run_dir} "
            f"(available: {list(parser.Available_outputs.keys())})")
    reader = QNC_ncdf_reader(run_dir, output.Categories, output.Identifier, output.Time_resolution)
    if not reader.Parse_env_and_variables():
        raise RuntimeError(f"Could not parse output in {run_dir}")
    df = reader.Read_1D_flat(category, variable)
    reader.Close()
    df = df.set_index("date")[[variable]]
    return df


def extract_metric_series(run_dir, metric):
    """Return the (model, obs) DataFrame merged on shared timestamps for one
    metric/run, with normalisation applied if requested.

    For a range-constraint metric (metric.is_range_constraint, no obs_file),
    there is no real observation to merge against: instead we build a
    pseudo-observation column, constant at the range's midpoint, over
    whichever of the model's own timestamps qualify (optionally restricted
    to metric.hour_start..hour_end for a "midday"-type constraint). Every
    other metric name (obs_column, sigma, weight, ...) already means the
    same thing from here on, so the rest of the pipeline (RMSE table,
    4D-En-Var stacking) doesn't need to know the difference.
    """
    df_mod = read_model_series(run_dir, metric.category, metric.variable)
    if metric.model_scale != 1.0:
        df_mod[metric.variable] = df_mod[metric.variable] * metric.model_scale

    if metric.is_range_constraint:
        if metric.hour_start is not None:
            df_mod = df_mod[(df_mod.index.hour >= metric.hour_start) & (df_mod.index.hour <= metric.hour_end)]
        merged = df_mod.copy()
        merged[metric.obs_column] = 0.5 * (metric.target_min + metric.target_max)
        return merged

    df_obs = load_observations(metric)
    merged = pd.merge(df_mod, df_obs, left_index=True, right_index=True, how="inner")
    if metric.normalize and not merged.empty:
        scale = np.max(np.abs(merged[metric.obs_column])) or 1.0
        merged[metric.variable] = merged[metric.variable] / scale
        merged[metric.obs_column] = merged[metric.obs_column] / scale
    return merged


def extract_ensemble_matrix(run_dirs, success, metrics):
    """Build everything qpy_calibrate.fourdenvar needs from a finished
    ensemble batch.

    For each metric we can only use timestamps for which (a) observations
    exist and (b) *every* successfully-run ensemble member produced output
    (a run that hydraulically fails/crashes early may cover a shorter
    period). We therefore intersect each metric's per-member available dates
    down to a common set before stacking, so every member contributes a
    same-length column to that metric's block of the observation vector.

    Returns
    -------
    Y        : (n_obs,) stacked observation vector across all metrics
    R_diag   : (n_obs,) observation-error variances (weight folded in)
    H        : (n_obs, n_ok) matrix, column j = model vector for the j-th
               successfully-run member (in the same order as `ok_idx`)
    ok_idx   : indices (into the original `run_dirs`/ensemble) that were
               used, i.e. ones that ran and had usable overlap for at least
               one metric
    table    : long-format per-member, per-metric RMSE table for diagnostics
    """
    ok_all = [i for i, s in enumerate(success) if s]
    if not ok_all:
        raise RuntimeError("No ensemble members finished successfully; nothing to calibrate against.")

    # H's columns must refer to the *same* set of ensemble members for every
    # metric block that gets stacked into it (the weight vector w is shared
    # across the whole observation vector). So a member that ran fine overall
    # but failed to produce even one configured metric (e.g. wrote PHYD
    # output but not Q_ASSIMI) must be dropped from *all* metrics, not just
    # the one it's missing -- otherwise that single member's date-set,
    # intersected into the "common dates" of a metric it's missing entirely
    # (an empty set), would silently zero out that metric for the whole
    # ensemble.
    merged_by_metric_member = {}
    for metric in metrics:
        merged_by_metric_member[metric.name] = {}
        for i in ok_all:
            try:
                merged = extract_metric_series(run_dirs[i], metric)
            except Exception as exc:
                print(f"[LAVENDAR] warning: could not read '{metric.name}' from {run_dirs[i]}: {exc}")
                merged = pd.DataFrame(columns=[metric.variable, metric.obs_column])
            merged_by_metric_member[metric.name][i] = merged

    ok_idx = [
        i for i in ok_all
        if all(len(merged_by_metric_member[m.name][i]) > 0 for m in metrics)
    ]
    if len(ok_idx) < len(ok_all):
        print(f"[LAVENDAR] {len(ok_all) - len(ok_idx)} member(s) ran but were missing at least "
              f"one configured metric's output and were dropped from this iteration.")
    if not ok_idx:
        raise RuntimeError(
            "No ensemble member produced usable output for all configured metrics. Check "
            "that 'category'/'variable' in each metric match the model output, and that "
            "obs_file paths are correct."
        )

    per_metric_dates = {}
    for metric in metrics:
        common_dates = None
        for i in ok_idx:
            dates = set(merged_by_metric_member[metric.name][i].index)
            common_dates = dates if common_dates is None else (common_dates & dates)
        per_metric_dates[metric.name] = sorted(common_dates) if common_dates else []
        if len(per_metric_dates[metric.name]) == 0:
            print(f"[LAVENDAR] warning: metric '{metric.name}' has no overlapping obs/model "
                  f"timestamps across the surviving ensemble and will be skipped this iteration.")

    usable_metrics = [m for m in metrics if len(per_metric_dates[m.name]) > 0]
    if not usable_metrics:
        raise RuntimeError("None of the configured metrics had any usable observation overlap.")

    y_parts, r_parts, h_rows = [], [], []
    rows_for_table = []

    for metric in usable_metrics:
        dates = per_metric_dates[metric.name]
        merged_by_member = merged_by_metric_member[metric.name]

        obs_vals = merged_by_member[ok_idx[0]].loc[dates, metric.obs_column].to_numpy(dtype=float)
        y_parts.append(obs_vals)

        if metric.sigma is not None:
            sigma = np.full_like(obs_vals, float(metric.sigma))
        else:
            sigma = metric.relative_sigma * np.maximum(np.abs(obs_vals), 1e-6)
        r_parts.append((sigma ** 2) / metric.weight)

        member_cols = []
        for i in ok_idx:
            mod_vals = merged_by_member[i].loc[dates, metric.variable].to_numpy(dtype=float)
            member_cols.append(mod_vals)
            rows_for_table.append(dict(
                member=i, metric=metric.name, n_obs=len(dates),
                rmse=rmse(mod_vals, obs_vals),
            ))
        h_rows.append(np.column_stack(member_cols))   # (n_dates_metric, n_ok)

    Y = np.concatenate(y_parts)
    R_diag = np.concatenate(r_parts)
    H = np.vstack(h_rows)
    table = pd.DataFrame(rows_for_table)

    return Y, R_diag, H, np.array(ok_idx), table
