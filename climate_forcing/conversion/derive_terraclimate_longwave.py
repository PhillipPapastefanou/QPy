#!/usr/bin/env python3
"""
Derive TerraClimate downward longwave (lw_srf_down, W m-2) at 0.5deg from
TerraClimate's own tmin/tmax, humidity and shortwave -- no external
longwave source, so the field stays consistent with the rest of the dataset.

TerraClimate reports neither longwave nor cloud cover. The derivation is
the standard empirical chain (as in FAO-56 net longwave):

  1. vapour pressure e back from q_air and press_srf (both already derived
     by derive_terraclimate_humidity_pressure.py / the 0.5deg coarsening):
         e = q p / (0.622 + 0.378 q)
  2. clear-sky emissivity, Prata (1996):
         w = 46.5 e[hPa] / T,  eps_clr = 1 - (1 + w) exp(-sqrt(1.2 + 3 w))
  3. cloud fraction from shortwave transmissivity, Crawford & Duchon (1999):
         c = clip(1 - Rs / Rso, 0, 1),  Rso = (0.75 + 2e-5 z) Ra  (FAO-56)
     with Ra the monthly-mean top-of-atmosphere insolation and z the
     elevation inverted from the standard-atmosphere press_srf.
     Where Ra <= 50 W m-2 (polar night / very low sun) Rs/Rso is meaningless,
     so c is the cell's mean c over that year's sunlit months (global mean
     of that year if the cell never has Ra > 50); such months are flagged in
     lw_srf_down_cloud_fallback.
  4. all-sky emissivity eps = c + (1 - c) eps_clr, and
         lw = eps sigma T_eff^4,  T_eff = tmin + (tmax - tmin) / 3

T_eff: Prata/Crawford-Duchon use a single air temperature. With the daily
mean (tmin+tmax)/2 the result is ~11 W m-2 too high against ERA5, almost
entirely over warm, dry, large-diurnal-range regions (20 W m-2 at 0-30N),
where screen-level tmax overstates the temperature of the emitting
boundary layer. Weighting towards tmin removes that (choice fixed on 2010
against ERA5 longwave; see README in the output folder for the per-year
validation). Formulation comparison on 2010, land, cos(lat)-weighted vs ERA5:
    Brutsaert clear-sky, Tmean        bias  +3.7  rmse 20.2  (60-90 band -27)
    Prata, CD, Tmean                  bias +11.1  rmse 18.9
    Prata, CD, tmin + dtr/3 (chosen)  bias  +2.8  rmse 14.0

Usage:
  cd conversion
  python derive_terraclimate_longwave.py --start-year 1958 --end-year 2025
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import netCDF4 as nc
import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_logger
from checks.forcing_checks import toa_monthly_insolation

LOG = get_logger("terraclimate-longwave")

DEFAULT_DIR = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/terraclimate/monthly/0.5deg")
ERA5_LW = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/era5_land/monthly/0.5deg/"
               "era5land_lw_srf_down_1950-2024_monthly.nc")  # ERA5 longwave on the same 0.5deg cells
SIGMA = 5.670374e-8
RA_MIN = 50.0         # W m-2; below this the shortwave-based cloud fraction is not used
RSO_A = 0.75          # FAO-56 clear-sky transmissivity at sea level
TEFF_WEIGHT = 1 / 3   # T_eff = tmin + TEFF_WEIGHT * (tmax - tmin)


def elevation_from_pressure(p_pa: np.ndarray) -> np.ndarray:
    """Inverse of common.standard_atmosphere_pressure_kpa."""
    return (1.0 - (p_pa / 101325.0) ** (1 / 5.25588)) / 2.25577e-5


def prata_clear_sky_emissivity(e_hpa: np.ndarray, t_k: np.ndarray) -> np.ndarray:
    w = 46.5 * e_hpa / t_k
    return 1.0 - (1.0 + w) * np.exp(-np.sqrt(1.2 + 3.0 * w))


def cloud_fraction(sw: np.ndarray, ra: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(time, lat, lon) cloud fraction from shortwave transmissivity, and the
    boolean fallback mask (months where Ra is too small to use)."""
    rso = (RSO_A + 2e-5 * z) * ra
    sunlit = np.broadcast_to(ra > RA_MIN, sw.shape)
    with np.errstate(invalid="ignore", divide="ignore"):
        c = np.clip(1.0 - np.where(sunlit, sw / rso, np.nan), 0.0, 1.0)
        cbar = np.nanmean(np.where(sunlit, c, np.nan), axis=0, keepdims=True)
    cbar = np.where(np.isfinite(cbar), cbar, np.nanmean(c))
    c = np.where(sunlit, c, np.broadcast_to(cbar, c.shape))
    c = np.where(np.isfinite(sw), c, np.nan)
    return c, ~sunlit


def longwave(tmin, tmax, q, sw, p, ra):
    e_pa = q * p / (0.622 + 0.378 * q)
    eps_clr = prata_clear_sky_emissivity(e_pa / 100.0, 0.5 * (tmin + tmax))
    c, fallback = cloud_fraction(sw, ra, elevation_from_pressure(p))
    t_eff = tmin + TEFF_WEIGHT * (tmax - tmin)
    lw = (c + (1.0 - c) * eps_clr) * SIGMA * t_eff ** 4
    return lw, fallback & np.isfinite(lw)


def validate_year(lw: np.ndarray, year: int, lat: np.ndarray, ref) -> str:
    if ref is None or not (ref.time.dt.year == year).any():
        return "no ERA5 reference"
    r = ref.sel(time=str(year)).values
    m = np.isfinite(lw) & np.isfinite(r)
    w = np.broadcast_to(np.cos(np.deg2rad(lat))[None, :, None], lw.shape)[m]
    d = (lw - r)[m]
    return (f"vs ERA5: bias {np.average(d, weights=w):+.1f} rmse {np.sqrt(np.average(d**2, weights=w)):.1f} "
            f"r {np.corrcoef(lw[m], r[m])[0, 1]:.3f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start-year", type=int, default=1958)
    ap.add_argument("--end-year", type=int, default=2025)
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = ap.parse_args()

    tag = f"{args.start_year}-{args.end_year}"
    src = {v: xr.open_dataset(args.dir / f"terraclimate_{v}_1958-2025_monthly.nc")[v]
           for v in ["t_air_min", "t_air_max", "q_air", "swvis_srf_down"]}
    p = xr.open_dataset(args.dir / "terraclimate_press_srf_1958-2025_monthly.nc")["press_srf"].values
    lat = src["q_air"].lat.values
    lon = src["q_air"].lon.values
    ref = xr.open_dataset(ERA5_LW)["lw_srf_down"] if ERA5_LW.exists() else None

    out = args.dir / f"terraclimate_lw_srf_down_{tag}_monthly.nc"
    part = out.with_name(out.name + ".part")
    ds = nc.Dataset(part, "w")
    ds.createDimension("time", None)
    ds.createDimension("lat", len(lat))
    ds.createDimension("lon", len(lon))
    for name, vals, attrs in [("lat", lat, {"units": "degrees_north", "standard_name": "latitude"}),
                              ("lon", lon, {"units": "degrees_east", "standard_name": "longitude"})]:
        v = ds.createVariable(name, "f8", (name,))
        v[:] = vals
        v.setncatts(attrs)
    t = ds.createVariable("time", "f8", ("time",))
    t.setncatts({"units": "days since 1900-01-01", "calendar": "gregorian", "standard_name": "time"})
    lwv = ds.createVariable("lw_srf_down", "f4", ("time", "lat", "lon"), zlib=True, complevel=4,
                            chunksizes=(12, 90, 90), fill_value=np.float32(np.nan))
    lwv.setncatts({
        "units": "W m-2",
        "long_name": "surface downward longwave radiation (derived)",
        "comment": "Prata (1996) clear-sky emissivity, Crawford & Duchon (1999) cloud fraction from "
                   "shortwave transmissivity (FAO-56 Rso), T_eff = tmin + (tmax-tmin)/3; "
                   "see conversion/derive_terraclimate_longwave.py",
    })
    flag = ds.createVariable("lw_srf_down_cloud_fallback", "i1", ("time", "lat", "lon"), zlib=True,
                             complevel=4, chunksizes=(12, 90, 90))
    flag.setncatts({"long_name": "1 = month too dark (TOA < 50 W m-2) for a shortwave cloud estimate; "
                                 "cloud fraction is the cell's mean over that year's sunlit months"})
    ds.setncatts({"title": "TerraClimate-derived downward longwave radiation, 0.5deg monthly",
                  "source": "TerraClimate tmin, tmax, vap (via q_air), srad, elevation (via press_srf)"})

    n = 0
    for year in range(args.start_year, args.end_year + 1):
        sl = slice(f"{year}-01", f"{year}-12")
        tmin, tmax, q, sw = (src[v].sel(time=sl).values for v in ["t_air_min", "t_air_max", "q_air", "swvis_srf_down"])
        ra = np.stack([toa_monthly_insolation(lat, year, m) for m in range(1, 13)])[:, :, None]
        lw, fb = longwave(tmin, tmax, q, sw, p, ra)
        k = len(tmin)
        lwv[n:n + k] = lw.astype(np.float32)
        flag[n:n + k] = fb.astype(np.int8)
        times = [np.datetime64(x, "s").astype(object) for x in src["q_air"].sel(time=sl).time.values]
        t[n:n + k] = nc.date2num(times, t.units, t.calendar)
        n += k
        LOG.info(f"{year}: land range [{np.nanmin(lw):.0f}, {np.nanmax(lw):.0f}] W m-2, "
                 f"fallback {fb.sum() / max(np.isfinite(lw).sum(), 1):.3%}; {validate_year(lw, year, lat, ref)}")
    ds.close()
    part.rename(out)
    LOG.info(f"wrote {out}")


if __name__ == "__main__":
    main()
