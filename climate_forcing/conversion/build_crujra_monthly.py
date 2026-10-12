#!/usr/bin/env python3
"""
CRU-JRA v2.5 (1901-2023) monthly forcing in QUINCY names and units, from
files already on disk -- the input of src/forcing/build_global_forcing_crujra.py.

Only v2.5 is used. v3.0 precipitation is broken in the CEDA source (the
CRU TS bias adjustment of JRA-55 precipitation is missing; annual totals are
0.20-0.27 of v2.5), see driver_data/crujra/monthly/0.5deg/README.md.

Output: driver_data/crujra/monthly/0.5deg_quincy/crujra_<var>_1901-2023_monthly.nc

  var             from (v2.5)                       units
  t_air           tmp                               K
  t_air_min       tmin                              K (monthly mean of daily min)
  t_air_max       tmax                              K
  precip_total    pre (monthly total, mm)           / days in month -> mm day-1
  q_air           spfh                              kg kg-1
  press_srf       pres                              Pa
  swvis_srf_down  dswrf                             W m-2
  lw_srf_down     dlwrf                             W m-2
  wind_air        raw 6-hourly ugrd, vgrd           monthly mean of sqrt(u^2+v^2), m s-1

Wind is recomputed from the 6-hourly raw files (raw/v2.5/{ugrd,vgrd}): the
monthly files only hold mean u and v, and |mean(u), mean(v)| underestimates
the mean speed (the same bias the old ERA5 wind had).

CRU-JRA uses a 365-day calendar; February always has 28 days. The output time
axis is the first of each month, "days since 1900-01-01", gregorian.
Ocean cells (zero precipitation, masked elsewhere) are NaN in every file,
using tmp's land mask.

Usage:
  python build_crujra_monthly.py wind YEAR     # one year of wind -> cache
  python build_crujra_monthly.py merge         # all variables -> 0.5deg_quincy/
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import netCDF4 as nc
import numpy as np

ROOT = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/crujra")
MONTHLY_V25 = ROOT / "monthly" / "0.5deg"
RAW_V25 = ROOT / "raw" / "v2.5"
WIND_CACHE = ROOT / "monthly_wind_cache_v2.5"
OUT_DIR = ROOT / "monthly" / "0.5deg_quincy"
START, END = 1901, 2023
DAYS_NOLEAP = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])

PLAIN = {  # QUINCY name -> (v2.5 name, units, long_name)
    "t_air": ("tmp", "K", "2 m air temperature, monthly mean"),
    "t_air_min": ("tmin", "K", "monthly mean of daily minimum 2 m air temperature"),
    "t_air_max": ("tmax", "K", "monthly mean of daily maximum 2 m air temperature"),
    "q_air": ("spfh", "kg kg-1", "near-surface specific humidity"),
    "press_srf": ("pres", "Pa", "surface pressure"),
    "swvis_srf_down": ("dswrf", "W m-2", "surface downward shortwave radiation"),
    "lw_srf_down": ("dlwrf", "W m-2", "surface downward longwave radiation"),
    "precip_total": ("pre", "mm day-1", "total precipitation, monthly mean daily rate"),
}


def read(path: Path, var: str) -> np.ndarray:
    with nc.Dataset(path) as ds:
        x = np.ma.filled(ds[var][:].astype(np.float32), np.nan)
    x[np.abs(x) > 1e20] = np.nan
    return x


def wind_year(year: int) -> None:
    out = WIND_CACHE / f"wind_{year}.nc"
    if out.exists():
        print(f"have {out}")
        return
    u_path = next(RAW_V25.glob(f"ugrd/crujra.v2.5.5d.ugrd.{year}.365d.noc.nc"))
    v_path = next(RAW_V25.glob(f"vgrd/crujra.v2.5.5d.vgrd.{year}.365d.noc.nc"))
    with nc.Dataset(u_path) as du, nc.Dataset(v_path) as dv:
        n = len(du["time"])
        assert n == 1460, (year, n)  # 365 days x 4
        lat, lon = du["lat"][:], du["lon"][:]
        speed = np.full((12, len(lat), len(lon)), np.nan, dtype=np.float32)
        t0 = 0
        for m, nd in enumerate(DAYS_NOLEAP):
            t1 = t0 + 4 * nd
            u = np.ma.filled(du["ugrd"][t0:t1].astype(np.float32), np.nan)
            v = np.ma.filled(dv["vgrd"][t0:t1].astype(np.float32), np.nan)
            u[np.abs(u) > 1e20] = np.nan
            v[np.abs(v) > 1e20] = np.nan
            speed[m] = np.sqrt(u ** 2 + v ** 2).mean(0)
            t0 = t1
    WIND_CACHE.mkdir(parents=True, exist_ok=True)
    part = out.with_name(out.name + ".part")
    with nc.Dataset(part, "w") as ds:
        ds.createDimension("month", 12)
        ds.createDimension("lat", len(lat))
        ds.createDimension("lon", len(lon))
        ds.createVariable("lat", "f8", ("lat",))[:] = lat
        ds.createVariable("lon", "f8", ("lon",))[:] = lon
        w = ds.createVariable("wind", "f4", ("month", "lat", "lon"), zlib=True, complevel=4,
                              fill_value=np.float32(np.nan))
        w[:] = speed
        w.units = "m s-1"
    part.rename(out)
    print(f"wrote {out}: land mean {np.nanmean(speed):.2f} m/s")


def write(var: str, data: np.ndarray, lat, lon, units: str, long_name: str, source: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"crujra_{var}_{START}-{END}_monthly.nc"
    part = out.with_name(out.name + ".part")
    with nc.Dataset(part, "w") as ds:
        ds.createDimension("time", None)
        ds.createDimension("lat", len(lat))
        ds.createDimension("lon", len(lon))
        t = ds.createVariable("time", "f8", ("time",))
        t.setncatts({"units": "days since 1900-01-01", "calendar": "gregorian", "standard_name": "time"})
        t[:] = nc.date2num([dt.datetime(y, m, 1) for y in range(START, END + 1) for m in range(1, 13)],
                           t.units, t.calendar)
        v = ds.createVariable("lat", "f8", ("lat",))
        v[:] = lat
        v.setncatts({"units": "degrees_north", "standard_name": "latitude"})
        v = ds.createVariable("lon", "f8", ("lon",))
        v[:] = lon
        v.setncatts({"units": "degrees_east", "standard_name": "longitude"})
        x = ds.createVariable(var, "f4", ("time", "lat", "lon"), zlib=True, complevel=4,
                              chunksizes=(12, 90, 90), fill_value=np.float32(np.nan))
        x[:] = data
        x.setncatts({"units": units, "long_name": long_name, "source": source})
        ds.setncatts({"title": "CRU-JRA v2.5 monthly forcing, QUINCY names and units",
                      "history": f"created {dt.datetime.now():%Y-%m-%d %H:%M} by "
                                 "climate_forcing/conversion/build_crujra_monthly.py"})
    part.rename(out)
    print(f"wrote {out}: [{np.nanmin(data):.4g}, {np.nanmax(data):.4g}], mean {np.nanmean(data):.4g}")


def merge() -> None:
    n_months = (END - START + 1) * 12
    tmp_file = MONTHLY_V25 / f"crujra_v2.5_tmp_{START}-{END}_monthly.nc"
    with nc.Dataset(tmp_file) as ds:
        lat, lon = ds["lat"][:].astype(float), ds["lon"][:].astype(float)
    land = np.isfinite(read(tmp_file, "tmp")[0])
    days = np.tile(DAYS_NOLEAP, END - START + 1)[:, None, None].astype(np.float32)

    for var, (src, units, lname) in PLAIN.items():
        x = read(MONTHLY_V25 / f"crujra_v2.5_{src}_{START}-{END}_monthly.nc", src)
        assert x.shape[0] == n_months, (src, x.shape)
        if var == "precip_total":
            x = x / days
        x[:, ~land] = np.nan
        write(var, x, lat, lon, units, lname, f"CRU-JRA v2.5 {src}")
        del x

    missing = [y for y in range(START, END + 1) if not (WIND_CACHE / f"wind_{y}.nc").exists()]
    if missing:
        sys.exit(f"wind cache incomplete, missing years: {missing[:10]}{'...' if len(missing) > 10 else ''}")
    wind = np.concatenate([read(WIND_CACHE / f"wind_{y}.nc", "wind") for y in range(START, END + 1)])
    wind[:, ~land] = np.nan
    write("wind_air", wind, lat, lon, "m s-1", "10 m wind speed, monthly mean of 6-hourly speed",
          "CRU-JRA v2.5 6-hourly ugrd, vgrd")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wind")
    w.add_argument("year", type=int)
    sub.add_parser("merge")
    args = ap.parse_args()
    if args.cmd == "wind":
        wind_year(args.year)
    else:
        merge()


if __name__ == "__main__":
    main()
