#!/usr/bin/env python3
"""
Download GLDAS Noah v2.1 (NASA GES DISC) -- unlike every other dataset in
this toolkit, GLDAS's native forcing fields map almost 1:1 onto QUINCY's
variable set, including a genuine rain/snow split (Rainf_tavg/Snowf_tavg,
the Noah LSM's own partition) -- neither ERA5 nor CRU-JRA provide that
natively. Confirmed live 2026-09-06 against a real downloaded file:

    Tair_f_inst    K            -> t_air
    Qair_f_inst    kg kg-1      -> q_air
    Psurf_f_inst   Pa           -> press_srf
    Wind_f_inst    m s-1        -> wind_air
    SWdown_f_tavg  W m-2        -> swvis_srf_down
    LWdown_f_tavg  W m-2        -> lw_srf_down
    Rainf_tavg     kg m-2 s-1   -> rain   (*86400 -> mm/day)
    Snowf_tavg     kg m-2 s-1   -> snow   (*86400 -> mm/day)

Two source products, both native 0.25deg (confirmed: 600 lat x 1440 lon,
0.25deg spacing, -59.875..89.875 lat -- GLDAS Noah excludes Antarctica):
  - GLDAS_NOAH025_M.2.1   monthly, already time-averaged, one file/month.
  - GLDAS_NOAH025_3H.2.1  3-hourly instantaneous/tavg, one file per 3h
    (8 files/day) -- resampled here to daily.

There is no native 0.5deg GLDAS product. The monthly 0.5deg output here is
derived locally via exact 2x2 block-averaging of the monthly 0.25deg grid
(600/2=300, 1440/2=720 -- divides evenly, no interpolation/trim needed).
This is naive grid-cell averaging, not area-weighted (same known
simplification as elsewhere in this toolkit -- see README.md Sec 7).

COVERAGE: GLDAS-2.1 is operationally live -- confirmed live 2026-09-06 the
main (GPCP-gated) production stream reaches 2026-05-31 (~3 month lag); the
Early Product stream (GLDAS_NOAH025_3H_EP / GLDAS_NOAH025_M_EP) is more
current (~1.5 month lag) but wasn't checked here. This toolkit caps GLDAS
at end-2025 to match CRU-JRA/TerraClimate's existing end year -- pass
--end-year 2026 yourself if you want to chase the partial year.

ACCESS: requires a free NASA Earthdata Login account
(https://urs.earthdata.nasa.gov/) with the "NASA GESDISC DATA ARCHIVE"
application approved under Profile > Applications > Authorized Apps (a
GLDAS/GES-DISC-specific extra step -- confirmed live 2026-09-06 that an
unauthenticated request gets "HTTP Basic: Access denied." even though the
directory *listing* is public). Generate a bearer token at
https://urs.earthdata.nasa.gov/profile ("Generate Token") and:

    export EARTHDATA_TOKEN=...

SIZE WARNING (daily): the 3-hourly source is 8 files/day, ~19MB each, so a
global multi-year daily pull is large and slow -- roughly 1.4GB/year raw
per variable-group just for the download, before processing. Start with a
short --start-year/--end-year test before committing to the full record.

Usage:
  export EARTHDATA_TOKEN=...
  # monthly, both resolutions, global, matching CRU-JRA/TerraClimate's 2025 cutoff
  python download_gldas.py --products monthly_0.25deg monthly_0.5deg \\
      --start-year 2000 --end-year 2025
  # daily 0.25deg -- start small
  python download_gldas.py --products daily_0.25deg --start-year 2023 --end-year 2025
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

import requests
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import env_or_none, get_logger, write_monthly_netcdf

LOG = get_logger("gldas")

DEFAULT_OUT_DIR = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/gldas")
BASE_URL = "https://hydro1.gesdisc.eosdis.nasa.gov/data/GLDAS"
MONTHLY_COLLECTION = "GLDAS_NOAH025_M.2.1"
THREEHOURLY_COLLECTION = "GLDAS_NOAH025_3H.2.1"

SECONDS_PER_DAY = 86400.0

# GLDAS variable -> (QUINCY name, unit conversion)
RATE_VARS = {"Rainf_tavg": "rain", "Snowf_tavg": "snow"}  # kg m-2 s-1 -> mm/day (*86400)
PLAIN_VARS = {
    "Tair_f_inst": "t_air", "Qair_f_inst": "q_air", "Psurf_f_inst": "press_srf",
    "Wind_f_inst": "wind_air", "SWdown_f_tavg": "swvis_srf_down", "LWdown_f_tavg": "lw_srf_down",
}
ALL_SOURCE_VARS = list(PLAIN_VARS) + list(RATE_VARS)


def get_token() -> str:
    token = env_or_none("EARTHDATA_TOKEN")
    if not token:
        raise SystemExit(
            "No Earthdata token found. Set EARTHDATA_TOKEN (generate one at "
            "https://urs.earthdata.nasa.gov/profile), and make sure the 'NASA "
            "GESDISC DATA ARCHIVE' app is approved under your Earthdata profile's "
            "Authorized Apps."
        )
    return token


def download_file(url: str, dest: Path, token: str) -> Path:
    """Confirmed live 2026-09-06: this environment's outbound network goes
    through a proxy (195.37.229.6:3128) that occasionally stalls a
    connection mid-transfer or returns a transient 401 -- observed on a
    request that succeeded moments before and after on the same token, so
    it wasn't a real auth failure. retry_request() normally treats 4xx as
    permanent (correct for CRU-JRA's real credential errors), but that
    assumption doesn't hold for this proxy's flakiness, so 401 is retried
    here too, capped so a genuinely expired/revoked token still fails
    within a bounded number of attempts rather than retrying forever.
    """
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    def _fetch():
        try:
            resp = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                                 stream=True, timeout=(30, 120))
            resp.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    for attempt in range(1, 4):
        try:
            _fetch()
            break
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 401 and attempt < 3:
                LOG.warning(f"  401 on {url} (attempt {attempt}/3, likely proxy flakiness -- "
                            f"retrying, same token worked on surrounding files), retrying in 15s")
                time.sleep(15)
                continue
            raise
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < 3:
                LOG.warning(f"  connection issue on {url} ({e}), retrying in 15s (attempt {attempt}/3)")
                time.sleep(15)
                continue
            raise

    tmp.rename(dest)
    return dest


def rename_to_quincy(ds: xr.Dataset) -> xr.Dataset:
    out = {}
    for src, dst in PLAIN_VARS.items():
        if src in ds.data_vars:
            out[dst] = ds[src]
    for src, dst in RATE_VARS.items():
        if src in ds.data_vars:
            flux = ds[src] * SECONDS_PER_DAY
            flux.attrs["units"] = "mm day-1"
            out[dst] = flux
    return xr.Dataset(out)


def coarsen_to_half_degree(ds: xr.Dataset) -> xr.Dataset:
    """Exact 2x2 block-mean: GLDAS's 600x1440 0.25deg grid divides evenly
    into 300x720 at 0.5deg -- confirmed live 2026-09-06 (no trim/pad needed).
    Naive (not area-weighted) grid-cell averaging -- see module docstring.
    """
    coarse = ds.coarsen(lat=2, lon=2, boundary="exact").mean()
    for name, da in coarse.data_vars.items():
        da.attrs = dict(ds[name].attrs)
    return coarse


def process_monthly(start_year: int, end_year: int, out_dir: Path, raw_dir: Path,
                     token: str, want_0p25: bool, want_0p5: bool) -> None:
    LOG.info(f"Monthly: downloading {start_year}-{end_year}...")
    monthly_parts = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            if year == dt.date.today().year and month > dt.date.today().month:
                continue
            fname = f"GLDAS_NOAH025_M.A{year}{month:02d}.021.nc4"
            url = f"{BASE_URL}/{MONTHLY_COLLECTION}/{year}/{fname}"
            dest = raw_dir / "monthly" / fname
            try:
                download_file(url, dest, token)
            except requests.HTTPError as e:
                LOG.warning(f"  skip {year}-{month:02d}: {e}")
                continue
            ds = xr.open_dataset(dest)
            monthly_parts.append(rename_to_quincy(ds).load())
            ds.close()
        LOG.info(f"  year {year} done")

    full = xr.concat(monthly_parts, dim="time").sortby("time")

    if want_0p25:
        out_subdir = out_dir / "monthly" / "0.25deg"
        for var in full.data_vars:
            write_monthly_netcdf(full[var], out_subdir / f"gldas_{var}_{start_year}-{end_year}_monthly.nc", var)
        LOG.info(f"  wrote 0.25deg monthly outputs to {out_subdir}")

    if want_0p5:
        coarse = coarsen_to_half_degree(full)
        out_subdir = out_dir / "monthly" / "0.5deg"
        for var in coarse.data_vars:
            write_monthly_netcdf(coarse[var], out_subdir / f"gldas_{var}_{start_year}-{end_year}_monthly.nc", var)
        LOG.info(f"  wrote 0.5deg monthly outputs to {out_subdir}")


THREEHOURLY_STAMPS = ["0000", "0300", "0600", "0900", "1200", "1500", "1800", "2100"]


def process_daily(start_year: int, end_year: int, out_dir: Path, raw_dir: Path, token: str) -> None:
    """Builds one intermediate yearly file per year first (small: ~366
    daily-mean timesteps, a few GB at most), then concatenates years via
    dask-backed open_mfdataset + a single chunked to_netcdf write. Mirrors
    the fix already applied to download_terraclimate_monthly.py -- holding
    every requested year's daily means in one Python list before a single
    final concat was confirmed live to blow up memory at that dataset's
    scale (227 GiB for 68 years of native-resolution TerraClimate); this
    dataset is much smaller per-timestep (600x1440 vs TerraClimate's
    4320x8640) but the same unbounded-accumulation pattern is still wrong
    in principle for an open-ended --start-year/--end-year range, so it's
    avoided here from the start rather than fixed after an OOM.
    """
    LOG.info(f"Daily (from 3-hourly): downloading {start_year}-{end_year}...")
    yearly_cache_dir = raw_dir / "daily_yearly"
    yearly_cache_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today()
    yearly_files = []

    for year in range(start_year, end_year + 1):
        year_cache = yearly_cache_dir / f"gldas_daily_{year}.nc"
        if year_cache.exists():
            yearly_files.append(year_cache)
            LOG.info(f"  year {year} already cached, skipping")
            continue

        day_parts = []
        d = dt.date(year, 1, 1)
        while d.year == year:
            if d > today:
                break
            doy = d.timetuple().tm_yday
            day_files = []
            for stamp in THREEHOURLY_STAMPS:
                fname = f"GLDAS_NOAH025_3H.A{d:%Y%m%d}.{stamp}.021.nc4"
                url = f"{BASE_URL}/{THREEHOURLY_COLLECTION}/{d.year}/{doy:03d}/{fname}"
                dest = raw_dir / "3hourly" / f"{d.year}" / f"{doy:03d}" / fname
                try:
                    download_file(url, dest, token)
                    day_files.append(dest)
                except requests.HTTPError as e:
                    LOG.warning(f"  skip {fname}: {e}")
            if day_files:
                day_ds = xr.open_mfdataset(day_files, combine="nested", concat_dim="time")
                day_mean = rename_to_quincy(day_ds).mean("time").load()
                day_mean = day_mean.expand_dims(time=[pd_timestamp(d)])
                day_parts.append(day_mean)
                day_ds.close()
            d += dt.timedelta(days=1)

        if not day_parts:
            LOG.warning(f"  no data for year {year}, skipping")
            continue
        year_ds = xr.concat(day_parts, dim="time").sortby("time")
        year_ds.to_netcdf(year_cache, encoding={v: {"zlib": True, "complevel": 4} for v in year_ds.data_vars})
        year_ds.close()
        yearly_files.append(year_cache)
        LOG.info(f"  year {year} done, cached to {year_cache}")

    if not yearly_files:
        LOG.warning("No daily data produced, nothing to write.")
        return

    full = xr.open_mfdataset(yearly_files, combine="nested", concat_dim="time", chunks={"time": 366})
    out_subdir = out_dir / "daily" / "0.25deg"
    out_subdir.mkdir(parents=True, exist_ok=True)
    for var in full.data_vars:
        out_path = out_subdir / f"gldas_{var}_{start_year}-{end_year}_daily.nc"
        full[[var]].to_netcdf(out_path, encoding={var: {"zlib": True, "complevel": 4}})
        LOG.info(f"  wrote {out_path}")
    full.close()


def pd_timestamp(d: dt.date):
    import pandas as pd
    return pd.Timestamp(d)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--products", nargs="+",
                         choices=["monthly_0.25deg", "monthly_0.5deg", "daily_0.25deg"],
                         default=["monthly_0.25deg", "monthly_0.5deg"])
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help=f"default: {DEFAULT_OUT_DIR}")
    parser.add_argument("--raw-dir", type=Path, default=None)
    args = parser.parse_args()

    token = get_token()
    raw_dir = args.raw_dir or (args.out_dir / "raw")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    want_monthly = "monthly_0.25deg" in args.products or "monthly_0.5deg" in args.products
    if want_monthly:
        process_monthly(
            args.start_year, args.end_year, args.out_dir, raw_dir, token,
            want_0p25="monthly_0.25deg" in args.products,
            want_0p5="monthly_0.5deg" in args.products,
        )

    if "daily_0.25deg" in args.products:
        process_daily(args.start_year, args.end_year, args.out_dir, raw_dir, token)

    LOG.info(f"Done. {args.start_year}-{args.end_year} written to {args.out_dir}")


if __name__ == "__main__":
    main()
