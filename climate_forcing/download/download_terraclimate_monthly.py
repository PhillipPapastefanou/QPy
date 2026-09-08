#!/usr/bin/env python3
"""
Download TerraClimate -- already monthly, direct HTTP, no account needed.

Verified live on 2026-09-05:
  http://thredds.northwestknowledge.net:8080/thredds/fileServer/TERRACLIMATE_ALL/data/TerraClimate_{var}_{year}.nc
returns 200 with Content-Type: application/x-netcdf, no auth required.
Variable codes confirmed from the public catalog page (climatologylab.org):
  aet, def, pet, ppt, q, soil, srad, swe, tmax, tmin, vap, vpd, ws, PDSI.

IMPORTANT LIMITATIONS for QUINCY use (see README.md comparison table):
  - No downwelling longwave radiation at all.
  - No surface pressure.
  - Precipitation (ppt) is a monthly total with no rain/snow split; "swe"
    is a snow-water-equivalent *storage*, not a snowfall flux.
  - No specific/relative humidity directly -- "vap" is actual vapour
    pressure (kPa). No pressure field either, but see
    conversion/derive_terraclimate_humidity_pressure.py: an elevation-based
    standard-atmosphere approximation (--with-dem below) is enough to
    derive both press_srf and q_air from "vap" without borrowing pressure
    from another dataset. Climatological, not synoptic -- see that
    script's docstring.
  - No wet-day counts (unlike CRU-JRA's precip-derived wetdays).
That makes TerraClimate useful for a quick gap-fill or a temperature/
precip/radiation sanity check, but NOT a self-sufficient substitute for
CRU-JRA/GSWP3-W5E5 as full QUINCY forcing.

Each file is one variable, one year, global, already at monthly
resolution (12 time steps) -- this script just concatenates years, no
resampling needed.

COVERAGE: confirmed live on 2026-09-05 -- yearly files exist through 2025
(TerraClimate is updated annually and is currently the most current
dataset in this toolkit alongside ERA5).

Usage:
  python download_terraclimate_monthly.py --variables tmax tmin ppt srad ws vap \\
      --start-year 2015 --end-year 2025 --out-dir ./data/terraclimate
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_logger, open_dataset_verified, retry_request, write_monthly_netcdf

LOG = get_logger("terraclimate")

BASE_URL = "http://thredds.northwestknowledge.net:8080/thredds/fileServer/TERRACLIMATE_ALL/data"
DEM_URL = "http://thredds.northwestknowledge.net:8080/thredds/fileServer/TERRACLIMATE_ALL/layers/terraclim_dem.nc"
DEFAULT_OUT_DIR = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/terraclimate")
ALL_VARIABLES = ["aet", "def", "pet", "ppt", "q", "soil", "srad", "swe", "tmax", "tmin", "vap", "vpd", "ws", "PDSI"]


def download_dem(raw_dir: Path) -> Path:
    """TerraClimate's own static elevation layer, on the exact same 1/24deg
    grid as every yearly variable file -- confirmed live 2026-09-07 via the
    THREDDS catalog (layers/terraclim_dem.nc). Used by
    conversion/derive_terraclimate_humidity_pressure.py to approximate
    surface pressure (TerraClimate has no pressure variable of its own),
    which in turn lets specific humidity be derived from "vap". One static
    149 MB file, not per-year -- cached once under raw/ancillary/.
    """
    dest = raw_dir / "ancillary" / "terraclim_dem.nc"
    if dest.exists():
        LOG.info(f"  already have {dest.name}, skipping download")
        return dest
    LOG.info(f"  downloading {DEM_URL}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _fetch():
        with requests.get(DEM_URL, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)

    retry_request(_fetch, LOG)
    return dest


def download_year(var: str, year: int, dest: Path) -> Path:
    if dest.exists():
        LOG.info(f"  already have {dest.name}, skipping download")
        return dest
    url = f"{BASE_URL}/TerraClimate_{var}_{year}.nc"
    LOG.info(f"  downloading {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _fetch():
        with requests.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)

    retry_request(_fetch, LOG)
    return dest


def download_year_verified(var: str, year: int, dest: Path) -> Path:
    """download_year(), but also confirms the cached/downloaded file
    actually opens before trusting it -- a bare `if dest.exists(): skip`
    silently trusted a truncated file from an earlier killed process on
    2026-09-06 (TerraClimate_tmin_1974.nc, 71MB of an expected ~92MB),
    which only surfaced as a crash much later inside open_mfdataset.
    """
    download_year(var, year, dest)
    ds = open_dataset_verified(dest, lambda: download_year(var, year, dest), LOG)
    ds.close()
    return dest


def process_variable(var: str, years: list[int], raw_dir: Path, out_dir: Path) -> None:
    LOG.info(f"Processing variable '{var}'")

    start, end = years[0], years[-1]
    # dataset/time_resolution/spatial_resolution/ layout -- TerraClimate is
    # native 1/24deg (~4km, confirmed from file coords).
    out_subdir = out_dir / "monthly" / "4km"
    out_path = out_subdir / f"terraclimate_{var}_{start}-{end}_monthly.nc"
    if out_path.exists():
        LOG.info(f"  already have {out_path.name}, skipping")
        return

    # TerraClimate is full native resolution (4320x8640) -- concatenating
    # all requested years in memory before writing tries to allocate ~3 GB
    # PER YEAR (confirmed to OOM in practice at 68 years: 227 GiB request,
    # 2026-09-05). A first attempt at fixing this with plain xarray
    # to_netcdf(mode="a") per year silently failed -- verified live: it
    # clobbers the previous year instead of extending the time dimension
    # (3 years in -> 1 year's worth out). Using dask via open_mfdataset lets
    # xarray write the concatenated dataset to disk in chunks instead,
    # which is the standard, actually-correct tool for this.
    nc_paths = []
    for year in years:
        nc_path = raw_dir / var / f"TerraClimate_{var}_{year}.nc"
        download_year_verified(var, year, nc_path)
        nc_paths.append(nc_path)

    # chunks={"time": 12} aligns dask chunks to whole source files (one
    # year each) instead of one timestep at a time -- chunks={"time": 1}
    # was measured live at ~4.3 min to process 3 already-cached years
    # (pure overhead, no download), which would be ~1 day for the full
    # 68-year record per variable.
    ds = xr.open_mfdataset(nc_paths, combine="nested", concat_dim="time", chunks={"time": 12})
    data_var = var if var in ds.data_vars else list(ds.data_vars)[0]
    out_subdir.mkdir(parents=True, exist_ok=True)
    ds[[data_var]].to_netcdf(out_path, encoding={data_var: {"zlib": True, "complevel": 4}})
    ds.close()

    LOG.info(f"  wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variables", nargs="+", default=["tmax", "tmin", "ppt", "srad", "ws", "vap"])
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                         help=f"default: {DEFAULT_OUT_DIR}")
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--with-dem", action="store_true",
                         help="also fetch the static elevation layer used to derive surface "
                              "pressure / specific humidity (see conversion/"
                              "derive_terraclimate_humidity_pressure.py)")
    args = parser.parse_args()

    bad = set(args.variables) - set(ALL_VARIABLES)
    if bad:
        raise SystemExit(f"Unknown TerraClimate variables: {sorted(bad)}. Valid: {ALL_VARIABLES}")

    years = list(range(args.start_year, args.end_year + 1))
    raw_dir = args.raw_dir or (args.out_dir / "raw")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for var in args.variables:
        process_variable(var, years, raw_dir, args.out_dir)

    if args.with_dem:
        download_dem(raw_dir)


if __name__ == "__main__":
    main()
