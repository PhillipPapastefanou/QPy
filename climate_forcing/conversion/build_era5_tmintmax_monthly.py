#!/usr/bin/env python3
"""
ERA5 monthly Tmin/Tmax (monthly mean of daily minimum / maximum 2 m
temperature) 1940-2025 on the ERA5 0.5deg point grid of
driver_data/era5/monthly/0.5deg/ (361 x 720, latitude 90..-90, longitude
0..359.5), so the ERA5 forcing store can carry t_air_min/t_air_max.

The ERA5 monthly-means product has no Tmin/Tmax, so they come from daily data
(daily extremes of the hourly 2 m temperature over UTC days):
  - 1940-1958 and 2025: Copernicus CDS derived-era5-single-levels-daily-
    statistics, regridded by CDS to the 0.5deg point grid, downloaded by
    download/download_era5_daily.py into era5/raw/.
  - 1959-2024: BGC shared archive /Net/Groups/data_BGC/era5/e1/0d25_daily/
    t2mmin, t2mmax (0.25deg cells). Monthly means on the cells, then each
    0.5deg point gets the mean of the 2 x 2 cells around it (at the poles the
    single row next to the pole), minus a fixed per-point, per-calendar-month
    "representation offset" (below).

Why this split (checked 2026-10-11 against the current ERA5 monthly t_air):
  - the archive (built March 2022) still holds ERA5's *preliminary* 1950-1978
    back extension, replaced by ECMWF in 2023; its 1950-1958 differs from
    current ERA5 by 0.43-0.87 K RMSE (monthly t2m), against a constant 0.29 K
    from 1959 on. So 1940-1958 come from CDS (the current release).
  - from 1959 the remaining 0.29 K RMSE (99.9th pct ~2.8 K, mountains/coasts)
    is static: 2x2 cell means vs CDS's point interpolation. The offset
    archive t2m - CDS monthly t_air, averaged over OFFSET_YEARS, removes it
    (0.29 -> 0.09 K in 1965, 2015, 2024). It is learned on mean temperature
    and applied to Tmin and Tmax (the representation effect is a grid effect,
    not a diurnal one).

Usage:
  python build_era5_tmintmax_monthly.py offset          # representation offset (once)
  python build_era5_tmintmax_monthly.py year YEAR       # one year -> cache
  python build_era5_tmintmax_monthly.py merge           # cache -> era5_t_air_{min,max}_1940-2025_monthly.nc
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import netCDF4 as nc
import numpy as np

ARCHIVE = Path("/Net/Groups/data_BGC/era5/e1/0d25_daily")
ERA5 = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/era5")
RAW = ERA5 / "raw"
OUT_DIR = ERA5 / "monthly" / "0.5deg"
CACHE = ERA5 / "monthly_tmintmax_cache" / "0.5deg"
REFERENCE = OUT_DIR / "era5_t_air_1940-2025_monthly.nc"   # grid + time axis template
START, END = 1940, 2025
ARCHIVE_YEARS = range(1959, 2025)
OFFSET_YEARS = (1960, 1970, 1980, 1990, 2000, 2010, 2020)
BAND = 90  # archive rows per read (its chunks are 5 days x 8 x 15 cells)
VARS = {"t_air_min": ("t2mmin", "tmin"), "t_air_max": ("t2mmax", "tmax")}


def cells_to_points(c: np.ndarray) -> np.ndarray:
    """(..., 720, 1440) 0.25deg cells, lat 89.875..-89.875, lon -179.875..179.875
    -> (..., 361, 720) 0.5deg points, lat 90..-90, lon 0..359.5."""
    c = np.roll(c, 720, axis=-1)                    # lon 0.125 .. 359.875
    rows = np.empty(c.shape[:-2] + (361, 1440), dtype=np.float32)
    rows[..., 0, :] = c[..., 0, :]
    rows[..., 360, :] = c[..., 719, :]
    rows[..., 1:360, :] = 0.5 * (c[..., 1:719:2, :] + c[..., 2:720:2, :])
    return 0.5 * (np.roll(rows, 1, axis=-1)[..., 0::2] + rows[..., 0::2])


def archive_monthly(year: int, short: str) -> np.ndarray:
    path = ARCHIVE / short / f"{short}.daily.an.era5.1440.720.{year}.nc"
    with nc.Dataset(path) as ds:
        v = ds[short]
        v.set_auto_maskandscale(False)
        months = np.array([d.month for d in nc.num2date(ds["time"][:], ds["time"].units, ds["time"].calendar)])
        out = np.full((12, 720, 1440), np.nan, dtype=np.float32)
        for r0 in range(0, 720, BAND):
            x = v[:, r0:r0 + BAND, :].astype(np.float32)
            x[(x < 100) | (x > 400)] = np.nan
            for m in range(1, 13):
                out[m - 1, r0:r0 + BAND] = np.nanmean(x[months == m], axis=0)
    assert sorted(set(months)) == list(range(1, 13)), (path, sorted(set(months)))
    return cells_to_points(out)


def cds_monthly(year: int, tag: str) -> np.ndarray:
    path = RAW / f"era5_daily_{tag}_{year}-{year}_grid0.5x0.5.nc"
    if not path.exists():
        raise FileNotFoundError(path)
    with nc.Dataset(path) as ds:
        tname = "valid_time" if "valid_time" in ds.variables else "time"
        months = np.array([d.month for d in nc.num2date(ds[tname][:], ds[tname].units)])
        x = np.ma.filled(ds["t2m"][:].astype(np.float32), np.nan)
        lat = ds["latitude"][:]
        assert x.shape[1:] == (361, 720) and lat[0] == 90, (path, x.shape)
    assert sorted(set(months)) == list(range(1, 13)), (path, sorted(set(months)))
    return np.stack([np.nanmean(x[months == m], axis=0) for m in range(1, 13)]).astype(np.float32)


OFFSET_FILE = CACHE / "representation_offset_archive_minus_cds.nc"


def offset() -> None:
    """Archive daily-mean t2m (2x2 cell mean) minus CDS monthly t_air, per point
    and calendar month, mean over OFFSET_YEARS."""
    with nc.Dataset(REFERENCE) as ref:
        diffs = []
        for y in OFFSET_YEARS:
            cds = np.ma.filled(ref["t_air"][(y - START) * 12:(y - START) * 12 + 12], np.nan)
            diffs.append(archive_monthly(y, "t2m") - cds)
            print(f"  {y} done")
    off = np.nanmean(diffs, axis=0).astype(np.float32)
    CACHE.mkdir(parents=True, exist_ok=True)
    with nc.Dataset(OFFSET_FILE, "w") as ds:
        ds.createDimension("month", 12)
        ds.createDimension("latitude", 361)
        ds.createDimension("longitude", 720)
        v = ds.createVariable("offset", "f4", ("month", "latitude", "longitude"), zlib=True)
        v[:] = off
        v.setncatts({"units": "K", "long_name": "archive daily-mean t2m (2x2 cell mean) minus CDS monthly t_air, "
                                                f"mean over {OFFSET_YEARS}"})
    print(f"wrote {OFFSET_FILE}: |offset| mean {np.nanmean(np.abs(off)):.3f} K, max {np.nanmax(np.abs(off)):.2f} K")


def year(y: int) -> None:
    out = CACHE / f"era5_tmintmax_{y}.nc"
    if out.exists():
        print(f"have {out}")
        return
    fields, sources = {}, {}
    for var, (short, tag) in VARS.items():
        if y in ARCHIVE_YEARS:
            with nc.Dataset(OFFSET_FILE) as ds:   # run `offset` first
                off = np.ma.filled(ds["offset"][:], 0.0)
            fields[var] = archive_monthly(y, short) - off
            sources[var] = "BGC archive 0d25_daily (2x2 cell mean) minus representation offset"
        else:
            fields[var] = cds_monthly(y, tag)
            sources[var] = "CDS derived-era5-single-levels-daily-statistics"
    CACHE.mkdir(parents=True, exist_ok=True)
    part = out.with_name(out.name + ".part")
    with nc.Dataset(part, "w") as ds:
        ds.createDimension("month", 12)
        ds.createDimension("latitude", 361)
        ds.createDimension("longitude", 720)
        for var, x in fields.items():
            v = ds.createVariable(var, "f4", ("month", "latitude", "longitude"), zlib=True, complevel=4)
            v[:] = x
            v.source = sources[var]
    part.rename(out)
    tmin, tmax = fields["t_air_min"], fields["t_air_max"]
    print(f"wrote {out}: Tmin mean {np.nanmean(tmin):.2f} K, Tmax mean {np.nanmean(tmax):.2f} K, "
          f"Tmax<Tmin in {np.mean(tmax < tmin):.2e} of values")


def merge() -> None:
    missing = [y for y in range(START, END + 1) if not (CACHE / f"era5_tmintmax_{y}.nc").exists()]
    if missing:
        sys.exit(f"cache incomplete, missing years: {missing}")
    with nc.Dataset(REFERENCE) as ref:
        lat, lon = ref["latitude"][:], ref["longitude"][:]
        tvals, tunits, tcal = ref["time"][:], ref["time"].units, getattr(ref["time"], "calendar", "proleptic_gregorian")
    assert len(tvals) == (END - START + 1) * 12
    for var in VARS:
        data = np.concatenate([np.ma.filled(nc.Dataset(CACHE / f"era5_tmintmax_{y}.nc")[var][:], np.nan)
                               for y in range(START, END + 1)])
        out = OUT_DIR / f"era5_{var}_{START}-{END}_monthly.nc"
        part = out.with_name(out.name + ".part")
        with nc.Dataset(part, "w") as ds:
            ds.createDimension("time", None)
            ds.createDimension("latitude", len(lat))
            ds.createDimension("longitude", len(lon))
            t = ds.createVariable("time", "f8", ("time",))
            t.setncatts({"units": tunits, "calendar": tcal, "standard_name": "time"})
            t[:] = tvals
            v = ds.createVariable("latitude", "f8", ("latitude",))
            v[:] = lat
            v.setncatts({"units": "degrees_north", "standard_name": "latitude"})
            v = ds.createVariable("longitude", "f8", ("longitude",))
            v[:] = lon
            v.setncatts({"units": "degrees_east", "standard_name": "longitude"})
            x = ds.createVariable(var, "f4", ("time", "latitude", "longitude"), zlib=True, complevel=4,
                                  chunksizes=(12, 91, 180), fill_value=np.float32(np.nan))
            x[:] = data
            x.setncatts({"units": "K",
                         "long_name": f"monthly mean of daily {'minimum' if var.endswith('min') else 'maximum'} "
                                      f"2 m temperature",
                         "source": "1940-1958 and 2025: CDS derived-era5-single-levels-daily-statistics "
                                   "(0.5deg); 1959-2024: BGC archive /Net/Groups/data_BGC/era5/e1/0d25_daily "
                                   "(2x2 cell mean onto 0.5deg points) minus a static representation offset; "
                                   "see conversion/build_era5_tmintmax_monthly.py"})
            ds.history = (f"created {dt.datetime.now():%Y-%m-%d %H:%M} by "
                          "climate_forcing/conversion/build_era5_tmintmax_monthly.py")
        part.rename(out)
        print(f"wrote {out}: [{np.nanmin(data):.1f}, {np.nanmax(data):.1f}] K")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("year")
    p.add_argument("year", type=int)
    sub.add_parser("offset")
    sub.add_parser("merge")
    args = ap.parse_args()
    {"year": lambda: year(args.year), "offset": offset, "merge": merge}[args.cmd]()


if __name__ == "__main__":
    main()
