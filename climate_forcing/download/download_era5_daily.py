#!/usr/bin/env python3
"""
Download ERA5 daily statistics (Copernicus CDS) -- the direct answer to
"does ERA5 have tmin/tmax": the standard monthly-means product
(download_era5_monthly.py) does NOT (confirmed live 2026-09-05 -- CDS
silently drops maximum/minimum temperature from that product). This
script instead uses CDS's server-side daily-aggregation service, which
computes daily mean/max/min/sum from hourly ERA5 on demand, so tmax/tmin
(and a full daily-resolution variable set) are directly available without
downloading raw hourly data yourself.

Access: same `cdsapi` + `~/.cdsapirc` setup as download_era5_monthly.py.
Dataset id: derived-era5-single-levels-daily-statistics (confirmed live
2026-09-05 with a real request/download -- product_type "reanalysis",
daily_statistic in {daily_mean, daily_maximum, daily_minimum, daily_sum},
time_zone "utc+00:00", frequency "1_hourly").

IMPORTANT: a "daily_statistic" applies to an entire request -- you cannot
mix daily_mean for one variable and daily_maximum for another in a single
call. This script therefore issues *four* CDS requests per year-chunk:
  1. daily_mean:    2m_temperature, 2m_dewpoint_temperature, surface_pressure,
                     10m_u/v_component_of_wind, surface_solar/thermal_radiation
                     _downwards, total_cloud_cover
  2. daily_maximum: 2m_temperature                          -> t_air_max (tmax)
  3. daily_minimum: 2m_temperature                          -> t_air_min (tmin)
  4. daily_sum:     total_precipitation                     -> precip_total

REGRIDDING: --grid "0.5/0.5" (the default here) asks CDS to regrid
server-side to match CRU-JRA/GSWP3-W5E5/WFDE5's native 0.5deg grid,
confirmed working live 2026-09-05 (exact 0.5deg spacing verified in the
output). Pass --grid "" to keep ERA5's native 0.25deg instead.

SIZE WARNING: daily data is far bigger than the monthly product. Even at
0.5deg (4x fewer points than native 0.25deg), a full global 1940-2025
pull across 11 variable-series is very roughly 60-100+ GB and involves
4x as many CDS jobs as the monthly script for the same year range --
expect a multi-hour run for the full record. Start with a bounded
--area/year-range test before committing to a full global historical
pull; there is no default start/end year for exactly this reason.

Usage:
  # regional, one decade, matches the Jena example site used elsewhere in this repo
  python download_era5_daily.py --start-year 2015 --end-year 2024 --area 55 5 47 16
  # global, full record, regridded to 0.5deg (large -- see SIZE WARNING)
  python download_era5_daily.py --start-year 1940 --end-year 2025
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import pandas as pd
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_logger, write_monthly_netcdf, year_chunks

LOG = get_logger("era5-daily")

DATASET_ID = "derived-era5-single-levels-daily-statistics"
DEFAULT_OUT_DIR = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/era5")
DEFAULT_GRID = "0.5/0.5"

MEAN_VARIABLES = [
    "2m_temperature", "2m_dewpoint_temperature", "surface_pressure",
    "10m_u_component_of_wind", "10m_v_component_of_wind",
    "surface_solar_radiation_downwards", "surface_thermal_radiation_downwards",
    "total_cloud_cover",
]

# (request tag, daily_statistic, variables, output var-name overrides)
REQUEST_GROUPS = [
    ("mean", "daily_mean", MEAN_VARIABLES, {}),
    ("tmax", "daily_maximum", ["2m_temperature"], {"t2m": "t_air_max"}),
    ("tmin", "daily_minimum", ["2m_temperature"], {"t2m": "t_air_min"}),
    ("precip_sum", "daily_sum", ["total_precipitation"], {"tp": "precip_total"}),
]

MEAN_GROUP_RENAME = {
    "t2m": "t_air", "sp": "press_srf",
    "ssrd": "swvis_srf_down", "strd": "lw_srf_down", "tcc": "cloud_cover",
    "u10": "u10", "v10": "v10", "d2m": "d2m",
}


def get_client():
    try:
        import cdsapi
    except ImportError as e:
        raise SystemExit('The "cdsapi" package is required: pip install "cdsapi>=0.7.7"') from e
    return cdsapi.Client()


def download_chunk(client, daily_statistic: str, variables: list[str], start_year: int, end_year: int,
                    area, grid, raw_path: Path) -> Path:
    if raw_path.exists():
        LOG.info(f"    already have {raw_path.name}, skipping request")
        return raw_path

    request = {
        "product_type": "reanalysis",
        "variable": variables,
        "year": [str(y) for y in range(start_year, end_year + 1)],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "day": [f"{d:02d}" for d in range(1, 32)],  # CDS ignores invalid day/month combos
        "daily_statistic": daily_statistic,
        "time_zone": "utc+00:00",
        "frequency": "1_hourly",
    }
    if area:
        request["area"] = area
    if grid:
        request["grid"] = grid

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    LOG.info(f"    submitting CDS request ({daily_statistic}, {variables}) for {start_year}-{end_year}...")
    client.retrieve(DATASET_ID, request).download(str(raw_path))
    return raw_path


def _open_raw(raw_path: Path) -> xr.Dataset:
    """Open one request's response, whether a plain NetCDF or a zip of
    several (defensive -- the monthly-means product does this, this one
    didn't in testing, but the request pattern is close enough to be
    cautious). Drops the singleton "number" (ensemble) dim CDS attaches,
    and renames "valid_time" -> "time" for consistency with the rest of
    this toolkit.
    """
    if zipfile.is_zipfile(raw_path):
        extract_dir = raw_path.parent / f"{raw_path.stem}_extracted"
        with zipfile.ZipFile(raw_path) as zf:
            zf.extractall(extract_dir)
        parts = [xr.open_dataset(p) for p in sorted(extract_dir.glob("*.nc"))]
        ds = xr.merge(parts, compat="override")
    else:
        ds = xr.open_dataset(raw_path)

    if "number" in ds.dims:
        ds = ds.squeeze("number", drop=True)
    if "valid_time" in ds.dims:
        ds = ds.rename({"valid_time": "time"})
    return ds


def write_group_outputs(tag: str, ds: xr.Dataset, out_dir: Path, start_year: int, end_year: int, grid_tag: str) -> None:
    if tag == "mean":
        for src, dst in MEAN_GROUP_RENAME.items():
            if src in ds.data_vars and dst not in ("u10", "v10", "d2m"):
                write_monthly_netcdf(ds[src], out_dir / f"era5_{dst}_{start_year}-{end_year}{grid_tag}_daily.nc", dst)
                LOG.info(f"    wrote {dst}")
        if {"u10", "v10"}.issubset(ds.data_vars):
            import numpy as np
            speed = xr.apply_ufunc(np.hypot, ds["u10"], ds["v10"])
            speed.attrs.update(long_name="wind speed", units="m s-1")
            write_monthly_netcdf(speed, out_dir / f"era5_wind_air_{start_year}-{end_year}{grid_tag}_daily.nc", "wind_air")
            LOG.info("    wrote wind_air (derived from u10/v10)")
    elif tag == "tmax" and "t2m" in ds.data_vars:
        write_monthly_netcdf(ds["t2m"], out_dir / f"era5_t_air_max_{start_year}-{end_year}{grid_tag}_daily.nc", "t_air_max")
        LOG.info("    wrote t_air_max (tmax)")
    elif tag == "tmin" and "t2m" in ds.data_vars:
        write_monthly_netcdf(ds["t2m"], out_dir / f"era5_t_air_min_{start_year}-{end_year}{grid_tag}_daily.nc", "t_air_min")
        LOG.info("    wrote t_air_min (tmin)")
    elif tag == "precip_sum" and "tp" in ds.data_vars:
        write_monthly_netcdf(ds["tp"], out_dir / f"era5_precip_total_{start_year}-{end_year}{grid_tag}_daily.nc", "precip_total")
        LOG.info("    wrote precip_total (daily sum)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--area", type=float, nargs=4, metavar=("NORTH", "WEST", "SOUTH", "EAST"),
                         default=None, help="optional bounding box, omit for global")
    parser.add_argument("--grid", default=DEFAULT_GRID,
                         help=f'target resolution (default: "{DEFAULT_GRID}", matching CRU-JRA/'
                              'GSWP3-W5E5/WFDE5); pass --grid "" to keep native 0.25 deg')
    parser.add_argument("--chunk-years", type=int, default=5,
                         help="years per CDS request (default: 5 -- smaller than the monthly "
                              "script's default since daily payloads are much larger)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                         help=f"default: {DEFAULT_OUT_DIR}")
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--groups", nargs="+", default=None,
                         choices=[tag for tag, _, _, _ in REQUEST_GROUPS],
                         help="request only these REQUEST_GROUPS tags (default: all 4). The 'mean' "
                              "group alone requests 8 variables and is the one most likely to hit "
                              "CDS's per-request cost limit at global/multi-year scope -- confirmed "
                              "live 2026-09-08 (global, 1 year, 8 variables -> 403 'cost limits "
                              "exceeded'); request tmax/tmin (1 variable each) on their own to work "
                              "around that instead of shrinking area/years for a request that doesn't "
                              "need the mean group's variables at all.")
    args = parser.parse_args()

    raw_dir = args.raw_dir or (args.out_dir / "raw")
    raw_dir.mkdir(parents=True, exist_ok=True)

    # dataset/time_resolution/spatial_resolution/ layout -- resolution now
    # lives in the directory, filenames no longer need a grid tag.
    res_label = f"{args.grid.split('/')[0]}deg" if args.grid else "0.25deg"
    out_subdir = args.out_dir / "daily" / res_label
    out_subdir.mkdir(parents=True, exist_ok=True)

    client = get_client()
    chunks = year_chunks(args.start_year, args.end_year, args.chunk_years)
    grid_tag = f"_grid{args.grid.replace('/', 'x')}" if args.grid else ""

    groups = [g for g in REQUEST_GROUPS if args.groups is None or g[0] in args.groups]
    LOG.info(f"{len(chunks)} chunk(s) x {len(groups)} request group(s) ({[g[0] for g in groups]}): "
              f"{chunks[0][0]}-{chunks[-1][1]}, {args.chunk_years}y each, "
              f"{'global' if not args.area else args.area}, grid={args.grid or 'native 0.25deg'}")

    for tag, daily_statistic, variables, _ in groups:
        LOG.info(f"Variable group '{tag}' ({daily_statistic})")
        datasets = []
        for i, (c_start, c_end) in enumerate(chunks, 1):
            LOG.info(f"  chunk {i}/{len(chunks)}: {c_start}-{c_end}")
            raw_path = raw_dir / f"era5_daily_{tag}_{c_start}-{c_end}{grid_tag}.nc"
            download_chunk(client, daily_statistic, variables, c_start, c_end, args.area, args.grid, raw_path)
            datasets.append(_open_raw(raw_path))

        full = xr.concat(datasets, dim="time").sortby("time")
        write_group_outputs(tag, full, out_subdir, args.start_year, args.end_year, "")
        for d in datasets:
            d.close()

    LOG.info(f"Done. {args.start_year}-{args.end_year} written to {out_subdir}")


if __name__ == "__main__":
    main()
