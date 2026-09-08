#!/usr/bin/env python3
"""
Download WFDE5 (bias-adjusted ERA5, via Copernicus CDS) and aggregate to
monthly NetCDF.

WFDE5 is the one dataset in this toolkit that provides rain and snow as
*separate* fluxes natively (rainfall_flux / snowfall_flux) instead of
requiring a temperature-threshold split -- worth it specifically for the
QUINCY "rain"/"snow" columns. The CDS "derived-near-surface-meteorological
-variables" product (the actively maintained WFDE5 successor/extension)
states coverage "from 1979 to 2024" (checked 2026-09-05) -- so, unlike
plain GSWP3-W5E5 (to 2019) or CRU-JRA v2.5 (to 2023), this one does reach
2024, matching CRU-JRA v3.0;
it is on the same 0.5deg ERA5-derived grid as CRU-JRA, so it adds little
independent information for cross-checks, and for 2025 you still need
download_era5_monthly.py.

Access: same `cdsapi` setup as download_era5_monthly.py. Dataset id:
derived-near-surface-meteorological-variables.

STATUS: the variable *names* below (near_surface_air_temperature,
near_surface_specific_humidity, near_surface_wind_speed,
surface_downwelling_shortwave_radiation, surface_downwelling_longwave_radiation,
surface_air_pressure, rainfall_flux, snowfall_flux) were confirmed present
on the live CDS dataset page on 2026-09-05. The exact request dict (whether
it needs "reference_dataset": "cru", a "time_aggregation" key, etc.) was
NOT confirmed against a live example -- use the "Show API request" button
on the CDS dataset page to fill in/adjust REQUEST_EXTRA below before a
real pull.

Usage:
  python download_wfde5_monthly.py --start-year 2018 --end-year 2024 \\
      --area 55 5 47 16 --out-dir ./data/wfde5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_logger, resample_monthly, write_monthly_netcdf, default_output_root

LOG = get_logger("wfde5-monthly")

DATASET_ID = "derived-near-surface-meteorological-variables"

VARIABLES = {
    "near_surface_air_temperature": ("t_air", "mean"),
    "near_surface_specific_humidity": ("q_air", "mean"),
    "surface_air_pressure": ("press_srf", "mean"),
    "near_surface_wind_speed": ("wind_air", "mean"),
    "surface_downwelling_shortwave_radiation": ("swvis_srf_down", "mean"),
    "surface_downwelling_longwave_radiation": ("lw_srf_down", "mean"),
    "rainfall_flux": ("rain", "mean"),
    "snowfall_flux": ("snow", "mean"),
}

# See STATUS note above -- adjust once verified against the CDS page.
REQUEST_EXTRA = {
    "reference_dataset": "cru",
}


def get_client():
    try:
        import cdsapi
    except ImportError as e:
        raise SystemExit('The "cdsapi" package is required: pip install "cdsapi>=0.7.7"') from e
    return cdsapi.Client()


def download_variable(client, cds_var: str, start_year: int, end_year: int, area, raw_path: Path) -> Path:
    if raw_path.exists():
        LOG.info(f"  already have {raw_path.name}, skipping request")
        return raw_path

    request = {
        "variable": cds_var,
        "year": [str(y) for y in range(start_year, end_year + 1)],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "format": "netcdf",
        **REQUEST_EXTRA,
    }
    if area:
        request["area"] = area

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    LOG.info(f"  requesting '{cds_var}' {start_year}-{end_year}...")
    client.retrieve(DATASET_ID, request).download(str(raw_path))
    return raw_path


def process(client, cds_var: str, out_name: str, how: str, start_year: int, end_year: int,
            area, raw_dir: Path, out_dir: Path) -> None:
    LOG.info(f"Processing '{cds_var}' -> {out_name}")
    raw_path = raw_dir / f"wfde5_{cds_var}_{start_year}-{end_year}.nc"
    download_variable(client, cds_var, start_year, end_year, area, raw_path)

    ds = xr.open_dataset(raw_path)
    data_var = list(ds.data_vars)[0]
    monthly = resample_monthly(ds[data_var], how=how) if "time" in ds[data_var].dims else ds[data_var]

    out_path = out_dir / f"wfde5_{out_name}_{start_year}-{end_year}_monthly.nc"
    write_monthly_netcdf(monthly, out_path, out_name)
    LOG.info(f"  wrote {out_path}")
    ds.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variables", nargs="+", default=list(VARIABLES.keys()))
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--area", type=float, nargs=4, metavar=("NORTH", "WEST", "SOUTH", "EAST"), default=None)
    parser.add_argument("--out-dir", type=Path, default=default_output_root() / "wfde5")
    parser.add_argument("--raw-dir", type=Path, default=None)
    args = parser.parse_args()

    raw_dir = args.raw_dir or (args.out_dir / "raw")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    client = get_client()
    for cds_var in args.variables:
        out_name, how = VARIABLES[cds_var]
        process(client, cds_var, out_name, how, args.start_year, args.end_year, args.area, raw_dir, args.out_dir)


if __name__ == "__main__":
    main()
