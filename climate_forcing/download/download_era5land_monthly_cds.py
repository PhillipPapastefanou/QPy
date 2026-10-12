#!/usr/bin/env python3
"""
Download ERA5-Land monthly means (Copernicus CDS dataset
reanalysis-era5-land-monthly-means) at native 0.1deg, one raw file per
request, cached and skipped on rerun.

Why, alongside the BGC shared daily archive used by
conversion/build_era5land_monthly.py:
  - longwave: the archive only has strd from 2000 (and with an unexplained
    3-9% offset against ERA5), so the full-record ERA5-Land longwave comes
    from here, to compare with / replace the ERA5 longwave used so far;
  - 2025: the archive has no 2025 ssrd or d2m, and its 2025 sp went through
    the daily-maximum aggregation, so 2025 shortwave, dewpoint and pressure
    come from here as monthly means.

Accumulated fields (ssrd, strd) in this product are mean daily accumulations
(J m-2 per day), like ERA5's monthly means -- divide by 86400 for W m-2.
The native grid is a point grid, latitude 90..-90 (1801 rows).

Usage:
  python download_era5land_monthly_cds.py --start-year 1950 --end-year 2025 \\
      --variables surface_thermal_radiation_downwards --chunk-years 5
  python download_era5land_monthly_cds.py --start-year 2024 --end-year 2025 \\
      --variables surface_solar_radiation_downwards 2m_dewpoint_temperature surface_pressure
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_logger, year_chunks

LOG = get_logger("era5land-cds-monthly")

DATASET_ID = "reanalysis-era5-land-monthly-means"
DEFAULT_RAW_DIR = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/era5_land/cds_monthly/raw")

# CDS request name -> short name in the returned NetCDF
SHORT_NAMES = {
    "surface_thermal_radiation_downwards": "strd",
    "surface_solar_radiation_downwards": "ssrd",
    "2m_dewpoint_temperature": "d2m",
    "surface_pressure": "sp",
}


def raw_path(raw_dir: Path, start: int, end: int, variables: list[str]) -> Path:
    tag = "-".join(SHORT_NAMES.get(v, v) for v in variables)
    return raw_dir / f"era5land_monthly_means_{tag}_{start}-{end}.nc"


def download_chunk(client, start: int, end: int, variables: list[str], path: Path) -> None:
    if path.exists():
        LOG.info(f"  already have {path.name}, skipping")
        return
    request = {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": variables,
        "year": [str(y) for y in range(start, end + 1)],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "time": ["00:00"],
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
    part = path.with_name(path.name + ".part")
    LOG.info(f"  submitting CDS request {variables} {start}-{end}...")
    client.retrieve(DATASET_ID, request).download(str(part))
    part.rename(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start-year", type=int, required=True)
    ap.add_argument("--end-year", type=int, required=True)
    ap.add_argument("--variables", nargs="+", required=True, choices=list(SHORT_NAMES))
    ap.add_argument("--chunk-years", type=int, default=5)
    ap.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    args = ap.parse_args()

    import cdsapi
    client = cdsapi.Client()
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    chunks = year_chunks(args.start_year, args.end_year, args.chunk_years)
    for i, (start, end) in enumerate(chunks, 1):
        LOG.info(f"Chunk {i}/{len(chunks)}: {start}-{end}")
        download_chunk(client, start, end, args.variables, raw_path(args.raw_dir, start, end, args.variables))
    LOG.info("Done.")


if __name__ == "__main__":
    main()
