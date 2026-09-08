#!/usr/bin/env python3
"""
Derive TerraClimate press_srf and q_air -- pure local reprocessing, no
new per-year downloads (the one exception being the static elevation
layer, a single 149 MB file fetched once by download_terraclimate_monthly.py
--with-dem, not a per-year loop, so this script still only *reads* raw/
rather than looping over the network like the download/ scripts do).

Why this exists: TerraClimate has no surface-pressure variable at all, and
without pressure "vap" (actual vapour pressure, kPa) can't be turned into
specific humidity -- see README.md's TerraClimate limitations. The fix
used here is the same one WATCH/CRU-style forcing products use when a
pressure field is missing: approximate it from elevation via the ICAO
standard-atmosphere barometric formula (see
common.standard_atmosphere_pressure_kpa). This is climatological, not
synoptic -- it captures the dominant topographic control on pressure but
not day-to-day weather variation, since it depends on a static DEM, not a
time-varying atmospheric field. Good enough for land-surface forcing use,
not a substitute for a real reanalysis pressure field.

TerraClimate's own DEM (terraclim_dem.nc) is on the exact same 1/24deg
grid as every variable file, confirmed live 2026-09-07 -- no regridding
needed, just a direct broadcast against each year's time axis.

Both derived variables are written with the "_derived" filename suffix
(unlike every other file this toolkit produces) specifically so they're
never mistaken for native TerraClimate output the way tmax/vap/etc are --
they're a documented approximation, not measured/reanalysis data.

Usage:
  cd conversion
  python derive_terraclimate_humidity_pressure.py --start-year 1958 --end-year 2025
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_logger, specific_humidity_from_vapor_pressure, standard_atmosphere_pressure_kpa

LOG = get_logger("terraclimate-humidity-pressure")

DEFAULT_OUT_DIR = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/terraclimate")


def _load_dem(raw_dir: Path) -> xr.DataArray:
    dem_path = raw_dir / "ancillary" / "terraclim_dem.nc"
    if not dem_path.exists():
        raise SystemExit(
            f"{dem_path} not found -- run:\n"
            f"  cd ../download && python download_terraclimate_monthly.py --with-dem "
            f"--variables vap --start-year 1958 --end-year 1958\n"
            f"(--with-dem alone also works if vap is already cached; the --variables/--start-year/"
            f"--end-year above are only needed the very first time to satisfy argparse)"
        )
    ds = xr.open_dataset(dem_path)
    return ds["elevation"]


def process(years: list[int], raw_dir: Path, out_dir: Path) -> None:
    start, end = years[0], years[-1]
    out_subdir = out_dir / "monthly" / "4km"
    press_path = out_subdir / f"terraclimate_press_srf_derived_{start}-{end}_monthly.nc"
    q_path = out_subdir / f"terraclimate_q_air_derived_{start}-{end}_monthly.nc"
    if press_path.exists() and q_path.exists():
        LOG.info(f"  already have {press_path.name} and {q_path.name}, skipping")
        return

    vap_dir = raw_dir / "vap"
    vap_files = {int(f.stem.split("_")[-1]): f for f in vap_dir.glob("TerraClimate_vap_*.nc")}
    missing = [y for y in years if y not in vap_files]
    if missing:
        LOG.warning(f"  missing cached vap for years {missing[:3]}{'...' if len(missing) > 3 else ''} -- "
                    f"run download_terraclimate_monthly.py --variables vap first for the full range, skipping")
        return

    elevation = _load_dem(raw_dir)
    # static per-gridpoint -- computed once, broadcast against each year's
    # 12-timestep vap file below (same shape, same lat/lon grid).
    pressure_kpa = standard_atmosphere_pressure_kpa(elevation)

    # Same memory-safety pattern as download_terraclimate_monthly.py's
    # process_variable() and build_daily_aggregates.py: resolve each year
    # immediately after opening it and cache the small per-year result,
    # rather than concatenating 68 years of full-resolution (4320x8640)
    # data before computing anything.
    yearly_cache_dir = raw_dir.parent / "derived_yearly_cache"
    press_cache_dir = yearly_cache_dir / "press_srf"
    q_cache_dir = yearly_cache_dir / "q_air"
    press_cache_dir.mkdir(parents=True, exist_ok=True)
    q_cache_dir.mkdir(parents=True, exist_ok=True)

    press_yearly_files, q_yearly_files = [], []
    for year in years:
        press_cache = press_cache_dir / f"press_srf_{year}.nc"
        q_cache = q_cache_dir / f"q_air_{year}.nc"
        if press_cache.exists() and q_cache.exists():
            press_yearly_files.append(press_cache)
            q_yearly_files.append(q_cache)
            continue

        ds = xr.open_dataset(vap_files[year])
        vap = ds["vap"] if "vap" in ds.data_vars else ds[list(ds.data_vars)[0]]

        press_year = pressure_kpa.broadcast_like(vap).astype("float32")
        press_year.attrs = dict(pressure_kpa.attrs)
        press_year.to_dataset(name="press_srf").to_netcdf(
            press_cache, encoding={"press_srf": {"zlib": True, "complevel": 4}})

        q_year = specific_humidity_from_vapor_pressure(vap, pressure_kpa).astype("float32")
        q_year.to_dataset(name="q_air").to_netcdf(
            q_cache, encoding={"q_air": {"zlib": True, "complevel": 4}})

        ds.close()
        press_yearly_files.append(press_cache)
        q_yearly_files.append(q_cache)
        LOG.info(f"  derived {year}")

    out_subdir.mkdir(parents=True, exist_ok=True)

    press_full = xr.open_mfdataset(press_yearly_files, combine="nested", concat_dim="time", chunks={"time": 12})
    press_full[["press_srf"]].to_netcdf(press_path, encoding={"press_srf": {"zlib": True, "complevel": 4}})
    press_full.close()
    LOG.info(f"  wrote {press_path}")

    q_full = xr.open_mfdataset(q_yearly_files, combine="nested", concat_dim="time", chunks={"time": 12})
    q_full[["q_air"]].to_netcdf(q_path, encoding={"q_air": {"zlib": True, "complevel": 4}})
    q_full.close()
    LOG.info(f"  wrote {q_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help=f"default: {DEFAULT_OUT_DIR}")
    parser.add_argument("--raw-dir", type=Path, default=None)
    args = parser.parse_args()

    years = list(range(args.start_year, args.end_year + 1))
    raw_dir = args.raw_dir or (args.out_dir / "raw")
    process(years, raw_dir, args.out_dir)
    LOG.info("Done.")


if __name__ == "__main__":
    main()
