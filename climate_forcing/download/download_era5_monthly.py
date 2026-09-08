#!/usr/bin/env python3
"""
Download ERA5 monthly-averaged reanalysis (Copernicus CDS) -- natively
monthly, so no resampling step is needed; this is the cheapest/most
reliable dataset in this toolkit and a good fallback when CRU-JRA/ISIMIP
access is unavailable. It has no rain/snow split and no direct specific
humidity (both are derived here from what ERA5 does provide).

Access: `cdsapi` (pip install "cdsapi>=0.7.7"), needs a free CDS account
and a `~/.cdsapirc` file:

    url: https://cds.climate.copernicus.eu/api
    key: <PERSONAL-ACCESS-TOKEN>

(token from your profile page after login at
https://cds.climate.copernicus.eu/, per the current CDS setup guide,
checked 2026-09-05). Dataset id: reanalysis-era5-single-levels-monthly-means.

Variables requested: 2m_temperature, 2m_dewpoint_temperature,
surface_pressure, total_precipitation, 10m_u_component_of_wind,
10m_v_component_of_wind, surface_solar_radiation_downwards,
surface_thermal_radiation_downwards, total_cloud_cover.
total_cloud_cover (fraction, 0-1) isn't one of QUINCY's forcing columns,
but is confirmed available in this product (tested live 2026-09-05) and
kept as a cross-check on the radiation fields. NOTE: unlike a genuinely
unsupported variable name (which CDS rejects outright), a variable that's
merely incompatible with product_type "monthly_averaged_reanalysis" (e.g.
maximum/minimum 2m temperature -- ERA5 has no monthly tmax/tmin here) is
silently DROPPED from the response rather than erroring -- always check
the returned data_vars actually contain what you asked for.

COVERAGE: rolling, 1940 to near-present (typically a few months' lag) --
of everything in this toolkit, this is the most reliable way to reach
2024/2025. GSWP3-W5E5 stops at 2019 and CRU-JRA v3.0 at 2024 (see their
scripts' docstrings), so prefer ERA5 to close the final 2025 gap.

NOTE: double-check the request dict against the "Show API request" button
on the CDS dataset page before a large pull -- CDS occasionally renames
request keys across client versions.

UNIT FIX (2026-09-05): tp, ssrd, strd come back from CDS in their raw
accumulated form (tp in metres/day, ssrd/strd in J/m2/day), NOT already
normalized to the mm/day and W/m2 QUINCY expects. Confirmed empirically
by checking global-mean magnitudes against known physical ranges (a naive
14,233,794 for "W/m2" shortwave is obviously wrong; divided by seconds/day
it becomes ~165 W/m2, right where global mean downward shortwave should
be). write_outputs() below converts tp *1000 and ssrd/strd /86400.
Output files written before this fix are silently wrong by those same
factors -- regenerate them (raw chunks are cached, so this is a local
reprocessing step, no re-download needed).

CHUNKING: a single request spanning the full 1940-2025 record, globally,
for 9 variables is tens of GB and risks CDS request-size/timeout limits
and an unrecoverable all-or-nothing failure. This script instead submits
one CDS request per --chunk-years block (default 10y), caches each raw
chunk under <out-dir>/raw/ (skipped on re-run if already downloaded), and
concatenates all chunks together before writing final per-variable
outputs -- so a failed/interrupted run just resumes from the last
uncached chunk instead of starting over.

Usage:
  # a bounded, regional pull
  python download_era5_monthly.py --start-year 2020 --end-year 2025 \\
      --area 55 5 47 16
  # global, full record, chunked by decade (writes to
  # /Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/era5 by default;
  # pass --out-dir to override)
  python download_era5_monthly.py --start-year 1940 --end-year 2025
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import pandas as pd
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import (
    get_logger, specific_humidity_from_dewpoint, wind_speed_from_components,
    write_monthly_netcdf, year_chunks,
)

LOG = get_logger("era5-monthly")

DATASET_ID = "reanalysis-era5-single-levels-monthly-means"
DEFAULT_OUT_DIR = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/era5")

CDS_VARIABLES = [
    "2m_temperature", "2m_dewpoint_temperature", "surface_pressure",
    "total_precipitation", "10m_u_component_of_wind", "10m_v_component_of_wind",
    "surface_solar_radiation_downwards", "surface_thermal_radiation_downwards",
    "total_cloud_cover",
]


def get_client():
    try:
        import cdsapi
    except ImportError as e:
        raise SystemExit('The "cdsapi" package is required: pip install "cdsapi>=0.7.7"') from e
    return cdsapi.Client()


def download_chunk(client, start_year: int, end_year: int, area, grid, raw_path: Path) -> Path:
    if raw_path.exists():
        LOG.info(f"  already have chunk {raw_path.name}, skipping request")
        return raw_path

    request = {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": CDS_VARIABLES,
        "year": [str(y) for y in range(start_year, end_year + 1)],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "time": ["00:00"],
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
    if area:
        request["area"] = area  # [north, west, south, east]
    if grid:
        request["grid"] = grid  # e.g. "0.5/0.5" -- confirmed working live 2026-09-05

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    LOG.info(f"  submitting CDS request for {start_year}-{end_year}...")
    client.retrieve(DATASET_ID, request).download(str(raw_path))
    return raw_path


def _normalize_monthly_time(ds: xr.Dataset) -> xr.Dataset:
    """Rename the time dim to "time" and snap every timestamp to that
    month's first day.

    Needed because CDS's two stepType files disagree on time-of-day:
    instantaneous fields (t2m, d2m, sp, u10, v10) are stamped 00:00 UTC,
    accumulated fields (tp, ssrd, strd) 06:00 UTC (a longstanding ERA5
    quirk -- accumulated params are recorded against a forecast base
    time). Confirmed live 2026-09-05: merging the two files without this
    step doubles the time axis and leaves half of every variable NaN.
    """
    time_dim = "valid_time" if "valid_time" in ds.dims else "time"
    month_starts = pd.to_datetime(ds[time_dim].values).to_period("M").to_timestamp()
    ds = ds.assign_coords({time_dim: month_starts})
    if time_dim != "time":
        ds = ds.rename({time_dim: "time"})
    return ds


def _open_raw(raw_path: Path) -> xr.Dataset:
    """Open one chunk's CDS response, whether it's a plain NetCDF or (as
    observed live on 2026-09-05, despite requesting
    download_format="unarchived") a zip containing several NetCDFs --
    current CDS splits monthly-means requests by stepType, e.g.
    instantaneous fields (t2m, d2m, sp, u10, v10) land in one file and
    accumulated fields (tp, ssrd, strd) in another. Merge transparently
    either way.
    """
    if zipfile.is_zipfile(raw_path):
        extract_dir = raw_path.parent / f"{raw_path.stem}_extracted"
        with zipfile.ZipFile(raw_path) as zf:
            zf.extractall(extract_dir)
        parts = [_normalize_monthly_time(xr.open_dataset(p)) for p in sorted(extract_dir.glob("*.nc"))]
        ds = xr.merge(parts, compat="override")
    else:
        ds = _normalize_monthly_time(xr.open_dataset(raw_path))
    return ds


SECONDS_PER_DAY = 86400.0

def write_outputs(ds: xr.Dataset, out_dir: Path, start_year: int, end_year: int, tag: str = "") -> None:
    # Plain rename, no unit conversion needed.
    plain_rename = {"t2m": "t_air", "sp": "press_srf", "tcc": "cloud_cover"}
    for src, dst in plain_rename.items():
        if src in ds.data_vars:
            write_monthly_netcdf(ds[src], out_dir / f"era5_{dst}_{start_year}-{end_year}{tag}_monthly.nc", dst)
            LOG.info(f"  wrote {dst}")

    # tp arrives as metres/day (mean daily accumulation) -- QUINCY wants mm/day.
    if "tp" in ds.data_vars:
        precip = ds["tp"] * 1000.0
        precip.attrs["units"] = "mm day-1"
        write_monthly_netcdf(precip, out_dir / f"era5_precip_total_{start_year}-{end_year}{tag}_monthly.nc", "precip_total")
        LOG.info("  wrote precip_total (converted m/day -> mm/day)")

    # ssrd/strd arrive as J/m2 accumulated over the day (confirmed empirically
    # 2026-09-05: raw global means were ~1.4e7 and ~2.6e7, only physically
    # sane -- ~165 and ~300 W/m2 -- after dividing by seconds/day) rather
    # than an already-normalized W/m2 mean. Earlier versions of this script
    # wrote these un-converted; if you have output files from before this
    # fix, regenerate them (raw chunks are cached, no re-download needed).
    for src, dst in [("ssrd", "swvis_srf_down"), ("strd", "lw_srf_down")]:
        if src in ds.data_vars:
            flux = ds[src] / SECONDS_PER_DAY
            flux.attrs["units"] = "W m-2"
            write_monthly_netcdf(flux, out_dir / f"era5_{dst}_{start_year}-{end_year}{tag}_monthly.nc", dst)
            LOG.info(f"  wrote {dst} (converted J/m2/day -> W/m2)")

    if {"u10", "v10"}.issubset(ds.data_vars):
        speed = wind_speed_from_components(ds["u10"], ds["v10"])
        write_monthly_netcdf(speed, out_dir / f"era5_wind_air_{start_year}-{end_year}{tag}_monthly.nc", "wind_air")
        LOG.info("  wrote wind_air (derived from u10/v10)")

    if {"d2m", "sp"}.issubset(ds.data_vars):
        q = specific_humidity_from_dewpoint(ds["d2m"], ds["sp"])
        write_monthly_netcdf(q, out_dir / f"era5_q_air_{start_year}-{end_year}{tag}_monthly.nc", "q_air")
        LOG.info("  wrote q_air (derived from 2m dewpoint + surface pressure)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--area", type=float, nargs=4, metavar=("NORTH", "WEST", "SOUTH", "EAST"),
                         default=None, help="optional bounding box, omit for global")
    parser.add_argument("--grid", default=None,
                         help='optional target resolution, e.g. "0.5/0.5" to match CRU-JRA/'
                              'GSWP3-W5E5/WFDE5\'s native grid (confirmed working live 2026-09-05); '
                              "omit to keep ERA5's native 0.25 deg")
    parser.add_argument("--chunk-years", type=int, default=10,
                         help="years per CDS request (default: 10); smaller chunks are slower "
                              "overall but resume more cheaply after a failure")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                         help=f"default: {DEFAULT_OUT_DIR}")
    parser.add_argument("--raw-dir", type=Path, default=None)
    args = parser.parse_args()

    raw_dir = args.raw_dir or (args.out_dir / "raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    client = get_client()

    chunks = year_chunks(args.start_year, args.end_year, args.chunk_years)
    LOG.info(f"{len(chunks)} chunk(s): {chunks[0][0]}-{chunks[-1][1]}, {args.chunk_years}y each "
              f"({'global' if not args.area else args.area})")

    grid_tag = f"_grid{args.grid.replace('/', 'x')}" if args.grid else ""
    # dataset/monthly/spatial_resolution/ layout -- resolution now lives in
    # the directory, not the filename, so the grid_tag above is only used
    # for the raw chunk cache (which stays flat) not the final outputs.
    res_label = f"{args.grid.split('/')[0]}deg" if args.grid else "0.25deg"
    out_subdir = args.out_dir / "monthly" / res_label
    out_subdir.mkdir(parents=True, exist_ok=True)

    datasets = []
    for i, (c_start, c_end) in enumerate(chunks, 1):
        LOG.info(f"Chunk {i}/{len(chunks)}: {c_start}-{c_end}")
        raw_path = raw_dir / f"era5_monthly_means_{c_start}-{c_end}{grid_tag}.nc"
        download_chunk(client, c_start, c_end, args.area, args.grid, raw_path)
        datasets.append(_open_raw(raw_path))

    LOG.info("Concatenating all chunks and writing final outputs...")
    full = xr.concat(datasets, dim="time").sortby("time")
    write_outputs(full, out_subdir, args.start_year, args.end_year)

    for d in datasets:
        d.close()

    LOG.info(f"Done. {args.start_year}-{args.end_year} written to {out_subdir}")


if __name__ == "__main__":
    main()
