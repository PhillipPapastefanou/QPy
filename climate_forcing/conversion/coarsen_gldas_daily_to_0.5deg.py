#!/usr/bin/env python3
"""
Coarsen GLDAS's native 0.25deg daily forcing variables (2018-2025) down to
0.5deg -- pure local reprocessing of download_gldas.py's already-downloaded
daily/0.25deg/ output, no new downloads.

Why this exists: download_gldas.py's process_daily() (the daily_0.25deg
product) only ever writes at native 0.25deg -- unlike its monthly product,
which already writes both 0.25deg and 0.5deg (coarsen_to_half_degree(),
confirmed live: gldas_t_air_2000-2025_monthly.nc etc. already cover the
full record at 0.5deg). The new 2018-2025 *daily* files
(t_air/q_air/press_srf/wind_air/swvis_srf_down/lw_srf_down/rain/snow) never
got that treatment, so they're the only GLDAS product left at native
resolution rather than the 0.5deg grid ERA5/CRU-JRA/TerraClimate's final
products all share.

Method: exact 2x2 block-mean, same as download_gldas.py's own
coarsen_to_half_degree() (kept as a local copy rather than a cross-script
import since download/ and conversion/ aren't packages here, matching
derive_gldas_tmin_tmax.py's precedent) -- GLDAS's 600x1440 0.25deg grid
divides evenly into 300x720 at 0.5deg, no interpolation/trim needed. Naive
(not area-weighted) grid-cell averaging, same known simplification as
elsewhere in this toolkit.

Each variable is read with dask chunking and coarsened/written lazily
(chunk-by-chunk, not loaded whole into memory) -- confirmed live 2026-09-09
each native file is ~10GB uncompressed (2922 daily steps x 600x1440 float32),
so eagerly loading all 8 variables at once would be unnecessary memory
pressure for a straightforward block-mean.

Usage:
  cd conversion
  python coarsen_gldas_daily_to_0.5deg.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_logger

LOG = get_logger("gldas-daily-coarsen")

DEFAULT_IN_DIR = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/gldas/daily/0.25deg")
DEFAULT_OUT_DIR = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/gldas/daily/0.5deg")
ALL_VARS = ["t_air", "q_air", "press_srf", "wind_air", "swvis_srf_down", "lw_srf_down", "rain", "snow"]


def coarsen_to_half_degree(da: xr.DataArray) -> xr.DataArray:
    """Exact 2x2 block-mean: GLDAS's 600x1440 0.25deg grid divides evenly
    into 300x720 at 0.5deg (same method as download_gldas.py's own
    coarsen_to_half_degree() and derive_gldas_tmin_tmax.py's local copy).
    """
    coarse = da.coarsen(lat=2, lon=2, boundary="exact").mean()
    coarse.attrs = dict(da.attrs)
    return coarse


def process(in_dir: Path, out_dir: Path, variables: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for var in variables:
        matches = sorted(in_dir.glob(f"gldas_{var}_*_daily.nc"))
        if not matches:
            LOG.warning(f"  no gldas_{var}_*_daily.nc found under {in_dir}, skipping")
            continue
        src = matches[-1]
        out_path = out_dir / src.name
        if out_path.exists():
            LOG.info(f"  already have {out_path.name}, skipping")
            continue

        LOG.info(f"  coarsening {var} ({src.name})...")
        ds = xr.open_dataset(src, chunks={"time": 366})
        coarse = coarsen_to_half_degree(ds[var])
        coarse.to_dataset(name=var).to_netcdf(out_path, encoding={var: {"zlib": True, "complevel": 4}})
        ds.close()
        LOG.info(f"  wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--in-dir", type=Path, default=DEFAULT_IN_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--variables", nargs="+", choices=ALL_VARS, default=None,
                         help=f"Subset of {ALL_VARS} to coarsen (default: all)")
    args = parser.parse_args()

    process(args.in_dir, args.out_dir, args.variables or ALL_VARS)
    LOG.info("Done.")


if __name__ == "__main__":
    main()
