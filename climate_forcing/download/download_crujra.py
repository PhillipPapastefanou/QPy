#!/usr/bin/env python3
"""
Download CRU-JRA (CEDA Archive) and aggregate it to monthly NetCDF.

CRU-JRA is the dataset already consumed by this repo (see
src/quincy_ui/forcing_prep.py, which reads pre-built monthly files named
kmcrujra.v2.4.5d.{var}.1981-2022.365d.nc). This script reproduces that
monthly product from the raw 6-hourly CEDA source so it can be regenerated
for a different variable/year range or a newer CRU-JRA version.

Verified against the live CEDA archive on 2026-09-05. Two versions exist
side by side there:
  - v2.5:  https://data.ceda.ac.uk/badc/cru/data/cru_jra/cru_jra_2.5/  -> 1901-2023
  - v3.0:  https://data.ceda.ac.uk/badc/cru/data/cru_jra/cru_jra_3.0/  -> 1901-**2024**
           (added to the archive in April 2025 -- this is the version to
           use if you want CRU-JRA's own most recent year; it's still not
           2025, see download_era5_monthly.py for that).
This script defaults to v3.0 but takes --ceda-version to pick v2.5 for
consistency with the older cached kmcrujra files if needed.

File naming is NOT identical between versions -- v2.5 files are named
crujra.v2.5.5d.{var}.{year}.365d.noc.nc.gz, v3.0 files are named
crujra.v3.5d.{var}.{year}.365d.noc.nc.gz (no ".0"). Rather than parse the
year out of the filename by a fixed token position (fragile -- an earlier
version of this script got this wrong for exactly this reason), this
script pulls the year straight from the JSON directory listing's file
metadata via a regex, and reuses the server's own file name for the local
cache -- so it does not need to know each version's exact naming scheme.

  - Directory listing:  https://data.ceda.ac.uk/badc/cru/data/cru_jra/cru_jra_{version}/data/{var}/?json
  - Download endpoint:  https://dap.ceda.ac.uk/{path}?download=1
  - Auth: CEDA requires a free account. Anonymous/basic-auth download is
    NOT accepted (confirmed: the download URL 302-redirects to
    auth.ceda.ac.uk). Scripted access needs a short-lived Bearer token,
    see https://help.ceda.ac.uk/article/5100-archive-access-tokens :
      wget URL --header "Authorization: Bearer <TOKEN>"
    Get one either by exporting CEDA_TOKEN yourself (from
    https://services.ceda.ac.uk/account/token/, valid 3 days), or by
    setting CEDA_USERNAME/CEDA_PASSWORD so this script mints one via the
    token API (https://services.ceda.ac.uk/api/token/create/).

CRU-JRA variables (10 total): tmp, tmax, tmin, spfh, pres, dswrf, dlwrf,
pre, ugrd, vgrd. Note "pre" is total precip only -- CRU-JRA does not split
rain/snow natively (see README.md comparison table); wind is provided as
u/v components and is combined into a scalar speed here, matching how the
existing kmcrujra "wind" field is presumably derived upstream.

COVERAGE: neither v2.5 (2023) nor v3.0 (2024) reaches 2025. For 2025, use
download_era5_monthly.py (rolling, near-present) instead, or bridge the
gap by stitching that on after the latest CRU-JRA year.

Usage:
  export CEDA_USERNAME=... CEDA_PASSWORD=...
  python download_crujra.py --variables tmp pre dswrf dlwrf pres spfh ugrd vgrd \\
      --start-year 2018 --end-year 2024 --out-dir ./data/crujra
  # or, to match the older cached kmcrujra v2.4-ish files:
  python download_crujra.py --ceda-version 2.5 --start-year 2018 --end-year 2023 ...
"""
from __future__ import annotations

import argparse
import gzip
import re
import shutil
import sys
from pathlib import Path

import requests
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import (
    count_wet_days_monthly,
    env_or_none,
    get_logger,
    open_dataset_verified,
    resample_monthly,
    retry_request,
    wind_speed_from_components,
    write_monthly_netcdf,
    CRUJRA_FLUX_SCALE,
)

LOG = get_logger("crujra")

DEFAULT_CEDA_VERSION = "3.0"
DEFAULT_OUT_DIR = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/crujra")
CEDA_DOWNLOAD_ROOT = "https://dap.ceda.ac.uk"
CEDA_TOKEN_ENDPOINT = "https://services.ceda.ac.uk/api/token/create/"
YEAR_RE = re.compile(r"\.(\d{4})\.")

ALL_VARIABLES = ["tmp", "tmax", "tmin", "spfh", "pres", "dswrf", "dlwrf", "pre", "ugrd", "vgrd"]

# how to aggregate each raw variable to monthly: "mean" for instantaneous/
# rate state variables, "sum" for the precipitation depth.
AGGREGATION = {
    "tmp": "mean", "tmax": "mean", "tmin": "mean", "spfh": "mean",
    "pres": "mean", "dswrf": "mean", "dlwrf": "mean",
    "ugrd": "mean", "vgrd": "mean",
    "pre": "sum",
}

# Scale factor for dswrf's accumulated-J/m2-per-6h -> average-W/m2 fix --
# see CRUJRA_FLUX_SCALE's docstring in common.py for the full derivation.
SCALE = CRUJRA_FLUX_SCALE


def data_root(version: str) -> str:
    return f"https://data.ceda.ac.uk/badc/cru/data/cru_jra/cru_jra_{version}/data"


def get_token() -> str:
    token = env_or_none("CEDA_TOKEN")
    if token:
        return token

    user = env_or_none("CEDA_USERNAME")
    pw = env_or_none("CEDA_PASSWORD")
    if not (user and pw):
        raise SystemExit(
            "No CEDA credentials found. Set CEDA_TOKEN, or CEDA_USERNAME + "
            "CEDA_PASSWORD (a free account: https://services.ceda.ac.uk/)."
        )

    LOG.info("Minting a short-lived CEDA access token...")
    resp = requests.post(CEDA_TOKEN_ENDPOINT, auth=(user, pw), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # Response shape per CEDA docs: {"access_token": "...", ...}
    token = data.get("access_token") or data.get("token")
    if not token:
        raise RuntimeError(f"Unexpected CEDA token response: {data}")
    return token


def list_year_files(var: str, version: str) -> dict[int, dict]:
    """Query the CEDA JSON directory listing for one variable folder.

    Pulls the year out of each filename with a regex rather than a fixed
    token index, since v2.5 ("crujra.v2.5.5d.{var}.{year}...") and v3.0
    ("crujra.v3.5d.{var}.{year}...") don't tokenize the same way.
    """
    url = f"{data_root(version)}/{var}/?json"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    listing = resp.json()

    by_year = {}
    for item in listing.get("items", []):
        name = item["name"]
        if not (name.endswith(".nc.gz") or name.endswith(".nc")):
            continue
        m = YEAR_RE.search(name)
        if not m:
            continue
        by_year[int(m.group(1))] = item
    return by_year


def download_year(item: dict, token: str, raw_dir: Path) -> Path:
    """Download+decompress one file, named after the server's own filename."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    gz_name = item["name"]
    gz_path = raw_dir / gz_name
    nc_path = raw_dir / gz_name.removesuffix(".gz") if gz_name.endswith(".gz") else gz_path

    if nc_path.exists():
        LOG.info(f"  already have {nc_path.name}, skipping download")
        return nc_path

    url = item.get("download") or f"{CEDA_DOWNLOAD_ROOT}{item['path']}?download=1"
    LOG.info(f"  downloading {gz_name} ({item['size'] / 1e6:.0f} MB)")
    headers = {"Authorization": f"Bearer {token}"}

    def _fetch():
        with requests.get(url, headers=headers, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(gz_path, "wb") as f:
                shutil.copyfileobj(r.raw, f)

    retry_request(_fetch, LOG)

    if gz_path != nc_path:
        with gzip.open(gz_path, "rb") as f_in, open(nc_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        gz_path.unlink()
    return nc_path


def process_variable(var: str, years: list[int], version: str, token: str, raw_dir: Path, out_dir: Path) -> None:
    LOG.info(f"Processing variable '{var}'")
    start, end = years[0], years[-1]
    out_path = out_dir / f"crujra_v{version}_{var}_{start}-{end}_monthly.nc"
    if out_path.exists():
        LOG.info(f"  already have {out_path.name}, skipping")
        return
    available = list_year_files(var, version)
    how = AGGREGATION.get(var, "mean")

    # Resample each year to monthly (12 timesteps) immediately after opening
    # it, rather than concatenating all years of raw 6-hourly data first.
    # The full record concatenated raw would be ~187 GB for one variable
    # (124y x 1460 timesteps/y x 360x720 grid) -- confirmed to actually
    # OOM in practice (2026-09-05, this exact bug crashed
    # download_terraclimate_monthly.py's analogous code). Resampling
    # per-year first is mathematically identical since monthly bins never
    # cross year boundaries, and keeps peak memory to ~1 year at a time.
    monthly_parts = []
    for year in years:
        if year not in available:
            LOG.warning(f"  no {var} file for {year} in CEDA archive (v{version}), skipping")
            continue
        nc_path = download_year(available[year], token, raw_dir / var)
        ds = open_dataset_verified(nc_path, lambda: download_year(available[year], token, raw_dir / var), LOG)
        data_var = var if var in ds.data_vars else list(ds.data_vars)[0]
        raw_da = ds[data_var]
        if var in SCALE:
            raw_da = raw_da * SCALE[var]
        monthly_parts.append(resample_monthly(raw_da, how=how).load())
        ds.close()

    if not monthly_parts:
        LOG.warning(f"  nothing downloaded for '{var}', skipping aggregation")
        return

    monthly = xr.concat(monthly_parts, dim="time")
    write_monthly_netcdf(monthly, out_path, var)
    LOG.info(f"  wrote {out_path}")


def process_wind_speed(years: list[int], version: str, token: str, raw_dir: Path, out_dir: Path) -> None:
    """CRU-JRA has no scalar wind speed variable; derive it from ugrd/vgrd."""
    LOG.info("Deriving wind speed from ugrd/vgrd")
    start, end = years[0], years[-1]
    out_path = out_dir / f"crujra_v{version}_wind_{start}-{end}_monthly.nc"
    if out_path.exists():
        LOG.info(f"  already have {out_path.name}, skipping")
        return
    u_avail, v_avail = list_year_files("ugrd", version), list_year_files("vgrd", version)

    monthly_parts = []
    for year in years:
        if year not in u_avail or year not in v_avail:
            LOG.warning(f"  missing ugrd/vgrd for {year}, skipping")
            continue
        u_path = download_year(u_avail[year], token, raw_dir / "ugrd")
        v_path = download_year(v_avail[year], token, raw_dir / "vgrd")
        u_ds = open_dataset_verified(u_path, lambda: download_year(u_avail[year], token, raw_dir / "ugrd"), LOG)
        v_ds = open_dataset_verified(v_path, lambda: download_year(v_avail[year], token, raw_dir / "vgrd"), LOG)
        u_var = "ugrd" if "ugrd" in u_ds.data_vars else list(u_ds.data_vars)[0]
        v_var = "vgrd" if "vgrd" in v_ds.data_vars else list(v_ds.data_vars)[0]
        speed = wind_speed_from_components(u_ds[u_var], v_ds[v_var])
        monthly_parts.append(resample_monthly(speed, how="mean").load())
        u_ds.close()
        v_ds.close()

    if not monthly_parts:
        return

    monthly_speed = xr.concat(monthly_parts, dim="time")
    write_monthly_netcdf(monthly_speed, out_path, "wind")
    LOG.info(f"  wrote {out_path}")


def process_wetdays(years: list[int], version: str, token: str, raw_dir: Path, out_dir: Path, threshold_mm: float) -> None:
    LOG.info("Deriving wetdays from pre")
    start, end = years[0], years[-1]
    out_path = out_dir / f"crujra_v{version}_wetdays_{start}-{end}_monthly.nc"
    if out_path.exists():
        LOG.info(f"  already have {out_path.name}, skipping")
        return
    avail = list_year_files("pre", version)
    monthly_parts = []
    for year in years:
        if year not in avail:
            continue
        pre_path = download_year(avail[year], token, raw_dir / "pre")
        ds = open_dataset_verified(pre_path, lambda: download_year(avail[year], token, raw_dir / "pre"), LOG)
        data_var = "pre" if "pre" in ds.data_vars else list(ds.data_vars)[0]
        daily = ds[data_var].resample(time="1D").sum()
        monthly_parts.append(count_wet_days_monthly(daily, threshold_mm=threshold_mm).load())
        ds.close()

    if not monthly_parts:
        return

    wetdays = xr.concat(monthly_parts, dim="time")
    write_monthly_netcdf(wetdays, out_path, "wetdays")
    LOG.info(f"  wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variables", nargs="+", default=ALL_VARIABLES,
                         help=f"subset of {ALL_VARIABLES}")
    parser.add_argument("--ceda-version", default=DEFAULT_CEDA_VERSION, choices=["2.5", "3.0"],
                         help="CRU-JRA release: 3.0 reaches 2024, 2.5 reaches 2023 (default: 3.0)")
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                         help=f"default: {DEFAULT_OUT_DIR}")
    parser.add_argument("--raw-dir", type=Path, default=None,
                         help="where to cache raw yearly NetCDFs (default: <out-dir>/raw)")
    parser.add_argument("--derive-wind", action="store_true",
                         help="also derive scalar wind speed from ugrd/vgrd")
    parser.add_argument("--derive-wetdays", action="store_true",
                         help="also derive monthly wet-day counts from pre")
    parser.add_argument("--wetday-threshold-mm", type=float, default=1.0)
    args = parser.parse_args()

    bad = set(args.variables) - set(ALL_VARIABLES)
    if bad:
        sys.exit(f"Unknown CRU-JRA variables: {sorted(bad)}. Valid: {ALL_VARIABLES}")

    years = list(range(args.start_year, args.end_year + 1))
    raw_dir = args.raw_dir or (args.out_dir / "raw" / f"v{args.ceda_version}")

    # dataset/time_resolution/spatial_resolution/ layout -- CRU-JRA is
    # native 0.5deg (confirmed from file coords), so the monthly-aggregated
    # outputs land in monthly/0.5deg/ regardless of --ceda-version.
    out_subdir = args.out_dir / "monthly" / "0.5deg"
    out_subdir.mkdir(parents=True, exist_ok=True)

    token = get_token()

    for var in args.variables:
        process_variable(var, years, args.ceda_version, token, raw_dir, out_subdir)

    if args.derive_wind:
        process_wind_speed(years, args.ceda_version, token, raw_dir, out_subdir)

    if args.derive_wetdays:
        process_wetdays(years, args.ceda_version, token, raw_dir, out_subdir, args.wetday_threshold_mm)


if __name__ == "__main__":
    main()
