"""
Shared helpers for the climate_forcing download scripts.

Every dataset-specific script (download_crujra.py, download_gswp3_w5e5.py,
download_era5_monthly.py, download_wfde5_monthly.py,
download_terraclimate_monthly.py) reduces its source data to monthly
NetCDF files using the helpers here, so all outputs share one convention:

  - time dimension named "time", monthly timestamps stamped on the 1st
    of each month (pandas "MS" / month-start).
  - one output file per variable, covering the whole requested year range.
  - output file naming: {dataset}_{variable}_{start}-{end}_monthly.nc
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import requests
import xarray as xr


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


@dataclass
class BoundingBox:
    """Geographic subset, CDS/ISIMIP style ordering kept explicit per field."""
    west: float
    east: float
    south: float
    north: float


SECONDS_PER_6H = 21600.0

# CRU-JRA's dswrf arrives as accumulated J/m2 over each 6-hour window, not
# an average W/m2 despite its 'W/m^2' units attribute (which is simply
# wrong -- confirmed empirically 2026-09-07 against a raw v3.0 sample:
# treating it as already-W/m2 produced a diurnal cycle peaking near 5e7
# W/m2, ~65% of the whole grid above the solar constant of 1361 W/m2;
# dividing by SECONDS_PER_6H turns the same four daily values into a
# textbook diurnal cycle, ~0 at night, ~500 W/m2 at midday for a tropical
# site). dlwrf does NOT need this -- checked the same way, it was already
# correct (412-429 W/m2). Shared here so download_crujra.py and
# build_daily_aggregates.py apply the identical fix rather than each
# hardcoding the constant separately.
CRUJRA_FLUX_SCALE = {"dswrf": 1.0 / SECONDS_PER_6H}


def resample_monthly(da: xr.DataArray, how: str = "mean", time_dim: str = "time") -> xr.DataArray:
    """Resample a sub-monthly DataArray to monthly values.

    how="mean" for state variables (temperature, pressure, humidity, wind,
    radiation fluxes in W/m2). how="sum" for accumulated fluxes that arrive
    as per-timestep depths (e.g. precipitation already in mm/timestep) that
    should be summed to a monthly total.
    """
    resampled = da.resample({time_dim: "MS"})
    if how == "mean":
        out = resampled.mean()
    elif how == "sum":
        out = resampled.sum()
    else:
        raise ValueError(f"Unknown aggregation '{how}', expected 'mean' or 'sum'")
    out.attrs = dict(da.attrs)
    out.attrs["monthly_aggregation"] = how
    return out


def resample_daily(da: xr.DataArray, how: str = "mean", time_dim: str = "time") -> xr.DataArray:
    """Resample a sub-daily DataArray to daily values. how="mean"/"sum" as in
    resample_monthly(); "min"/"max" additionally supported here (used to
    derive daily tmin/tmax from sub-daily instantaneous temperature, e.g.
    GLDAS's 3-hourly Tair_f_inst -- see
    climate_forcing/conversion/derive_gldas_tmin_tmax.py). Works on
    cftime-indexed data (e.g. CRU-JRA's 365-day no-leap calendar) the same
    way xarray's "MS" resample already does elsewhere in this toolkit --
    "1D" is equally supported.
    """
    resampled = da.resample({time_dim: "1D"})
    if how == "mean":
        out = resampled.mean()
    elif how == "sum":
        out = resampled.sum()
    elif how == "min":
        out = resampled.min()
    elif how == "max":
        out = resampled.max()
    else:
        raise ValueError(f"Unknown aggregation '{how}', expected 'mean', 'sum', 'min', or 'max'")
    out.attrs = dict(da.attrs)
    out.attrs["daily_aggregation"] = how
    return out


def count_wet_days_monthly(precip_da: xr.DataArray, threshold_mm: float = 1.0,
                            time_dim: str = "time") -> xr.DataArray:
    """Count days per month where daily precip exceeds `threshold_mm`.

    Expects `precip_da` already resampled to a daily time axis with units
    of mm/day. QUINCY-style forcing pipelines use this as the "wetdays"
    field consumed by the sub-daily weather generator.
    """
    wet = (precip_da > threshold_mm).astype("int8")
    out = wet.resample({time_dim: "MS"}).sum()
    out.attrs["long_name"] = "number of wet days per month"
    out.attrs["threshold_mm"] = threshold_mm
    return out


def wind_speed_from_components(u_da: xr.DataArray, v_da: xr.DataArray) -> xr.DataArray:
    speed = np.hypot(u_da, v_da)
    speed.attrs["long_name"] = "wind speed"
    speed.attrs["units"] = "m s-1"
    return speed


def specific_humidity_from_dewpoint(t2d_k: xr.DataArray, sp_pa: xr.DataArray) -> xr.DataArray:
    """Approximate 2 m specific humidity (kg/kg) from 2 m dewpoint temperature
    and surface pressure, using the Bolton (1980) saturation vapour pressure
    formula. This is the standard fallback for datasets (like ERA5) that
    report dewpoint rather than specific/relative humidity directly.
    """
    t2d_c = t2d_k - 273.15
    e_hpa = 6.112 * np.exp((17.67 * t2d_c) / (t2d_c + 243.5))
    e_pa = e_hpa * 100.0
    q = (0.622 * e_pa) / (sp_pa - 0.378 * e_pa)
    q.attrs["long_name"] = "near-surface specific humidity (derived from dewpoint)"
    q.attrs["units"] = "kg kg-1"
    return q


def standard_atmosphere_pressure_kpa(elevation_m: xr.DataArray) -> xr.DataArray:
    """Approximate surface pressure (kPa) from elevation via the ICAO
    standard-atmosphere barometric formula: P = P0 * (1 - 2.25577e-5*z)^5.25588,
    P0 = 101.325 kPa.

    This is climatological, not synoptic -- it captures the dominant
    (topographic) control on surface pressure but not day-to-day weather
    variation, since it depends only on a static elevation field. Added for
    datasets (TerraClimate) that don't report surface pressure at all, so
    specific humidity can still be derived from actual vapour pressure
    (see specific_humidity_from_vapor_pressure below) instead of having no
    pressure field whatsoever.
    """
    p = 101.325 * (1.0 - 2.25577e-5 * elevation_m) ** 5.25588
    p.attrs["long_name"] = "surface pressure (derived from elevation, standard atmosphere)"
    p.attrs["units"] = "kPa"
    p.attrs["comment"] = "climatological estimate from elevation only, no synoptic variation"
    return p


def specific_humidity_from_vapor_pressure(ea_kpa: xr.DataArray, p_kpa: xr.DataArray) -> xr.DataArray:
    """Specific humidity (kg/kg) from actual vapour pressure and total
    (surface) pressure, both in kPa: q = 0.622 e / (p - 0.378 e). Unlike
    specific_humidity_from_dewpoint, this does not need the Bolton formula
    at all -- it's for datasets (TerraClimate's "vap") that already report
    actual vapour pressure directly rather than dewpoint temperature.
    """
    q = (0.622 * ea_kpa) / (p_kpa - 0.378 * ea_kpa)
    q.attrs["long_name"] = "near-surface specific humidity (derived from vapor pressure)"
    q.attrs["units"] = "kg kg-1"
    return q


def write_monthly_netcdf(da: xr.DataArray, out_path: Path, var_name: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds = da.to_dataset(name=var_name)
    encoding = {var_name: {"zlib": True, "complevel": 4}}
    ds.to_netcdf(out_path, encoding=encoding)


def retry_request(fn: Callable, logger: logging.Logger, max_retries: int = 4,
                   backoff_seconds: float = 20.0):
    """Call fn() with retries on transient network errors (HTTP 5xx,
    timeouts, connection resets). Raises the final exception once retries
    are exhausted.

    Added 2026-09-06 after a live crash: CEDA returned a single transient
    500 for one CRU-JRA year-file mid-way through a multi-day download, and
    with no retry logic that killed the entire script, losing the rest of
    an unattended run until someone noticed and restarted it by hand. HTTP
    4xx (bad request, not found, auth failure) is NOT retried -- retrying
    those just wastes time re-hitting the same permanent error.
    """
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status is not None and 400 <= status < 500:
                raise  # permanent client error -- retrying won't help
            if attempt == max_retries:
                raise
            wait = backoff_seconds * attempt
            logger.warning(f"  request failed ({e}), retrying in {wait:.0f}s "
                            f"(attempt {attempt}/{max_retries})")
            time.sleep(wait)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt == max_retries:
                raise
            wait = backoff_seconds * attempt
            logger.warning(f"  connection error ({e}), retrying in {wait:.0f}s "
                            f"(attempt {attempt}/{max_retries})")
            time.sleep(wait)


def open_dataset_verified(path: Path, redownload_fn: Callable[[], None], logger: logging.Logger) -> xr.Dataset:
    """Open a cached NetCDF file; if it fails (truncated/corrupted from an
    earlier interrupted download), delete it and call redownload_fn() once
    to fetch it fresh before giving up.

    Added 2026-09-06 after a live crash: a TerraClimate raw yearly file was
    truncated to ~77% of its expected size by an earlier killed process.
    The download step's `if dest.exists(): skip` check only checks
    existence, not validity, so the bad file sat there undetected until
    this open() call hit an HDF error and crashed the whole script. This
    makes that specific failure self-healing instead of fatal.
    """
    try:
        return xr.open_dataset(path)
    except (OSError, ValueError) as e:
        # OSError: a truncated-but-recognizable HDF5/NetCDF file (confirmed
        # live 2026-09-06: "NetCDF: HDF error" on a file cut off mid-write).
        # ValueError: xarray can't even guess a backend for totally garbage
        # content (confirmed via a synthetic test after the fact -- the
        # live incident happened to be the OSError case, but a corrupted
        # download could just as easily produce this instead).
        logger.warning(f"  {path.name} failed to open ({e}) -- assuming corrupted, redownloading")
        path.unlink(missing_ok=True)
        redownload_fn()
        return xr.open_dataset(path)


def env_or_none(name: str) -> Optional[str]:
    val = os.environ.get(name)
    return val if val else None


def default_output_root() -> Path:
    return Path(env_or_none("CLIMATE_FORCING_OUT") or (Path(__file__).parent / "data"))


def year_chunks(start_year: int, end_year: int, chunk_years: int) -> list[tuple[int, int]]:
    """Split [start_year, end_year] into consecutive (chunk_start, chunk_end)
    blocks of at most chunk_years, used to keep any single CDS/CEDA/ISIMIP
    request bounded in size and independently resumable/cacheable."""
    chunks = []
    y = start_year
    while y <= end_year:
        y_end = min(y + chunk_years - 1, end_year)
        chunks.append((y, y_end))
        y = y_end + 1
    return chunks
