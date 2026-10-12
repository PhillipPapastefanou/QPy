#!/usr/bin/env python3
"""
Build a monthly ERA5-Land forcing at 0.1deg, 0.25deg and 0.5deg from the BGC
shared daily archive (/Net/Groups/data_BGC/era5_land/e1/0d10_daily), with
longwave taken from our own ERA5 CDS monthly product (ERA5-Land's strd only
exists from 2000, so ERA5 is used for every year to keep it consistent).
Temperature is provided as monthly means of daily Tmin and Tmax only (no
mean temperature), matching what the daily weather generator consumes.

Two stages, both run under Slurm (see build_era5land_monthly_*.sbatch):

  year  YEAR   daily 0.1deg -> monthly at all three resolutions, one cache
               file per year and resolution (job array over years).
  merge VAR    concatenate the per-year cache files into one file per
               variable and resolution (job array over variables). The
               special VAR "press_q" writes both press_srf (gap-filled, see
               below) and q_air.

Reading strategy (why not cdo/nco): the source files are stored in tiny
zlib chunks of (5 or 6 days) x 18 lat x 36 lon -- ssrd is the exception,
uncompressed and contiguous. Reading month by month would cut through the
time chunks at every month boundary and decompress those chunks twice; a
whole-year field doesn't fit comfortably in memory (365 x 1800 x 3600 x 4 B
= 9.5 GB per variable). So each variable is read in latitude bands of
BAND_ROWS rows x all days x all longitudes: every chunk is decompressed
exactly once, monthly means come straight out of the band, and a band
(<0.5 GB) is small. BAND_ROWS = 90 is a multiple of the 18-row chunks and
divides exactly into 0.5deg (5 rows) and 0.25deg (2.5 rows -> done on a
0.05deg upsampled band) target cells, so coarsening happens in the same pass.

Grids: all targets are cell-centred, latitude descending, longitude
-180..180 (the source convention): 0.1deg 1800x3600, 0.25deg 720x1440,
0.5deg 360x720. Coarse cells are the plain (not area-weighted) mean over
the land pixels they contain, same simplification as the rest of this
toolkit; cells without any land pixel are NaN. land_fraction (share of
0.1deg land pixels per cell) is written alongside.

Source quirks handled here (checked 2026-10-11):
  - Missing values are -9999 (t2m*, d2m, sp, ws10) or -32767 (tp), and tp
    additionally has scattered garbage values around -1e4..-2e4 -- all of
    them off the land mask. Anything below -1000 is treated as missing, and
    every variable is masked with the land mask taken from t2m_max.
  - sp is missing (-9999 all year) at 14,681 scattered land pixels in at
    least 2000-2015, and at 84% of land pixels in 2024. q_air therefore does
    not use daily pressure: the year stage stores the monthly mean vapour
    pressure (from d2m alone), and the merge stage computes
    q = 0.622 e / (p - 0.378 e) with the monthly pressure (using monthly
    instead of daily p changes q by well under 0.1%). Monthly pressure in a
    cell whose land pixels were not all complete is replaced by that cell's
    same-calendar-month mean over the complete years, and flagged in
    press_srf_gapfilled.
  - ssrd is global (no fill values) and its latitude axis is labelled
    90.0..-89.9, offset by half a pixel from every other variable
    (89.95..-89.95). It is moved onto the common grid by averaging adjacent
    rows (NaN-aware: at coasts the row that has data). The land masks
    confirm the offset (rows k-1 and k of the other variables match equally
    well). ~0.3% of land pixels have ssrd in neither row and are filled from
    their valid 3x3 neighbours. ERA5-Land shortwave is taken straight from ERA5, and a
    check against our CDS ERA5 monthly product matched to within 0.2%, so
    this half-pixel uncertainty is negligible at 0.25/0.5deg.
  - ws10 is labelled "m*s-2"; it is wind speed in m s-1.
  - ssrd and d2m end in 2024 in the archive; 2025 shortwave, dewpoint and
    pressure come from the CDS ERA5-Land monthly means instead (see
    load_cds_monthly), as does 2024 pressure, which is corrupt in the archive
    (CDS_OVERRIDE).
  - ssrd is incomplete for 1968 (31 Aug-30 Sep only) and 1972 (from 31 Jan);
    days are placed by the file's own dates, and months not fully covered use
    the ERA5 monthly shortwave instead (ERA5-Land shortwave is ERA5's), flagged
    in swvis_srf_down_from_era5.

Usage:
  python build_era5land_monthly.py year 2010
  python build_era5land_monthly.py merge t_air_max
  python build_era5land_monthly.py merge press_q
  python build_era5land_monthly.py merge t_air_max --end-year 2025
"""
from __future__ import annotations

import argparse
import calendar
import datetime
import sys
import time
import warnings
import zipfile
from pathlib import Path

import netCDF4 as nc
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_logger

LOG = get_logger("era5land-monthly")

SRC_DIR = Path("/Net/Groups/data_BGC/era5_land/e1/0d10_daily")
ERA5_MONTHLY = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/era5/monthly/0.25deg")
OUT_ROOT = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/era5_land")
CACHE_DIR = OUT_ROOT / "monthly_yearly_cache"
CDS_RAW_DIR = OUT_ROOT / "cds_monthly" / "raw"   # download/download_era5land_monthly_cds.py
# Archive files that exist but are wrong, replaced by the CDS monthly means:
# 2024 sp is -9999 at 84% of land pixels AND wrong at many of the rest
# (e.g. 58,300 Pa near Guangzhou in June; 8.7% of 0.5deg cells >10% off ERA5
# against a 0.5% terrain baseline in every other year).
CDS_OVERRIDE = {2024: {"press_srf"}}
OUT_DIR = OUT_ROOT / "monthly"

START_YEAR, END_YEAR = 1950, 2024
NLAT, NLON = 1800, 3600
BAND_ROWS = 90
SECONDS_PER_DAY = 86400.0
MISSING_BELOW = -1000.0

# target resolution label -> coarsening factor in 0.1deg pixels
RESOLUTIONS = {"0.1deg": 1.0, "0.25deg": 2.5, "0.5deg": 5.0}

# final output variable -> (units, long_name)
OUT_VARS = {
    "t_air_min": ("K", "monthly mean of daily minimum 2m air temperature"),
    "t_air_max": ("K", "monthly mean of daily maximum 2m air temperature"),
    "precip_total": ("mm day-1", "monthly mean daily total precipitation"),
    "swvis_srf_down": ("W m-2", "surface downwelling shortwave radiation"),
    "q_air": ("kg kg-1", "near-surface specific humidity, from monthly mean vapour pressure "
                         "(2m dewpoint) and surface pressure"),
    "press_srf": ("Pa", "surface pressure"),
    "wind_air": ("m s-1", "10m wind speed (monthly mean of daily mean speed)"),
    "lw_srf_down": ("W m-2", "surface downwelling longwave radiation, from ERA5 (not ERA5-Land)"),
}
# units of the cache-only variables
CACHE_UNITS = {"vap_press": "Pa", "press_coverage": "1", "land_fraction": "1", "swvis_from_era5": "1"}
# merge tasks: one per plain variable, plus press_q for press_srf + q_air
MERGE_TASKS = [v for v in OUT_VARS if v not in ("press_srf", "q_air")] + ["press_q"]

# cache variable -> (source folder, file kind) for the plain 1:1 variables
DIRECT = {
    "t_air_min": ("t2m_min", "an"),
    "t_air_max": ("t2m_max", "an"),
    "precip_total": ("tp", "an"),
    "press_srf": ("sp", "an"),
    "wind_air": ("ws10", "calc"),
}


def src_path(folder: str, kind: str, year: int) -> Path:
    return SRC_DIR / folder / f"{folder}.daily.{kind}.era5_land.3600.1800.{year}.nc"


def open_var(path: Path, name: str):
    ds = nc.Dataset(path)
    var = ds[name]
    var.set_auto_mask(False)
    return ds, var


def clean(a: np.ndarray) -> np.ndarray:
    """float32 with every fill/garbage value (< MISSING_BELOW, non-finite) as NaN."""
    a = np.asarray(a, dtype=np.float32)
    a[~np.isfinite(a) | (a < MISSING_BELOW)] = np.nan
    return a


def month_index(year: int) -> np.ndarray:
    """Day-of-year -> month (0..11) for a calendar year."""
    return np.repeat(np.arange(12), [calendar.monthrange(year, m + 1)[1] for m in range(12)])


def monthly_mean(daily: np.ndarray, months: np.ndarray) -> np.ndarray:
    """(ndays, ny, nx) -> (12, ny, nx) NaN-aware mean, float64 accumulation."""
    out = np.empty((12,) + daily.shape[1:], dtype=np.float32)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN (ocean) pixels -> NaN
        for m in range(12):
            out[m] = np.nanmean(daily[months == m], axis=0, dtype=np.float64)
    return out


def monthly_complete(daily: np.ndarray, months: np.ndarray) -> np.ndarray:
    """(12, ny, nx) True where every day of the month is valid."""
    return np.stack([np.isfinite(daily[months == m]).all(axis=0) for m in range(12)])


def vapour_pressure_from_dewpoint(t2d_k: np.ndarray) -> np.ndarray:
    """Bolton (1980), same constants as common.specific_humidity_from_dewpoint (Pa)."""
    t2d_c = t2d_k - 273.15
    return 611.2 * np.exp((17.67 * t2d_c) / (t2d_c + 243.5))


def specific_humidity(e_pa: np.ndarray, p_pa: np.ndarray) -> np.ndarray:
    return (0.622 * e_pa) / (p_pa - 0.378 * e_pa)


def pair_mean_rows(a: np.ndarray) -> np.ndarray:
    """(..., n+1, nx) -> (..., n, nx): NaN-aware mean of rows k and k+1, i.e.
    values half a row further south (where only one row has data, that one)."""
    upper, lower = a[..., :-1, :], a[..., 1:, :]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(np.stack([upper, lower]), axis=0)


def fill_from_neighbours(a: np.ndarray, where: np.ndarray) -> np.ndarray:
    """Fill NaNs at `where` (ny, nx) in (..., ny, nx) with the mean of the
    valid 3x3 neighbours (longitude wraps); anything without one stays NaN."""
    total = np.zeros_like(a, dtype=np.float64)
    count = np.zeros(a.shape, dtype=np.int16)
    padded = np.concatenate([a[..., :1, :], a, a[..., -1:, :]], axis=-2)
    for dy in (0, 1, 2):
        rows = padded[..., dy:dy + a.shape[-2], :]
        for dx in (-1, 0, 1):
            shifted = np.roll(rows, dx, axis=-1)
            ok = np.isfinite(shifted)
            total += np.where(ok, shifted, 0.0)
            count += ok
    fill = where & ~np.isfinite(a)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(fill, total / count, a)
    return out.astype(a.dtype)


def coarsen(field: np.ndarray, factor: float) -> np.ndarray:
    """NaN-aware block mean of (..., ny, nx) by factor 1, 2.5 or 5."""
    if factor == 1.0:
        return np.asarray(field, dtype=np.float32)
    if factor == 2.5:
        field = np.repeat(np.repeat(field, 2, axis=-2), 2, axis=-1)
        k = 5
    else:
        k = int(factor)
    *lead, ny, nx = field.shape
    blocks = field.reshape(*lead, ny // k, k, nx // k, k)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-ocean cells -> NaN, by design
        return np.nanmean(blocks, axis=(-3, -1)).astype(np.float32)


def target_axes(res: str) -> tuple[np.ndarray, np.ndarray]:
    step = {"0.1deg": 0.1, "0.25deg": 0.25, "0.5deg": 0.5}[res]
    lat = 90.0 - step / 2 - step * np.arange(round(180 / step))
    lon = -180.0 + step / 2 + step * np.arange(round(360 / step))
    return lat, lon


def bilinear_from_point_grid(field: np.ndarray, lat_src: np.ndarray, lon_src: np.ndarray,
                             lat_t: np.ndarray, lon_t: np.ndarray) -> np.ndarray:
    """Bilinear interpolation of (..., lat, lon) on a regular global point grid
    (latitude descending, longitude 0..360 starting at 0) to target
    coordinates, wrapping in longitude."""
    field = field.astype(np.float64)
    fy = (lat_src[0] - lat_t) / (lat_src[0] - lat_src[1])
    y0 = np.clip(np.floor(fy).astype(int), 0, len(lat_src) - 2)
    wy = (fy - y0)[:, None]
    field = field[..., y0, :] * (1 - wy) + field[..., y0 + 1, :] * wy
    fx = (lon_t % 360.0) / (lon_src[1] - lon_src[0])
    x0 = np.floor(fx).astype(int) % len(lon_src)
    x1 = (x0 + 1) % len(lon_src)
    wx = fx - np.floor(fx)
    return (field[..., x0] * (1 - wx) + field[..., x1] * wx).astype(np.float32)


def interp_era5(var: str, year: int, res: str) -> np.ndarray:
    """One year of an ERA5 CDS monthly variable (0.25deg point grid, lat
    90..-90, lon 0..359.75) bilinearly interpolated to the cell centres of a
    target grid."""
    with nc.Dataset(ERA5_MONTHLY / f"era5_{var}_1940-2025_monthly.nc") as ds:
        lat_src = ds["latitude"][:].astype(np.float64)
        lon_src = ds["longitude"][:].astype(np.float64)
        t0 = (year - 1940) * 12
        data = ds[var][t0:t0 + 12].filled(np.nan)
    lat_t, lon_t = target_axes(res)
    return bilinear_from_point_grid(data, lat_src, lon_src, lat_t, lon_t)


def points_to_cells(a: np.ndarray) -> np.ndarray:
    """(..., 1801, 3600) on the native 0.1deg point grid (lat 90..-90, lon
    starting at -180) -> (..., 1800, 3600) cell centres: NaN-aware mean of
    the four surrounding points (longitude wraps)."""
    rows = pair_mean_rows(a)
    cols = np.concatenate([rows, rows[..., :1]], axis=-1)
    return np.swapaxes(pair_mean_rows(np.swapaxes(cols, -1, -2)), -1, -2).astype(np.float32)


def load_cds_monthly(short: str, year: int) -> np.ndarray:
    """One year (12, 1800, 3600) of an ERA5-Land monthly-means variable from
    the CDS download, on the cell-centred grid, native units."""
    import xarray as xr
    for path in sorted(CDS_RAW_DIR.glob("era5land_monthly_means_*.nc")):
        tag, years = path.stem.split("_")[-2:]
        y0, y1 = (int(y) for y in years.split("-"))
        if short not in tag.split("-") or not y0 <= year <= y1:
            continue
        if zipfile.is_zipfile(path):
            extract = path.parent / f"{path.stem}_extracted"
            with zipfile.ZipFile(path) as zf:
                zf.extractall(extract)
            parts = [xr.open_dataset(p) for p in sorted(extract.glob("*.nc"))]
            ds = next(p for p in parts if short in p.data_vars)
        else:
            ds = xr.open_dataset(path)
        da = ds[short]
        tdim = "valid_time" if "valid_time" in da.dims else "time"
        da = da.sel({tdim: da[tdim].dt.year == year})
        if da.sizes[tdim] != 12:
            raise ValueError(f"{path}: {da.sizes[tdim]} months of {short} for {year}")
        da = da.assign_coords(longitude=((da["longitude"] + 180.0) % 360.0) - 180.0).sortby("longitude")
        da = da.sortby("latitude", ascending=False)
        if da.sizes["latitude"] != NLAT + 1 or da.sizes["longitude"] != NLON:
            raise ValueError(f"{path}: unexpected grid {dict(da.sizes)}")
        return points_to_cells(da.values.astype(np.float32))
    raise FileNotFoundError(f"no CDS monthly file with {short} for {year} in {CDS_RAW_DIR}")


def file_day_of_year(ds: nc.Dataset, year: int) -> np.ndarray:
    """0-based day of year of each time step of a daily source file, from its
    own time axis (some files don't start on 1 January, see ssrd 1968/1972)."""
    t = ds["time"]
    dates = nc.num2date(t[:], t.units, getattr(t, "calendar", "standard"))
    doy = np.array([(datetime.date(d.year, d.month, d.day) - datetime.date(year, 1, 1)).days for d in dates])
    if len(np.unique(doy)) != len(doy) or doy.min() < 0 or doy.max() >= len(month_index(year)):
        raise ValueError(f"{year}: time axis outside the year or with duplicate days")
    return doy


def _write_axes(ds: nc.Dataset, res: str, unlimited_time: bool):
    lat, lon = target_axes(res)
    ds.createDimension("time", None if unlimited_time else 12)
    ds.createDimension("lat", len(lat))
    ds.createDimension("lon", len(lon))
    t = ds.createVariable("time", "i4", ("time",))
    t.units, t.calendar = "days since 1950-01-01", "proleptic_gregorian"
    la = ds.createVariable("lat", "f8", ("lat",))
    la[:], la.units, la.standard_name = lat, "degrees_north", "latitude"
    lo = ds.createVariable("lon", "f8", ("lon",))
    lo[:], lo.units, lo.standard_name = lon, "degrees_east", "longitude"
    return t


def write_year_cache(path: Path, res: str, year: int, fields: dict[str, np.ndarray]) -> None:
    tmp = path.with_name(path.name + ".part")
    with nc.Dataset(tmp, "w", format="NETCDF4") as ds:
        t = _write_axes(ds, res, unlimited_time=False)
        t[:] = nc.date2num([datetime.datetime(year, m, 1) for m in range(1, 13)], t.units, t.calendar)
        for name, data in fields.items():
            dims = {1: ("time",), 2: ("lat", "lon"), 3: ("time", "lat", "lon")}[data.ndim]
            v = ds.createVariable(name, "f4", dims, zlib=True, complevel=1, fill_value=np.float32(np.nan))
            v.units = OUT_VARS[name][0] if name in OUT_VARS else CACHE_UNITS.get(name, "1")
            v[:] = data
    tmp.rename(path)


def build_year(year: int) -> None:
    out_paths = {res: CACHE_DIR / res / f"era5land_monthly_{year}.nc" for res in RESOLUTIONS}
    if all(p.exists() for p in out_paths.values()):
        LOG.info(f"{year}: all cache files exist, nothing to do")
        return
    for p in out_paths.values():
        p.parent.mkdir(parents=True, exist_ok=True)

    months = month_index(year)
    ndays = len(months)
    cache_vars = list(DIRECT) + ["swvis_srf_down", "vap_press", "press_coverage"]
    out = {res: {v: np.full((12, int(NLAT / f), int(NLON / f)), np.nan, np.float32) for v in cache_vars}
           for res, f in RESOLUTIONS.items()}
    land_frac = {res: np.zeros((int(NLAT / f), int(NLON / f)), np.float32) for res, f in RESOLUTIONS.items()}

    # Shortwave, dewpoint and pressure fall back to the CDS ERA5-Land monthly
    # means when the archive has no daily file for the year (2025). vap_press
    # is then e(monthly-mean dewpoint) rather than the mean of daily e.
    archive = {"press_srf": src_path("sp", "an", year), "d2m": src_path("d2m", "an", year),
               "ssrd": src_path("ssrd", "fc", year)}
    from_cds = {k: load_cds_monthly({"press_srf": "sp"}.get(k, k), year)
                for k, path in archive.items() if not path.exists() or k in CDS_OVERRIDE.get(year, ())}
    if from_cds:
        LOG.info(f"{year}: no archive daily file for {sorted(from_cds)}, using CDS ERA5-Land monthly means")
    handles = {v: open_var(src_path(folder, kind, year), folder) for v, (folder, kind) in DIRECT.items()
               if v not in from_cds}
    for k in ("d2m", "ssrd"):
        if k not in from_cds:
            handles[k] = open_var(archive[k], k)
    for name, (_, var) in handles.items():
        if var.shape[1:] != (NLAT, NLON) or (name != "ssrd" and var.shape[0] != ndays):
            raise ValueError(f"{year} {name}: shape {var.shape}, expected {(ndays, NLAT, NLON)}")
    # ssrd is incomplete in some years of the archive (1968: 31 Aug-30 Sep only,
    # 1972: from 31 Jan): place days by date, use only fully covered months,
    # and take the other months from ERA5 below.
    if "ssrd" in from_cds:
        sw_complete = np.ones(12, bool)
    else:
        ss_months = months[file_day_of_year(handles["ssrd"][0], year)]
        sw_complete = np.array([np.sum(ss_months == m) == np.sum(months == m) for m in range(12)])

    t_start = time.time()
    for b0 in range(0, NLAT, BAND_ROWS):
        b1 = b0 + BAND_ROWS
        land = np.isfinite(clean(handles["t_air_max"][1][0, b0:b1, :]))
        monthly = {}
        for v in DIRECT:
            if v in from_cds:                     # press_srf as monthly means
                p = from_cds[v][:, b0:b1].copy()
                p[:, ~land] = np.nan
                cov = np.isfinite(p).astype(np.float32)
                cov[:, ~land] = np.nan
                monthly["press_coverage"], monthly[v] = cov, p
                continue
            daily = clean(handles[v][1][:, b0:b1, :])
            daily[:, ~land] = np.nan
            if v == "precip_total":
                daily = np.maximum(daily, 0.0)
            if v == "press_srf":
                # share of land pixels with every day of the month present
                cov = monthly_complete(daily, months).astype(np.float32)
                cov[:, ~land] = np.nan
                monthly["press_coverage"] = cov
            monthly[v] = monthly_mean(daily, months)
        if "d2m" in from_cds:
            e = vapour_pressure_from_dewpoint(from_cds["d2m"][:, b0:b1].astype(np.float64)).astype(np.float32)
            e[:, ~land] = np.nan
            monthly["vap_press"] = e
        else:
            d2m = clean(handles["d2m"][1][:, b0:b1, :])
            d2m[:, ~land] = np.nan
            monthly["vap_press"] = monthly_mean(vapour_pressure_from_dewpoint(d2m.astype(np.float64)), months)
            del d2m
        if "ssrd" in from_cds:
            # monthly means, already on the cell-centred grid (no half-row shift)
            ss = fill_from_neighbours(from_cds["ssrd"][:, b0:b1] / SECONDS_PER_DAY, land[None])
            ss[:, ~land] = np.nan
            monthly["swvis_srf_down"] = ss
        else:
            # ssrd: half-pixel latitude offset -> mean of rows k and k+1 (labels 90.0-0.1k)
            r1 = min(b1 + 1, NLAT)
            ss = clean(handles["ssrd"][1][:, b0:r1, :])
            if ss.shape[1] == BAND_ROWS:          # last band: repeat the final row
                ss = np.concatenate([ss, ss[:, -1:]], axis=1)
            ss = pair_mean_rows(ss) / SECONDS_PER_DAY
            # ~0.3% of land pixels lie outside ssrd's own land mask: borrow from neighbours
            ss = fill_from_neighbours(ss, land[None])
            ss[:, ~land] = np.nan
            monthly["swvis_srf_down"] = monthly_mean(ss, ss_months)
            monthly["swvis_srf_down"][~sw_complete] = np.nan
        del ss

        for res, f in RESOLUTIONS.items():
            r0, rr = int(b0 / f), int(BAND_ROWS / f)
            for v, data in monthly.items():
                out[res][v][:, r0:r0 + rr] = coarsen(data, f)
            land_frac[res][r0:r0 + rr] = coarsen(land.astype(np.float32), f)
        LOG.info(f"{year}: band {b0}-{b1} done ({b1 / NLAT:.0%}, {time.time() - t_start:.0f}s)")

    for ds, _ in handles.values():
        ds.close()

    if "ssrd" in from_cds:
        # The CDS ERA5-Land monthly means are not reliable for every month
        # (Jan/Feb 2024 ssrd came back ~45% low, while ERA5 and the archive's
        # daily ERA5-Land agreed). ERA5-Land shortwave is ERA5's, so any month
        # whose land mean is off by more than 2% is replaced by ERA5 below.
        era = interp_era5("swvis_srf_down", year, "0.1deg")
        got = out["0.1deg"]["swvis_srf_down"]
        for m in range(12):
            ok = np.isfinite(got[m]) & np.isfinite(era[m])
            ratio = float(np.mean(got[m][ok]) / np.mean(era[m][ok]))
            if abs(ratio - 1.0) > 0.02:
                LOG.warning(f"{year}: CDS shortwave month {m + 1} is {ratio:.3f} x ERA5, using ERA5 instead")
                sw_complete[m] = False
    if not sw_complete.all():
        LOG.info(f"{year}: shortwave months {np.nonzero(~sw_complete)[0] + 1} from ERA5")
    for res in RESOLUTIONS:
        lw = interp_era5("lw_srf_down", year, res)
        lw[:, land_frac[res] == 0] = np.nan
        fields = dict(out[res])
        fields["lw_srf_down"] = lw
        if not sw_complete.all():
            sw = interp_era5("swvis_srf_down", year, res)
            sw[:, land_frac[res] == 0] = np.nan
            fields["swvis_srf_down"][~sw_complete] = sw[~sw_complete]
        fields["swvis_from_era5"] = (~sw_complete).astype(np.float32)
        fields["land_fraction"] = land_frac[res]
        write_year_cache(out_paths[res], res, year, fields)
        LOG.info(f"{year}: wrote {out_paths[res]}")


def _cache_files(res: str) -> list[Path]:
    years = range(START_YEAR, END_YEAR + 1)
    files = [CACHE_DIR / res / f"era5land_monthly_{y}.nc" for y in years]
    missing = [y for y, f in zip(years, files) if not f.exists()]
    if missing:
        raise FileNotFoundError(f"{res}: no cache file for years {missing}")
    return files


def _create_output(path: Path, res: str, var: str, cache0: Path):
    """Open a merged output file with axes, the variable and land_fraction."""
    units, long_name = OUT_VARS[var]
    ds = nc.Dataset(path, "w", format="NETCDF4")
    t = _write_axes(ds, res, unlimited_time=True)
    ny, nx = len(ds.dimensions["lat"]), len(ds.dimensions["lon"])
    # (12 months, 90 x 90 cells): whole years per chunk keeps both map reads
    # and single-site time-series reads cheap at every resolution.
    v = ds.createVariable(var, "f4", ("time", "lat", "lon"), zlib=True, complevel=4,
                          chunksizes=(12, min(90, ny), min(90, nx)), fill_value=np.float32(np.nan))
    v.units, v.long_name = units, long_name
    v.source = ("ERA5 monthly (CDS), bilinear to cell centres" if var == "lw_srf_down"
                else "ERA5-Land daily 0.1deg, BGC archive /Net/Groups/data_BGC/era5_land/e1/0d10_daily")
    lf = ds.createVariable("land_fraction", "f4", ("lat", "lon"), zlib=True, complevel=4)
    lf.long_name = "fraction of 0.1deg ERA5-Land land pixels in cell"
    with nc.Dataset(cache0) as src:
        src.set_auto_mask(False)
        lf[:] = src["land_fraction"][:]
    ds.title = f"ERA5-Land monthly forcing, {res}"
    ds.history = f"created {time.strftime('%Y-%m-%d %H:%M')} by build_era5land_monthly.py"
    return ds, t, v


def merge_plain(var: str) -> None:
    for res in RESOLUTIONS:
        out = OUT_DIR / res / f"era5land_{var}_{START_YEAR}-{END_YEAR}_monthly.nc"
        if out.exists():
            LOG.info(f"{out} exists, skipping")
            continue
        files = _cache_files(res)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(out.name + ".part")
        ds, t, v = _create_output(tmp, res, var, files[0])
        flag = None
        if var == "swvis_srf_down":
            flag = ds.createVariable("swvis_srf_down_from_era5", "i1", ("time",))
            flag.long_name = ("1 for months where the ERA5-Land archive's daily ssrd was incomplete and the "
                              "ERA5 monthly shortwave (bilinear to cell centres) was used instead")
        with ds:
            for i, f in enumerate(files):
                with nc.Dataset(f) as src:
                    src.set_auto_mask(False)
                    sl = slice(i * 12, (i + 1) * 12)
                    t[sl] = src["time"][:]
                    v[sl] = src[var][:]
                    if flag is not None:
                        flag[sl] = (src["swvis_from_era5"][:] if "swvis_from_era5" in src.variables
                                    else np.zeros(12)).astype(np.int8)
        tmp.rename(out)
        LOG.info(f"wrote {out}")


def merge_press_q() -> None:
    """press_srf with incomplete cells replaced by the same-calendar-month
    mean over complete years, and q_air from vapour pressure + that pressure."""
    for res in RESOLUTIONS:
        out_p = OUT_DIR / res / f"era5land_press_srf_{START_YEAR}-{END_YEAR}_monthly.nc"
        out_q = OUT_DIR / res / f"era5land_q_air_{START_YEAR}-{END_YEAR}_monthly.nc"
        if out_p.exists() and out_q.exists():
            LOG.info(f"{res}: press_srf and q_air exist, skipping")
            continue
        files = _cache_files(res)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # pass 1: climatology of complete months
        clim_sum = clim_n = None
        for f in files:
            with nc.Dataset(f) as src:
                src.set_auto_mask(False)
                p = src["press_srf"][:].astype(np.float64)
                complete = src["press_coverage"][:] >= 1.0 - 1e-6
            if clim_sum is None:
                clim_sum, clim_n = np.zeros_like(p), np.zeros(p.shape, np.int32)
            clim_sum += np.where(complete, p, 0.0)
            clim_n += complete
        with np.errstate(invalid="ignore", divide="ignore"):
            clim = (clim_sum / clim_n).astype(np.float32)
        del clim_sum

        # pass 2: write gap-filled pressure, flag, and q
        tmp_p, tmp_q = (o.with_name(o.name + ".part") for o in (out_p, out_q))
        dp, tp_, vp = _create_output(tmp_p, res, "press_srf", files[0])
        dq, tq, vq = _create_output(tmp_q, res, "q_air", files[0])
        ny, nx = len(dp.dimensions["lat"]), len(dp.dimensions["lon"])
        flag = dp.createVariable("press_srf_gapfilled", "i1", ("time", "lat", "lon"), zlib=True, complevel=4,
                                 chunksizes=(12, min(90, ny), min(90, nx)))
        flag.long_name = ("1 where the cell's land pixels did not all have surface pressure on every day of "
                          "the month in the source, and the same-calendar-month mean over complete years "
                          "was used instead")
        n_filled = n_unfillable = 0
        with dp, dq:
            for i, f in enumerate(files):
                with nc.Dataset(f) as src:
                    src.set_auto_mask(False)
                    times = src["time"][:]
                    p = src["press_srf"][:]
                    complete = src["press_coverage"][:] >= 1.0 - 1e-6
                    e = src["vap_press"][:]
                    land = src["land_fraction"][:] > 0
                fill = ~complete & land[None]
                p = np.where(fill, clim, p).astype(np.float32)
                n_filled += int(fill.sum())
                n_unfillable += int((fill & ~np.isfinite(clim)).sum())
                sl = slice(i * 12, (i + 1) * 12)
                tp_[sl] = times
                tq[sl] = times
                vp[sl] = p
                flag[sl] = fill.astype(np.int8)
                vq[sl] = specific_humidity(e.astype(np.float64), p.astype(np.float64)).astype(np.float32)
        tmp_p.rename(out_p)
        tmp_q.rename(out_q)
        LOG.info(f"wrote {out_p} and {out_q}: {n_filled} cell-months gap-filled, "
                 f"{n_unfillable} without any complete year (left NaN)")


def main() -> None:
    global END_YEAR
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    y = sub.add_parser("year")
    y.add_argument("year", type=int)
    m = sub.add_parser("merge")
    m.add_argument("var", choices=MERGE_TASKS)
    m.add_argument("--end-year", type=int, default=END_YEAR,
                   help=f"last year to merge (default {END_YEAR}; 2025 needs the CDS monthly download)")
    args = ap.parse_args()
    if args.cmd == "merge":
        END_YEAR = args.end_year
    if args.cmd == "year":
        build_year(args.year)
    elif args.var == "press_q":
        merge_press_q()
    else:
        merge_plain(args.var)


if __name__ == "__main__":
    main()
