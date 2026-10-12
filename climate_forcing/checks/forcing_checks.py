#!/usr/bin/env python3
"""
Dataset-agnostic consistency checks for the monthly forcing products
(ERA5, GLDAS, TerraClimate, ERA5-Land, ...), at any resolution and for any
selection of locations: the whole globe, a lat/lon box, or a list of sites.

Two layers:

  load_monthly()  reads a dataset's per-variable monthly files and normalises
                  them to one convention: canonical variable names
                  (VAR_ALIASES), canonical units (UNIT_CONVERSIONS), latitude
                  descending, longitude in [-180, 180), dims (time, lat, lon)
                  -- or (time, site) when sites are requested.
  check_*()       work on that normalised dict of DataArrays. They only assume
                  a leading time dimension, so the same check runs unchanged
                  on a global grid, a box or a handful of sites. Each returns
                  a CheckResult(name, passed, detail).

run_all_checks() runs every check whose variables are present.

Command line (prints a report, exit status 1 if any check fails):
  python forcing_checks.py --dataset gldas --res 0.5deg --years 2010
  python forcing_checks.py --dataset era5land --res 0.1deg --years 2010 --bbox 45 55 5 15
  python forcing_checks.py --dataset terraclimate --res 0.5deg --years 2000 2001 \\
      --site 50.95 10.45 --site -2.6 -60.2 --reference era5
  python forcing_checks.py --dir /some/folder --prefix mydata --res 0.5deg --years 2010
  python forcing_checks.py --file .../global_forcing/gldas_global_forcing_0.5deg_2000-2025.zarr --years 2010

The unit tests live in tests/consistency/test_forcing_checks.py.
"""
from __future__ import annotations

import argparse
import calendar
import re
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np
import xarray as xr

DRIVER_DATA = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data")

# dataset name -> (directory template with {res}, file prefix, available resolutions)
DATASETS = {
    "era5": ("era5/monthly/{res}", "era5", ["0.5deg", "0.25deg"]),
    "gldas": ("gldas/monthly/{res}", "gldas", ["0.5deg", "0.25deg"]),
    "terraclimate": ("terraclimate/monthly/{res}", "terraclimate", ["0.5deg"]),
    "era5land": ("era5_land/monthly/{res}", "era5land", ["0.1deg", "0.25deg", "0.5deg"]),
}

# Meteorological variables in canonical names and units.
CANONICAL_UNITS = {
    "t_air": "K", "t_air_min": "K", "t_air_max": "K",
    "precip_total": "mm day-1",
    "swvis_srf_down": "W m-2", "lw_srf_down": "W m-2",
    "q_air": "kg kg-1", "press_srf": "Pa", "wind_air": "m s-1",
    "cloud_cover": "1",
}

# source variable name -> canonical name
VAR_ALIASES = {
    "rain": "precip_total", "tmp": "t_air", "tmin": "t_air_min", "tmax": "t_air_max",
    "pre": "precip_total", "spfh": "q_air", "pres": "press_srf", "wind": "wind_air",
    "dswrf": "swvis_srf_down", "dlwrf": "lw_srf_down",
}

# normalised unit string -> (canonical unit, function converting values to it)
UNIT_CONVERSIONS = {
    "k": ("K", lambda x: x), "kelvin": ("K", lambda x: x), "degreeskelvin": ("K", lambda x: x),
    "degc": ("K", lambda x: x + 273.15), "c": ("K", lambda x: x + 273.15),
    "mmday-1": ("mm day-1", lambda x: x), "mm/day": ("mm day-1", lambda x: x),
    "mmd-1": ("mm day-1", lambda x: x),
    "kgm-2s-1": ("mm day-1", lambda x: x * 86400.0),
    "wm-2": ("W m-2", lambda x: x), "w/m2": ("W m-2", lambda x: x), "wm**-2": ("W m-2", lambda x: x),
    "kgkg-1": ("kg kg-1", lambda x: x), "kg/kg": ("kg kg-1", lambda x: x),
    "gkg-1": ("kg kg-1", lambda x: x / 1000.0), "g/kg": ("kg kg-1", lambda x: x / 1000.0),
    "pa": ("Pa", lambda x: x), "hpa": ("Pa", lambda x: x * 100.0), "kpa": ("Pa", lambda x: x * 1000.0),
    "ms-1": ("m s-1", lambda x: x), "m/s": ("m s-1", lambda x: x),
    "1": ("1", lambda x: x), "fraction": ("1", lambda x: x), "(0-1)": ("1", lambda x: x),
}

# Physically plausible bounds for monthly means, canonical units. Wide on
# purpose: they catch unit and sign mistakes, not climate anomalies.
RANGES = {
    "t_air": (180.0, 335.0), "t_air_min": (175.0, 330.0), "t_air_max": (185.0, 340.0),
    "precip_total": (0.0, 200.0),   # monsoon months at 0.1deg reach ~130 mm/day
    "swvis_srf_down": (0.0, 500.0), "lw_srf_down": (40.0, 550.0),
    "q_air": (0.0, 0.035), "press_srf": (40000.0, 110000.0),
    "wind_air": (0.0, 40.0), "cloud_cover": (0.0, 1.0),
}

SOLAR_CONSTANT = 1361.0  # W m-2


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""

    def __str__(self) -> str:
        return f"[{'PASS' if self.passed else 'FAIL'}] {self.name}: {self.detail}"


# --------------------------------------------------------------------------
# loading / normalisation
# --------------------------------------------------------------------------

def _unit_key(units: str) -> str:
    return re.sub(r"\s+", "", str(units)).lower()


def to_canonical_units(da: xr.DataArray, var: str) -> xr.DataArray:
    """Convert to CANONICAL_UNITS[var] based on the units attribute. Raises
    ValueError for units it doesn't know or that don't match the variable."""
    units = da.attrs.get("units")
    if units is None:
        raise ValueError(f"{var}: no units attribute")
    key = _unit_key(units)
    if key not in UNIT_CONVERSIONS:
        raise ValueError(f"{var}: unknown units {units!r}")
    canon, conv = UNIT_CONVERSIONS[key]
    if canon != CANONICAL_UNITS[var]:
        raise ValueError(f"{var}: units {units!r} are not compatible with {CANONICAL_UNITS[var]!r}")
    out = conv(da)
    out.attrs = dict(da.attrs, units=canon)
    return out


def normalise_grid(da: xr.DataArray) -> xr.DataArray:
    """Rename latitude/longitude to lat/lon, longitude to [-180, 180) sorted,
    latitude descending, and drop scalar/auxiliary coordinates."""
    da = da.rename({k: v for k, v in {"latitude": "lat", "longitude": "lon"}.items() if k in da.dims})
    if "lon" in da.dims:
        da = da.assign_coords(lon=((da["lon"] + 180.0) % 360.0) - 180.0).sortby("lon")
    if "lat" in da.dims:
        da = da.sortby("lat", ascending=False)
    keep = {"time", "lat", "lon"}
    return da.drop_vars([c for c in da.coords if c not in keep and c not in da.dims])


def select_locations(da: xr.DataArray, bbox: Optional[Sequence[float]] = None,
                     sites: Optional[Sequence[tuple[float, float]]] = None) -> xr.DataArray:
    """bbox = (lat_min, lat_max, lon_min, lon_max) in [-180, 180) longitudes;
    sites = [(lat, lon), ...] -> nearest grid cell each, new dim 'site'."""
    if bbox is not None:
        lat0, lat1, lon0, lon1 = bbox
        da = da.sel(lat=slice(lat1, lat0), lon=slice(lon0, lon1))
    if sites:
        lats = xr.DataArray([s[0] for s in sites], dims="site")
        lons = xr.DataArray([((s[1] + 180.0) % 360.0) - 180.0 for s in sites], dims="site")
        da = da.sel(lat=lats, lon=lons, method="nearest")
    return da


def dataset_dir(dataset: str, res: str, root: Path = DRIVER_DATA) -> Path:
    template, _, _ = DATASETS[dataset]
    return root / template.format(res=res)


def find_variable_files(directory: Path, prefix: str) -> dict[str, Path]:
    """{canonical var: file} for files named {prefix}_<var>[_derived]_<years>_monthly.nc."""
    found = {}
    for path in sorted(directory.glob(f"{prefix}_*_monthly.nc")):
        m = re.match(rf"{re.escape(prefix)}_(.+?)(?:_derived)?_\d{{4}}-\d{{4}}_monthly\.nc$", path.name)
        if not m:
            continue
        var = VAR_ALIASES.get(m.group(1), m.group(1))
        if var in CANONICAL_UNITS:
            found[var] = path
    return found


def load_monthly(directory: Path, prefix: str, years: Optional[Iterable[int]] = None,
                 bbox: Optional[Sequence[float]] = None,
                 sites: Optional[Sequence[tuple[float, float]]] = None) -> dict[str, xr.DataArray]:
    """Load and normalise every recognised meteorological variable in
    directory. Only the requested years/locations are read from disk."""
    out = {}
    for var, path in find_variable_files(directory, prefix).items():
        ds = xr.open_dataset(path, chunks={})
        # the field named after the variable (files may carry flags/masks next
        # to it); otherwise the one time-varying field, static ones (e.g.
        # TerraClimate's press_srf) as fallback
        names = ([n for n in ds.data_vars if VAR_ALIASES.get(n, n) == var]
                 or [n for n in ds.data_vars if "time" in ds[n].dims and ds[n].ndim >= 2]
                 or [n for n in ds.data_vars if ds[n].ndim >= 2])
        if len(names) != 1:
            raise ValueError(f"{path}: expected one gridded variable, found {names}")
        da = normalise_grid(ds[names[0]])
        if years is not None and "time" in da.dims:
            da = da.sel(time=da["time"].dt.year.isin(list(years)))
        da = select_locations(da, bbox, sites)
        out[var] = to_canonical_units(da.load(), var)
    return out


def load_multivar(path: Path, years: Optional[Iterable[int]] = None,
                  bbox: Optional[Sequence[float]] = None,
                  sites: Optional[Sequence[tuple[float, float]]] = None,
                  assume_canonical_units: bool = False) -> dict[str, xr.DataArray]:
    """Like load_monthly, for one file (or .zarr store) holding several
    variables -- e.g. the global_forcing stores or a per-year cache file.
    Variables without a units attribute raise unless assume_canonical_units."""
    path = Path(path)
    ds = (xr.open_zarr(path, consolidated=False) if path.suffix == ".zarr"
          else xr.open_dataset(path, chunks={}))
    out = {}
    for name in ds.data_vars:
        var = VAR_ALIASES.get(name, name)
        if var not in CANONICAL_UNITS or ds[name].ndim < 2:
            continue
        da = normalise_grid(ds[name])
        if years is not None and "time" in da.dims:
            da = da.sel(time=da["time"].dt.year.isin(list(years)))
        da = select_locations(da, bbox, sites).load()
        if assume_canonical_units and "units" not in da.attrs:
            da.attrs["units"] = CANONICAL_UNITS[var]
        out[var] = to_canonical_units(da, var)
    return out


# --------------------------------------------------------------------------
# physics helpers
# --------------------------------------------------------------------------

def saturation_specific_humidity(t_k, p_pa):
    """Bolton (1980) saturation vapour pressure -> specific humidity, same
    formula as common.specific_humidity_from_dewpoint with T in place of Td."""
    t_c = t_k - 273.15
    e = 611.2 * np.exp(17.67 * t_c / (t_c + 243.5))
    return 0.622 * e / (p_pa - 0.378 * e)


def toa_daily_insolation(lat_deg, doy):
    """Daily-mean top-of-atmosphere shortwave (W m-2) for latitude(s) and
    day(s) of year, standard declination/hour-angle formula."""
    lat = np.deg2rad(np.asarray(lat_deg, dtype=float))
    gamma = 2.0 * np.pi * (np.asarray(doy, dtype=float) - 1.0) / 365.0
    decl = (0.006918 - 0.399912 * np.cos(gamma) + 0.070257 * np.sin(gamma)
            - 0.006758 * np.cos(2 * gamma) + 0.000907 * np.sin(2 * gamma)
            - 0.002697 * np.cos(3 * gamma) + 0.00148 * np.sin(3 * gamma))
    dr = 1.0 + 0.033 * np.cos(gamma)
    cos_h0 = np.clip(-np.tan(lat) * np.tan(decl), -1.0, 1.0)
    h0 = np.arccos(cos_h0)
    return SOLAR_CONSTANT / np.pi * dr * (h0 * np.sin(lat) * np.sin(decl)
                                          + np.cos(lat) * np.cos(decl) * np.sin(h0))


def toa_monthly_insolation(lat_deg, year: int, month: int):
    ndays = calendar.monthrange(year, month)[1]
    doy0 = sum(calendar.monthrange(year, m)[1] for m in range(1, month)) + 1
    days = np.arange(doy0, doy0 + ndays)
    lat = np.asarray(lat_deg, dtype=float)
    return toa_daily_insolation(lat[..., None], days).mean(axis=-1)


def _lat_broadcast(da: xr.DataArray) -> xr.DataArray:
    """Latitude of every element of da (works for (time, lat, lon) and (time, site))."""
    return xr.broadcast(da["lat"], da)[0].transpose(*da.dims)


def _frac(mask) -> float:
    mask = np.asarray(mask)
    return float(mask.mean()) if mask.size else 0.0


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------

def check_time_axis(fields: dict[str, xr.DataArray],
                    expected_years: Optional[Iterable[int]] = None) -> CheckResult:
    """Every variable: monthly steps stamped on one day of the month, all 12
    months of every year present and in order, identical axes across
    variables. The years must be exactly expected_years if given (e.g. a
    non-contiguous selection), otherwise consecutive."""
    problems, ref = [], None
    expected = sorted(set(expected_years)) if expected_years is not None else None
    for var, da in fields.items():
        if "time" not in da.dims:
            continue
        t = da["time"].to_index()
        if len(t) == 0:
            problems.append(f"{var}: empty time axis")
            continue
        months = t.year * 12 + t.month
        years = sorted(set(t.year))
        if np.any(np.diff(months) <= 0):
            problems.append(f"{var}: time not strictly increasing")
        incomplete = [y for y in years if sorted(t.month[t.year == y]) != list(range(1, 13))]
        if incomplete:
            problems.append(f"{var}: incomplete years {incomplete[:5]}")
        if expected is not None and years != expected:
            problems.append(f"{var}: years {years[0]}..{years[-1]} ({len(years)}) differ from the requested ones")
        elif expected is None and years != list(range(years[0], years[-1] + 1)):
            problems.append(f"{var}: missing years between {years[0]} and {years[-1]}")
        if len(set(t.day)) != 1:
            problems.append(f"{var}: inconsistent day-of-month stamps {sorted(set(t.day))}")
        key = tuple(months)
        if ref is None:
            ref = (var, key)
        elif key != ref[1]:
            problems.append(f"{var}: time axis differs from {ref[0]}")
    return CheckResult("time_axis", not problems, "; ".join(problems) or "monthly, consecutive, aligned")


def check_ranges(fields: dict[str, xr.DataArray]) -> CheckResult:
    problems = []
    for var, da in fields.items():
        lo, hi = RANGES[var]
        vals = da.values
        finite = vals[np.isfinite(vals)]
        if finite.size == 0:
            problems.append(f"{var}: no finite values")
            continue
        n_out = int(np.sum((finite < lo) | (finite > hi)))
        if n_out:
            problems.append(f"{var}: {n_out} values outside [{lo}, {hi}] "
                            f"(min {finite.min():.4g}, max {finite.max():.4g})")
    return CheckResult("physical_ranges", not problems, "; ".join(problems) or "all within bounds")


def check_temperature_order(fields: dict[str, xr.DataArray], tol: float = 0.05) -> CheckResult:
    """t_air_min <= t_air <= t_air_max (and min <= max without a mean)."""
    if not {"t_air_min", "t_air_max"} <= fields.keys():
        return CheckResult("temperature_order", True, "skipped: needs t_air_min and t_air_max")
    tmin, tmax = fields["t_air_min"], fields["t_air_max"]
    pairs = [("t_air_min", "t_air_max", tmin, tmax)]
    if "t_air" in fields:
        pairs += [("t_air_min", "t_air", tmin, fields["t_air"]), ("t_air", "t_air_max", fields["t_air"], tmax)]
    problems = []
    for a, b, lo, hi in pairs:
        diff = (lo - hi).values
        bad = np.isfinite(diff) & (diff > tol)
        if bad.any():
            problems.append(f"{a} > {b} at {_frac(bad[np.isfinite(diff)]):.4%} of values "
                            f"(worst by {np.nanmax(diff):.2f} K)")
    return CheckResult("temperature_order", not problems, "; ".join(problems) or "min <= mean <= max")


def check_humidity_saturation(fields: dict[str, xr.DataArray], rel_tol: float = 0.05) -> CheckResult:
    """q_air must not exceed saturation at the warmest monthly temperature
    available (t_air_max, else t_air) and the surface pressure (standard
    pressure if the dataset has none)."""
    if "q_air" not in fields:
        return CheckResult("humidity_saturation", True, "skipped: no q_air")
    t = fields.get("t_air_max", fields.get("t_air"))
    if t is None:
        return CheckResult("humidity_saturation", True, "skipped: no temperature")
    p = fields.get("press_srf")
    p_vals = p.values if p is not None else 101325.0   # static (lat, lon) pressure broadcasts too
    q = fields["q_air"].values
    qsat = saturation_specific_humidity(t.values, p_vals)
    ratio = q / qsat
    finite = np.isfinite(ratio)
    bad = finite & (ratio > 1.0 + rel_tol)
    detail = (f"q > qsat(T{'max' if 't_air_max' in fields else ''}) at {_frac(bad[finite]):.4%} of values, "
              f"max ratio {np.nanmax(ratio):.3f}") if bad.any() else f"max q/qsat {np.nanmax(ratio):.3f}"
    return CheckResult("humidity_saturation", not bad.any(), detail)


def check_common_mask(fields: dict[str, xr.DataArray], tol: float = 0.0) -> CheckResult:
    """All time-varying variables are missing at the same locations (a cell
    is 'missing' if it is NaN at every time step)."""
    masks = {v: np.isnan(da.values).all(axis=0) for v, da in fields.items() if "time" in da.dims}
    if len(masks) < 2:
        return CheckResult("common_mask", True, "skipped: fewer than two variables")
    ref_var, ref = next(iter(masks.items()))
    problems = []
    for var, m in masks.items():
        if m.shape != ref.shape:
            problems.append(f"{var}: grid shape {m.shape} differs from {ref_var} {ref.shape}")
            continue
        mismatch = _frac(m != ref)
        if mismatch > tol:
            problems.append(f"{var}: mask differs from {ref_var} at {mismatch:.4%} of cells")
    return CheckResult("common_mask", not problems, "; ".join(problems) or f"{len(masks)} variables share one mask")


def check_shortwave_vs_toa(fields: dict[str, xr.DataArray], rel_tol: float = 0.02,
                           polar_night_wm2: float = 5.0) -> CheckResult:
    """Surface shortwave <= top-of-atmosphere insolation for that latitude and
    month, and ~0 where the sun doesn't rise (polar night)."""
    if "swvis_srf_down" not in fields:
        return CheckResult("shortwave_vs_toa", True, "skipped: no swvis_srf_down")
    sw = fields["swvis_srf_down"]
    t = sw["time"].to_index()
    lat = _lat_broadcast(sw.isel(time=0)).values
    toa = np.stack([toa_monthly_insolation(lat, y, m) for y, m in zip(t.year, t.month)])
    vals = sw.values
    finite = np.isfinite(vals)
    over = finite & (vals > toa * (1.0 + rel_tol) + 1.0)
    dark = finite & (toa < 1.0) & (vals > polar_night_wm2)
    problems = []
    if over.any():
        problems.append(f"SW > TOA at {_frac(over[finite]):.4%} of values (max SW/TOA "
                        f"{np.nanmax(np.where(toa > 1, vals / toa, np.nan)):.2f})")
    if dark.any():
        problems.append(f"SW > {polar_night_wm2} W m-2 during polar night at {int(dark.sum())} values")
    return CheckResult("shortwave_vs_toa", not problems, "; ".join(problems) or "below TOA, dark in polar night")


def check_seasonality(fields: dict[str, xr.DataArray], min_lat: float = 30.0,
                      min_frac: float = 0.95) -> CheckResult:
    """Outside the tropics, July is warmer than January in the north and
    colder in the south: catches flipped latitude axes and shifted months."""
    t = fields.get("t_air")
    if t is None and {"t_air_min", "t_air_max"} <= fields.keys():
        t = 0.5 * (fields["t_air_min"] + fields["t_air_max"])
    if t is None:
        return CheckResult("seasonality", True, "skipped: no temperature")
    month = t["time"].dt.month
    if not ({1, 7} <= set(month.values.tolist())):
        return CheckResult("seasonality", True, "skipped: needs January and July")
    jul = t.where(month == 7, drop=True).mean("time").values
    jan = t.where(month == 1, drop=True).mean("time").values
    lat = _lat_broadcast(t.isel(time=0)).values
    problems = []
    for name, sel, sign in [("NH", lat > min_lat, 1.0), ("SH", lat < -min_lat, -1.0)]:
        ok_vals = np.isfinite(jul) & np.isfinite(jan) & sel
        if not ok_vals.any():
            continue
        frac = _frac((sign * (jul - jan))[ok_vals] > 0)
        if frac < min_frac:
            problems.append(f"{name}: expected sign of July-January in only {frac:.1%} of cells")
    return CheckResult("seasonality", not problems, "; ".join(problems) or "hemispheric seasons correct")


def check_coarsening(fine: xr.DataArray, coarse: xr.DataArray, atol: float, name: str = "") -> CheckResult:
    """coarse equals the NaN-aware block mean of fine, for products built by
    exact block averaging (e.g. ERA5-Land 0.1 -> 0.25/0.5). Both on (time, lat, lon)."""
    label = f"coarsening{('_' + name) if name else ''}"
    ratio = fine.sizes["lat"] / coarse.sizes["lat"]
    f = fine.values
    if abs(ratio - 2.5) < 1e-9:
        f = np.repeat(np.repeat(f, 2, axis=-2), 2, axis=-1)
        k = 5
    elif abs(ratio - round(ratio)) < 1e-9:
        k = int(round(ratio))
    else:
        return CheckResult(label, False, f"unsupported resolution ratio {ratio}")
    *lead, ny, nx = f.shape
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        expected = np.nanmean(f.reshape(*lead, ny // k, k, nx // k, k), axis=(-3, -1))
    got = coarse.values
    both = np.isfinite(expected) & np.isfinite(got)
    nan_mismatch = int(np.sum(np.isfinite(expected) != np.isfinite(got)))
    err = float(np.max(np.abs(expected[both] - got[both]))) if both.any() else 0.0
    passed = err <= atol and nan_mismatch == 0
    return CheckResult(label, passed, f"max |diff| {err:.3g}, NaN-pattern mismatches {nan_mismatch}")


def compare_to_reference(fields: dict[str, xr.DataArray], reference: dict[str, xr.DataArray],
                         mean_tol: Optional[dict[str, tuple[str, float]]] = None,
                         min_corr: Optional[dict[str, float]] = None) -> list[CheckResult]:
    """Same-location comparison against another dataset (nearest reference
    cell). Tolerances are loose: different products legitimately differ, the
    point is catching unit, sign, grid-flip and month-shift errors."""
    mean_tol = mean_tol or {
        "t_air": ("abs", 2.0), "t_air_min": ("abs", 2.5), "t_air_max": ("abs", 2.5),
        "precip_total": ("rel", 0.3), "swvis_srf_down": ("rel", 0.1), "lw_srf_down": ("rel", 0.05),
        "q_air": ("rel", 0.15), "press_srf": ("rel", 0.03), "wind_air": ("rel", 0.6),
    }
    # independent precipitation products typically agree at r~0.8-0.9 for
    # 0.5deg monthly values; everything else is held to 0.9
    min_corr = {"precip_total": 0.8, **(min_corr or {})}
    results = []
    for var in sorted(fields.keys() & reference.keys()):
        if var not in mean_tol:
            continue
        a, b = fields[var], reference[var]
        if "lat" in a.dims and "lat" in b.dims and "site" not in a.dims:
            b = b.sel(lat=a["lat"], lon=a["lon"], method="nearest")
            b = b.assign_coords(lat=a["lat"], lon=a["lon"])
        a, b = xr.align(a, b, join="inner")
        a, b = xr.broadcast(a, b)               # e.g. a static climatology vs a time series
        b = b.transpose(*a.dims)
        av, bv = a.values, b.values
        ok = np.isfinite(av) & np.isfinite(bv)
        if ok.sum() < 10:
            results.append(CheckResult(f"reference_{var}", True, "skipped: too little overlap"))
            continue
        w = np.cos(np.deg2rad(_lat_broadcast(a).values))[ok]
        ma, mb = np.average(av[ok], weights=w), np.average(bv[ok], weights=w)
        kind, tol = mean_tol[var]
        diff = abs(ma - mb) if kind == "abs" else abs(ma / mb - 1.0)
        # a constant field has no correlation to speak of: judge it on the mean alone
        constant = np.std(av[ok]) == 0 or np.std(bv[ok]) == 0
        corr = np.nan if constant else float(np.corrcoef(av[ok], bv[ok])[0, 1])
        r_min = min_corr.get(var, 0.9)
        passed = diff <= tol and (constant or corr >= r_min)
        results.append(CheckResult(
            f"reference_{var}", passed,
            f"mean {ma:.4g} vs {mb:.4g} ({'diff' if kind == 'abs' else 'rel diff'} {diff:.3g}, tol {tol}), "
            + ("r=n/a (constant field)" if constant else f"r={corr:.3f} (min {r_min})")))
    return results


ALL_CHECKS = [check_time_axis, check_ranges, check_temperature_order, check_humidity_saturation,
              check_common_mask, check_shortwave_vs_toa, check_seasonality]


def run_all_checks(fields: dict[str, xr.DataArray],
                   reference: Optional[dict[str, xr.DataArray]] = None,
                   expected_years: Optional[Iterable[int]] = None) -> list[CheckResult]:
    results = [check_time_axis(fields, expected_years)]
    results += [check(fields) for check in ALL_CHECKS if check is not check_time_axis]
    if reference:
        results += compare_to_reference(fields, reference)
    return results


# --------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--dataset", choices=sorted(DATASETS))
    src.add_argument("--dir", type=Path, help="any folder of {prefix}_<var>_<years>_monthly.nc files")
    src.add_argument("--file", type=Path, help="one multi-variable .nc file or .zarr store")
    ap.add_argument("--prefix", help="file prefix with --dir")
    ap.add_argument("--res", default="0.5deg")
    ap.add_argument("--years", type=int, nargs="+")
    ap.add_argument("--bbox", type=float, nargs=4, metavar=("LAT_MIN", "LAT_MAX", "LON_MIN", "LON_MAX"))
    ap.add_argument("--site", type=float, nargs=2, action="append", metavar=("LAT", "LON"))
    ap.add_argument("--reference", choices=sorted(DATASETS), help="also compare against this dataset")
    ap.add_argument("--reference-res", default="0.5deg")
    args = ap.parse_args(argv)

    sites = [tuple(s) for s in args.site] if args.site else None
    if args.file:
        directory, prefix = args.file, ""
        fields = load_multivar(args.file, args.years, args.bbox, sites)
    else:
        if args.dataset:
            directory, prefix = dataset_dir(args.dataset, args.res), DATASETS[args.dataset][1]
        else:
            if not args.prefix:
                ap.error("--dir needs --prefix")
            directory, prefix = args.dir, args.prefix
        fields = load_monthly(directory, prefix, args.years, args.bbox, sites)
    if not fields:
        print(f"no recognised monthly variables in {directory} {prefix!r}")
        return 1
    reference = None
    if args.reference:
        reference = load_monthly(dataset_dir(args.reference, args.reference_res), DATASETS[args.reference][1],
                                 args.years, args.bbox, sites)
    print(f"{directory} ({prefix}): {', '.join(sorted(fields))}")
    results = run_all_checks(fields, reference, args.years)
    for r in results:
        print(r)
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
