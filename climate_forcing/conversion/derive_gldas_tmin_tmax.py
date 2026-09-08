#!/usr/bin/env python3
"""
Derive GLDAS monthly t_air_min/t_air_max -- pure local reprocessing of
already-downloaded raw data, no new network access.

Why this exists: GLDAS Noah has no native tmin/tmax product (unlike
CRU-JRA/TerraClimate). But download_gldas.py's daily_0.25deg product already
downloads GLDAS_NOAH025_3H.2.1's instantaneous Tair_f_inst at 8 synoptic
times/day (00/03/06/09/12/15/18/21 UTC) to build a daily *mean* -- the
min/max across those same 8 samples is sitting in already-downloaded raw
files (driver_data/gldas/raw/3hourly/<year>/<doy>/*.nc4) and simply never
computed. This script reads those same files again (no re-download) and
writes the monthly mean-of-daily-minimum/maximum temperature, matching the
convention CRU-JRA/TerraClimate's own "tmin"/"tmax" monthly variables
already use (mean of daily extremes, not the single most extreme value of
the month).

CAVEAT (unlike CRU-JRA/TerraClimate's continuous-record tmin/tmax): 8
synoptic samples/day is a coarser sampling than a true continuous daily
min/max -- the real diurnal extreme can fall between two 3-hourly samples
and be missed, so this is an *approximation*, biased slightly toward the
mean relative to a true continuous-record tmin/tmax. Written with a
"_derived" filename suffix for the same reason
derive_terraclimate_humidity_pressure.py uses it: never mistaken for a
native GLDAS product.

COVERAGE: only years with a complete set of raw 3-hourly files already on
disk are processed (confirmed 2000-2018 present, 2019-2025 not yet
downloaded as of 2026-09-08 -- run download_gldas.py --products
daily_0.25deg first to extend coverage; this script does not download
anything itself).

Usage:
  cd conversion
  python derive_gldas_tmin_tmax.py --start-year 2000 --end-year 2018
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_logger, resample_daily, resample_monthly, write_monthly_netcdf

LOG = get_logger("gldas-tmin-tmax")

DEFAULT_RAW_DIR = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/gldas/raw")
DEFAULT_OUT_DIR = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/gldas")


def coarsen_to_half_degree(ds: xr.Dataset) -> xr.Dataset:
    """Exact 2x2 block-mean, same method (and same 600x1440 -> 300x720 exact
    divisibility) as download_gldas.py's coarsen_to_half_degree() -- kept as
    a local copy rather than a cross-script import since download/ and
    conversion/ aren't packages here (no __init__.py), and it's one line.
    """
    return ds.coarsen(lat=2, lon=2, boundary="exact").mean()


def process_year(year: int, raw_dir: Path, cache_dir: Path) -> Path | None:
    cache_path = cache_dir / f"gldas_tmin_tmax_monthly_{year}.nc"
    if cache_path.exists():
        LOG.info(f"  year {year} already cached, skipping")
        return cache_path

    day_files = sorted((raw_dir / "3hourly" / str(year)).glob("*/*.nc4"))
    if not day_files:
        LOG.warning(f"  no raw 3-hourly files for {year} under {raw_dir / '3hourly' / str(year)}, skipping")
        return None
    expected = 366 * 8 if _is_leap(year) else 365 * 8
    if len(day_files) < expected:
        LOG.warning(f"  {year}: only {len(day_files)}/{expected} 3-hourly files present -- "
                    f"processing anyway, some days/months may be based on fewer than 8 samples")

    ds = xr.open_mfdataset(day_files, combine="nested", concat_dim="time", chunks={"time": 8 * 31},
                            parallel=False)
    ds = ds.sortby("time")
    tair = ds["Tair_f_inst"]

    daily_min = resample_daily(tair, how="min")
    daily_max = resample_daily(tair, how="max")
    monthly_tmin = resample_monthly(daily_min, how="mean").load()
    monthly_tmax = resample_monthly(daily_max, how="mean").load()
    ds.close()

    monthly_tmin.attrs.update(units="K", long_name="monthly mean of daily minimum 2m air temperature",
                              source="GLDAS_NOAH025_3H.2.1 Tair_f_inst, 8 synoptic samples/day (approximate, "
                                     "see module docstring)")
    monthly_tmax.attrs.update(units="K", long_name="monthly mean of daily maximum 2m air temperature",
                              source="GLDAS_NOAH025_3H.2.1 Tair_f_inst, 8 synoptic samples/day (approximate, "
                                     "see module docstring)")

    out = xr.Dataset({"t_air_min": monthly_tmin, "t_air_max": monthly_tmax})
    cache_dir.mkdir(parents=True, exist_ok=True)
    out.to_netcdf(cache_path, encoding={v: {"zlib": True, "complevel": 4} for v in out.data_vars})
    LOG.info(f"  year {year} done, cached to {cache_path}")
    return cache_path


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--start-year", type=int, required=True)
    p.add_argument("--end-year", type=int, required=True)
    p.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = p.parse_args()

    cache_dir = args.raw_dir / "tmin_tmax_yearly"
    yearly_files = []
    for year in range(args.start_year, args.end_year + 1):
        result = process_year(year, args.raw_dir, cache_dir)
        if result is not None:
            yearly_files.append(result)

    if not yearly_files:
        LOG.warning("No years processed, nothing to write.")
        return

    full = xr.open_mfdataset(yearly_files, combine="nested", concat_dim="time").sortby("time")
    first_year = int(full["time"].dt.year.min())
    last_year = int(full["time"].dt.year.max())

    for res_label, transform in (("0.25deg", lambda d: d), ("0.5deg", coarsen_to_half_degree)):
        out_subdir = args.out_dir / "monthly" / res_label
        transformed = transform(full)
        for var in ("t_air_min", "t_air_max"):
            out_path = out_subdir / f"gldas_{var}_derived_{first_year}-{last_year}_monthly.nc"
            write_monthly_netcdf(transformed[var], out_path, var)
            LOG.info(f"  wrote {out_path}")
    full.close()


if __name__ == "__main__":
    main()
