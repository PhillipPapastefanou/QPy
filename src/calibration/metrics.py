"""Observation loading and model-output evaluation for one ensemble member.

Generalises the RMSE pattern of
science/phillip/DE-Hai/bench/post_process_complete_single.py (merge model
output on the obs CSV's date index, compute RMSE) to an arbitrary list of
metrics. evaluate_member() runs inside each member's SLURM task right after
QUINCY has finished, so the expensive NetCDF reading happens in parallel and
the raw output can be deleted immediately afterwards.
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
            print(f"[calibration] warning: could not normalize time units in {path}: {exc}")


def typical_sigma(metric):
    """The observation-error std of a metric. For an absolute `sigma` (or a
    range constraint, which derives one automatically in MetricSpec) this is
    just metric.sigma; for `relative_sigma` it's relative to the mean
    magnitude of the observations. A single value per metric avoids tiny
    sigmas at near-zero observations (e.g. night-time sap flow) dominating
    the score. None if the metric has neither."""
    if metric.sigma is not None:
        return float(metric.sigma)
    if metric.relative_sigma is None:
        return None
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
    shift = getattr(metric, "obs_time_shift_hours", 0.0)
    key = (metric.obs_file, metric.obs_column, metric.obs_index_col, metric.clip_negative_obs_to_zero, shift)
    if key not in _OBS_CACHE:
        df = pd.read_csv(metric.obs_file, index_col=metric.obs_index_col, parse_dates=True)
        if metric.obs_column not in df.columns:
            raise ValueError(f"Column '{metric.obs_column}' not found in {metric.obs_file}")
        df = df[[metric.obs_column]].dropna()
        if metric.clip_negative_obs_to_zero:
            df[metric.obs_column] = df[metric.obs_column].clip(lower=0.0)
        if shift:
            df.index = df.index + pd.Timedelta(hours=shift)
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
    metric/run.

    For a range-constraint metric (metric.is_range_constraint, no obs_file),
    there is no real observation to merge against: instead we build a
    pseudo-observation column, constant at the range's midpoint, over
    whichever of the model's own timestamps qualify (optionally restricted
    to metric.hour_start..hour_end for a "midday"-type constraint, to
    metric.months and to metric.year_start..year_end), or over one aggregate
    per year (or of the whole selection) if metric.aggregate is set.
    """
    df_mod = read_model_series(run_dir, metric.category, metric.variable)
    if metric.model_scale != 1.0:
        df_mod[metric.variable] = df_mod[metric.variable] * metric.model_scale

    if metric.is_range_constraint:
        # getattr: metric objects pickled before these options existed
        idx = df_mod.index
        if metric.hour_start is not None:
            df_mod = df_mod[(idx.hour >= metric.hour_start) & (idx.hour <= metric.hour_end)]
        if getattr(metric, "months", None):
            df_mod = df_mod[df_mod.index.month.isin(metric.months)]
        if getattr(metric, "year_start", None) is not None:
            df_mod = df_mod[df_mod.index.year >= metric.year_start]
        if getattr(metric, "year_end", None) is not None:
            df_mod = df_mod[df_mod.index.year <= metric.year_end]
        if getattr(metric, "aggregate", None) and len(df_mod):
            # One value per period, dated at the period's first timestamp
            keys = df_mod.index.year if metric.aggregate_period == "year" else np.zeros(len(df_mod), dtype=int)
            grouped = df_mod[metric.variable].groupby(keys)
            df_mod = pd.DataFrame({metric.variable: grouped.agg(metric.aggregate).to_numpy()},
                                  index=pd.DatetimeIndex(df_mod.index.to_series().groupby(keys).first().to_numpy(),
                                                         name=df_mod.index.name))
        merged = df_mod.copy()
        merged[metric.obs_column] = 0.5 * (metric.target_min + metric.target_max)
        return merged

    df_obs = load_observations(metric)
    return pd.merge(df_mod, df_obs, left_index=True, right_index=True, how="inner")


def evaluate_member(run_dir, metrics):
    """Score one finished QUINCY run against all metrics.

    Returns (result, series):
      result : dict with "ok", "reason" and per metric "rmse_<name>",
               "nmse_<name>" (mean squared error in units of sigma^2) and "n_<name>"
      series : long DataFrame (metric, date, model, obs) of the model values at
               the observation timestamps, kept for the plots

    A member counts as failed if a metric has no overlapping timestamps or if
    its model output is completely flat (a dead plant, e.g. after hydraulic
    failure, writes constant values instead of crashing).
    """
    result = {"ok": True, "reason": ""}
    parts = []
    for metric in metrics:
        merged = extract_metric_series(run_dir, metric).dropna()
        mod = merged[metric.variable].to_numpy(dtype=float)
        obs = merged[metric.obs_column].to_numpy(dtype=float)
        sigma = typical_sigma(metric)

        result[f"n_{metric.name}"] = len(mod)
        result[f"rmse_{metric.name}"] = rmse(mod, obs)
        result[f"nmse_{metric.name}"] = (float(np.mean(((mod - obs) / sigma) ** 2))
                                         if len(mod) and sigma is not None else float("nan"))

        if len(mod) == 0:
            result["ok"], result["reason"] = False, f"no overlap with observations for {metric.name}"
        elif len(mod) > 1 and np.ptp(mod) == 0.0 and result["ok"]:
            result["ok"], result["reason"] = False, f"flat model output for {metric.name} (dead plant?)"

        parts.append(pd.DataFrame({"metric": metric.name, "date": merged.index, "model": mod, "obs": obs}))

    series = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["metric", "date", "model", "obs"])
    return result, series


def spread_sigma(metric):
    """Natural variability of the observations (e.g. between trees), as a
    standard deviation: the mean distance between the two quantile columns
    obs_spread_columns, divided by that distance for a normal distribution.
    None if the metric has no obs_spread_columns."""
    if metric.obs_spread_columns is None:
        return None
    from scipy.stats import norm
    lo_col, hi_col = metric.obs_spread_columns
    q_lo, q_hi = metric.obs_spread_quantiles
    df = pd.read_csv(metric.obs_file, index_col=metric.obs_index_col)
    width = (df[hi_col] - df[lo_col]).dropna()
    return float(width.mean() / (norm.ppf(q_hi) - norm.ppf(q_lo)))


STAT_NAMES = ("bias", "r", "nse", "maxabs", "nwithin")


def series_stats(series, metric):
    """Statistics of one metric from a member's series (model and obs at the
    observation timestamps): RMSE, bias (model - obs), correlation, NSE, the
    largest |model - obs|, and for constraints the number of observations
    within the tolerance."""
    g = series[series["metric"] == metric.name].dropna(subset=["model", "obs"])
    mod, obs = g["model"].to_numpy(dtype=float), g["obs"].to_numpy(dtype=float)
    out = {f"{k}_{metric.name}": float("nan") for k in STAT_NAMES}
    if len(mod) == 0:
        return out
    err = mod - obs
    out[f"bias_{metric.name}"] = float(err.mean())
    out[f"maxabs_{metric.name}"] = float(np.abs(err).max())
    if len(mod) > 2 and np.std(obs) > 0:
        out[f"nse_{metric.name}"] = float(1 - np.mean(err ** 2) / np.var(obs))
        if np.std(mod) > 0:
            out[f"r_{metric.name}"] = float(np.corrcoef(mod, obs)[0, 1])
    if metric.tolerance is not None:
        out[f"nwithin_{metric.name}"] = int((np.abs(err) <= metric.tolerance).sum())
    return out


def add_stats(results, metrics, output_root):
    """Add the series_stats columns to the ok members of results that don't
    have them yet, reading each member's series file (round_dir is relative
    to output_root, or absolute for members of earlier calibrations)."""
    from src.calibration.member_task import series_path
    results = results.copy()
    for m in metrics:
        for k in STAT_NAMES:
            if f"{k}_{m.name}" not in results.columns:
                results[f"{k}_{m.name}"] = np.nan
    first = f"bias_{metrics[0].name}"
    todo = results.index[results["ok"].astype(bool) & results[first].isna()]
    for i in todo:
        path = series_path(os.path.join(output_root, results.at[i, "round_dir"]), int(results.at[i, "member"]))
        if not os.path.isfile(path):
            continue
        series = pd.read_csv(path)
        for m in metrics:
            for col, value in series_stats(series, m).items():
                results.at[i, col] = value
    return results


def score_reference(metric, method, best_rmse):
    """The RMSE an objective is divided by in the score:
    "reference": the observation spread if given, else sigma, else best_rmse;
    "sigma": sigma; "relative": best_rmse (the best any member reached)."""
    if method == "relative":
        return best_rmse
    if method == "sigma":
        return typical_sigma(metric)
    for ref in (spread_sigma(metric), typical_sigma(metric)):
        if ref is not None:
            return ref
    return best_rmse


def score_members(results, metrics, method="reference"):
    """Score and rank all ok members together (the "relative" reference
    depends on every member run so far, so scores are recomputed each round).

    Adds per objective "ratio_<name>" = RMSE / reference, "score" = the mean
    over the objectives of max(weight * ratio, 1) (with method="relative": the
    largest weight * ratio), and "feasible" = every constraint has at least
    min_within_fraction of its observations within the tolerance. Returns
    the ok members, best first: those passing all constraints by score, then
    the others by score. Constraints only filter: how far a member misses
    one never steers the search."""
    ok = results[results["ok"].astype(bool)].copy()
    objectives = [m for m in metrics if m.role == "objective"]
    constraints = [m for m in metrics if m.role == "constraint"]

    ratios = []
    for m in objectives:
        rmse_m = ok[f"rmse_{m.name}"].astype(float)
        ref = score_reference(m, method, rmse_m.min())
        ok[f"ratio_{m.name}"] = rmse_m / ref
        ratios.append(m.weight * ok[f"ratio_{m.name}"])
    ratios = np.column_stack(ratios)
    if method == "relative":
        ok["score"] = ratios.max(axis=1)
    else:
        # Within its spread/sigma a metric is as good as the data can tell
        # (counts as 1); above it, every metric's excess counts
        ok["score"] = np.maximum(ratios, 1.0).mean(axis=1)

    feasible = np.ones(len(ok), dtype=bool)
    for m in constraints:
        within = ok[f"nwithin_{m.name}"].astype(float).fillna(0)
        needed = np.ceil(m.min_within_fraction * ok[f"n_{m.name}"].astype(float) - 1e-9)
        feasible &= (within >= needed).to_numpy()
    ok["feasible"] = feasible
    return ok.sort_values(["feasible", "score"], ascending=[False, True])
