#!/usr/bin/env python3
"""
Download GSWP3-W5E5 (ISIMIP3a InputData climate forcing) for a point or
small bounding box, and aggregate to monthly NetCDF.

GSWP3-W5E5 is the ISIMIP-community-standard forcing: GSWP3 for 1901-1978
homogenized onto W5E5 (bias-adjusted ERA5) for 1979-2019. It is a good
drop-in alternative/cross-check for CRU-JRA (see README.md), and unlike
CRU-JRA it ships rain/snow already split (pr vs prsn).

Access: via the official `isimip-client` package (PyPI, published by
PIK/ISIMIP: https://pypi.org/project/isimip-client/), confirmed available
2026-09-05. No authentication needed for InputData. The client's
`select_point`/`select_bbox` server-side cutout means you only download
the small region you need, not the global daily file.

  pip install isimip-client

Variables (ISIMIP3a obsclim, daily, 0.5deg): tas, tasmin, tasmax, huss,
hurs, ps, sfcWind, pr, prsn, rlds, rsds.

COVERAGE: ISIMIP3a obsclim spans 1901-2019 -- it does NOT reach 2024/2025
(ISIMIP rounds are fixed historical products, not rolling updates). For
recent years use download_era5_monthly.py or download_wfde5_monthly.py
instead, or combine this with one of those for the post-2019 gap.

Usage (single site, matches QuincyInputGenerator's lon/lat convention):
  python download_gswp3_w5e5.py --lon 10.472944 --lat 51.080587 \\
      --variables tas huss ps sfcWind pr prsn rlds rsds \\
      --start-year 2010 --end-year 2019 --out-dir ./data/gswp3-w5e5
"""
from __future__ import annotations

import argparse
import sys
import time
import zipfile
from pathlib import Path

import requests
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_logger, resample_monthly, write_monthly_netcdf, default_output_root

LOG = get_logger("gswp3-w5e5")

CLIMATE_FORCING = "gswp3-w5e5"
SIMULATION_ROUND = "ISIMIP3a"
SCENARIO = "obsclim"

ALL_VARIABLES = ["tas", "tasmin", "tasmax", "huss", "hurs", "ps", "sfcWind", "pr", "prsn", "rlds", "rsds"]

# state variables -> monthly mean; accumulated depths (pr, prsn) -> monthly sum
AGGREGATION = {v: "mean" for v in ALL_VARIABLES}
AGGREGATION.update({"pr": "sum", "prsn": "sum"})


def get_client():
    try:
        from isimip_client.client import ISIMIPClient
    except ImportError as e:
        raise SystemExit(
            "The 'isimip-client' package is required: pip install isimip-client"
        ) from e
    return ISIMIPClient()


def find_dataset_paths(client, var: str, start_year: int, end_year: int) -> list[str]:
    # NOTE: client.datasets() returns a plain list of dataset dicts, not a
    # {"results": [...]} envelope -- confirmed live 2026-09-05 against
    # isimip-client 2.0.2, contradicting the PyPI README's example (which
    # shows a paginated dict). Handle both shapes defensively in case this
    # changes again between client versions.
    resp = client.datasets(
        simulation_round=SIMULATION_ROUND,
        product="InputData",
        climate_forcing=CLIMATE_FORCING,
        climate_scenario=SCENARIO,
        climate_variable=var,
        page_size=100,
    )
    results = resp if isinstance(resp, list) else resp.get("results", [])
    paths = []
    for dataset in results:
        for f in dataset.get("files", []):
            name = f.get("name", "")
            # GSWP3-W5E5 files are chunked by decade-ish ranges in the name,
            # e.g. ..._obsclim_tas_global_daily_1971_1980.nc -- keep any
            # file whose name overlaps the requested year range.
            if any(str(y) in name for y in range(start_year, end_year + 1)):
                paths.append(f["path"])
    if not paths:
        LOG.warning(f"  no file paths matched years {start_year}-{end_year} for '{var}', "
                     f"grabbing full path list instead (server-side cutout will still work)")
        paths = [f["path"] for d in resp.get("results", []) for f in d.get("files", [])]
    return paths


def download_point(client, paths: list[str], lon: float, lat: float, out_dir: Path, var: str) -> Path:
    LOG.info(f"  requesting server-side point cutout for '{var}' ({len(paths)} source file(s))")
    response = client.select_point(paths, lat=lat, lon=lon, poll=10)

    # isimip-client polls until the cutout job is finished and the response
    # contains a "file_url" pointing at a small netcdf/zip download.
    file_url = response.get("file_url") or response.get("download_url")
    if not file_url:
        raise RuntimeError(f"Unexpected ISIMIP cutout response: {response}")

    out_dir.mkdir(parents=True, exist_ok=True)
    local_path = out_dir / Path(file_url).name
    LOG.info(f"  downloading cutout: {file_url}")
    with requests.get(file_url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)

    if local_path.suffix == ".zip":
        extract_dir = out_dir / local_path.stem
        with zipfile.ZipFile(local_path) as zf:
            zf.extractall(extract_dir)
        ncs = sorted(extract_dir.glob("*.nc"))
        if not ncs:
            raise RuntimeError(f"No .nc file found in {local_path}")
        return ncs[0]

    return local_path


def process_variable(client, var: str, lon: float, lat: float, start_year: int, end_year: int,
                      raw_dir: Path, out_dir: Path) -> None:
    LOG.info(f"Processing variable '{var}'")
    paths = find_dataset_paths(client, var, start_year, end_year)
    if not paths:
        LOG.warning(f"  no ISIMIP dataset found for '{var}', skipping")
        return

    nc_path = download_point(client, paths, lon, lat, raw_dir / var, var)
    ds = xr.open_dataset(nc_path)
    data_var = var if var in ds.data_vars else list(ds.data_vars)[0]
    da = ds[data_var].sel(time=slice(f"{start_year}-01-01", f"{end_year}-12-31"))

    how = AGGREGATION.get(var, "mean")
    monthly = resample_monthly(da, how=how)

    # dataset/time_resolution/spatial_resolution/ layout -- GSWP3-W5E5 is
    # native 0.5deg (ISIMIP3a daily product), aggregated to monthly here.
    out_subdir = out_dir / "monthly" / "0.5deg"
    out_subdir.mkdir(parents=True, exist_ok=True)
    out_path = out_subdir / f"gswp3-w5e5_{var}_{start_year}-{end_year}_monthly.nc"
    write_monthly_netcdf(monthly, out_path, var)
    LOG.info(f"  wrote {out_path}")
    ds.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--variables", nargs="+", default=ALL_VARIABLES)
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, default=default_output_root() / "gswp3-w5e5")
    parser.add_argument("--raw-dir", type=Path, default=None)
    args = parser.parse_args()

    raw_dir = args.raw_dir or (args.out_dir / "raw")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    client = get_client()
    for var in args.variables:
        process_variable(client, var, args.lon, args.lat, args.start_year, args.end_year, raw_dir, args.out_dir)
        time.sleep(1)  # be polite to the cutout service between requests


if __name__ == "__main__":
    main()
