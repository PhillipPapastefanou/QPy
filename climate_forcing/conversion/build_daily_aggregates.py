#!/usr/bin/env python3
"""
Derive *daily* forcing outputs from datasets that were already downloaded
at a finer time resolution than daily -- this is pure local reprocessing
of the raw cache each download_*.py script already keeps under
<out-dir>/raw/, no new downloads.

Whether daily is even possible depends on the dataset's native time
resolution, checked per-dataset rather than assumed:

  - CRU-JRA: native 6-hourly -- daily is a real, meaningful aggregation.
    Reads driver_data/crujra/raw/v3.0/<var>/*.nc (populated by
    download_crujra.py) and resamples each year to daily immediately after
    opening it, mirroring how the monthly script resamples per-year before
    concatenating -- confirmed live 2026-09-06 that concatenating the full
    124-year raw 6-hourly record before resampling would allocate ~187 GB;
    resampling to daily first (still a 4x reduction from 6-hourly) then
    caching one small file per year, and only concatenating those cached
    yearly files via a dask-chunked open_mfdataset + to_netcdf write,
    avoids ever holding more than ~1 year of raw + 1 variable's full daily
    record in memory at once.
  - TerraClimate: native monthly. There is no finer-resolution TerraClimate
    product to derive daily from (the public THREDDS catalog only serves
    monthly files -- see download_terraclimate_monthly.py's docstring) --
    this script recognizes that and skips TerraClimate with an explanation
    rather than attempting something the source data can't support.

Usage:
  cd conversion
  python build_daily_aggregates.py --variables tmp tmax tmin pre \
      --start-year 1901 --end-year 2024
  # explicitly include/exclude datasets (default: both, TerraClimate always
  # just prints why it's skipped)
  python build_daily_aggregates.py --datasets crujra --start-year 2015 --end-year 2024
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import CRUJRA_FLUX_SCALE, get_logger, resample_daily, wind_speed_from_components

LOG = get_logger("build-daily")

DRIVER_ROOT = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data")

CRUJRA_VARIABLES = ["tmp", "tmax", "tmin", "spfh", "pres", "dswrf", "dlwrf", "pre", "ugrd", "vgrd"]
CRUJRA_AGGREGATION = {v: "mean" for v in CRUJRA_VARIABLES}
CRUJRA_AGGREGATION["pre"] = "sum"


def crujra_process_variable(var: str, years: list[int], version: str, raw_dir: Path, out_dir: Path) -> None:
    LOG.info(f"[CRU-JRA] Processing variable '{var}' -> daily")
    start, end = years[0], years[-1]
    out_subdir = out_dir / "daily" / "0.5deg"
    out_path = out_subdir / f"crujra_v{version}_{var}_{start}-{end}_daily.nc"
    if out_path.exists():
        LOG.info(f"  already have {out_path.name}, skipping")
        return

    var_raw_dir = raw_dir / var
    files = {int(f.stem.split(".")[-3]): f for f in var_raw_dir.glob("*.nc") if f.stem.split(".")[-3].isdigit()}
    if not files:
        LOG.warning(f"  no cached raw files under {var_raw_dir} -- run download_crujra.py for "
                    f"'{var}' first, skipping")
        return

    how = CRUJRA_AGGREGATION.get(var, "mean")
    yearly_cache_dir = raw_dir.parent / "daily_yearly_cache" / var
    yearly_cache_dir.mkdir(parents=True, exist_ok=True)
    yearly_files = []
    for year in years:
        year_cache = yearly_cache_dir / f"{var}_{year}_daily.nc"
        if year_cache.exists():
            yearly_files.append(year_cache)
            continue
        if year not in files:
            LOG.warning(f"  no cached raw file for {var} {year}, skipping that year")
            continue
        ds = xr.open_dataset(files[year])
        data_var = var if var in ds.data_vars else list(ds.data_vars)[0]
        raw_da = ds[data_var]
        if var in CRUJRA_FLUX_SCALE:
            raw_da = raw_da * CRUJRA_FLUX_SCALE[var]
        daily = resample_daily(raw_da, how=how).load()
        daily.to_dataset(name=var).to_netcdf(year_cache, encoding={var: {"zlib": True, "complevel": 4}})
        ds.close()
        yearly_files.append(year_cache)

    if not yearly_files:
        LOG.warning(f"  nothing to aggregate for '{var}', skipping")
        return

    full = xr.open_mfdataset(yearly_files, combine="nested", concat_dim="time", chunks={"time": 365})
    out_subdir.mkdir(parents=True, exist_ok=True)
    full[[var]].to_netcdf(out_path, encoding={var: {"zlib": True, "complevel": 4}})
    full.close()
    LOG.info(f"  wrote {out_path}")


def crujra_process_wind_speed(years: list[int], version: str, raw_dir: Path, out_dir: Path) -> None:
    LOG.info("[CRU-JRA] Deriving daily wind speed from ugrd/vgrd")
    start, end = years[0], years[-1]
    out_subdir = out_dir / "daily" / "0.5deg"
    out_path = out_subdir / f"crujra_v{version}_wind_{start}-{end}_daily.nc"
    if out_path.exists():
        LOG.info(f"  already have {out_path.name}, skipping")
        return

    u_dir, v_dir = raw_dir / "ugrd", raw_dir / "vgrd"
    u_files = {int(f.stem.split(".")[-3]): f for f in u_dir.glob("*.nc") if f.stem.split(".")[-3].isdigit()}
    v_files = {int(f.stem.split(".")[-3]): f for f in v_dir.glob("*.nc") if f.stem.split(".")[-3].isdigit()}
    if not u_files or not v_files:
        LOG.warning("  no cached ugrd/vgrd raw files -- run download_crujra.py first, skipping")
        return

    yearly_cache_dir = raw_dir.parent / "daily_yearly_cache" / "wind"
    yearly_cache_dir.mkdir(parents=True, exist_ok=True)
    yearly_files = []
    for year in years:
        year_cache = yearly_cache_dir / f"wind_{year}_daily.nc"
        if year_cache.exists():
            yearly_files.append(year_cache)
            continue
        if year not in u_files or year not in v_files:
            continue
        u_ds = xr.open_dataset(u_files[year])
        v_ds = xr.open_dataset(v_files[year])
        u_var = "ugrd" if "ugrd" in u_ds.data_vars else list(u_ds.data_vars)[0]
        v_var = "vgrd" if "vgrd" in v_ds.data_vars else list(v_ds.data_vars)[0]
        speed = wind_speed_from_components(u_ds[u_var], v_ds[v_var])
        daily = resample_daily(speed, how="mean").load()
        daily.to_dataset(name="wind").to_netcdf(year_cache, encoding={"wind": {"zlib": True, "complevel": 4}})
        u_ds.close()
        v_ds.close()
        yearly_files.append(year_cache)

    if not yearly_files:
        LOG.warning("  nothing to aggregate for wind, skipping")
        return

    full = xr.open_mfdataset(yearly_files, combine="nested", concat_dim="time", chunks={"time": 365})
    out_subdir = out_dir / "daily" / "0.5deg"
    out_subdir.mkdir(parents=True, exist_ok=True)
    full[["wind"]].to_netcdf(out_path, encoding={"wind": {"zlib": True, "complevel": 4}})
    full.close()
    LOG.info(f"  wrote {out_path}")


def terraclimate_skip() -> None:
    LOG.info("[TerraClimate] Daily aggregation not applicable -- TerraClimate's native "
             "resolution is already monthly (confirmed against the public THREDDS catalog: "
             "no finer-than-monthly TerraClimate product exists to derive daily from). "
             "Skipping.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datasets", nargs="+", choices=["crujra", "terraclimate"],
                         default=["crujra", "terraclimate"])
    parser.add_argument("--variables", nargs="+", default=CRUJRA_VARIABLES,
                         help=f"CRU-JRA variables to aggregate to daily (default: all {CRUJRA_VARIABLES})")
    parser.add_argument("--derive-wind", action="store_true", default=True,
                         help="also derive daily scalar wind speed from ugrd/vgrd (default: on)")
    parser.add_argument("--no-derive-wind", dest="derive_wind", action="store_false")
    parser.add_argument("--ceda-version", default="3.0")
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--crujra-out-dir", type=Path, default=DRIVER_ROOT / "crujra")
    args = parser.parse_args()

    bad = set(args.variables) - set(CRUJRA_VARIABLES)
    if bad:
        raise SystemExit(f"Unknown CRU-JRA variables: {sorted(bad)}. Valid: {CRUJRA_VARIABLES}")

    years = list(range(args.start_year, args.end_year + 1))

    if "terraclimate" in args.datasets:
        terraclimate_skip()

    if "crujra" in args.datasets:
        raw_dir = args.crujra_out_dir / "raw" / f"v{args.ceda_version}"
        for var in args.variables:
            crujra_process_variable(var, years, args.ceda_version, raw_dir, args.crujra_out_dir)
        if args.derive_wind:
            crujra_process_wind_speed(years, args.ceda_version, raw_dir, args.crujra_out_dir)

    LOG.info("Done.")


if __name__ == "__main__":
    main()
