#!/usr/bin/env python3
"""
Coarsen TerraClimate's native 1/24deg (~4km) monthly grid down to 0.5deg,
matching ERA5/GLDAS's native grid -- pure local reprocessing of the
already-converted monthly files under driver_data/terraclimate/monthly/4km/,
no new downloads.

Why this exists: TerraClimate's native grid (4320x8640, 1/24deg) is ~144x
finer than ERA5/GLDAS's 0.5deg grid that global_forcing_builder.py's
MetSourceConfig writes the global forcing product at. A single time-varying
variable at native resolution is ~120GB uncompressed for the full
1958-2025 record -- building a global QUINCY forcing product at that
resolution isn't practical or comparable to the ERA5/GLDAS products.
Block-averaging 12x12 native cells into one 0.5deg cell (4320/12=360,
8640/12=720, exact -- confirmed against the DEM's own coordinate grid, and
enforced here via boundary="exact" so a future TerraClimate grid change
fails loudly instead of silently truncating a row/column) brings every
variable down to the same order of magnitude as ERA5/GLDAS.

This also derives press_srf and q_air directly AT 0.5deg, instead of
reusing derive_terraclimate_humidity_pressure.py's native-resolution
output -- that script's final concat+write step was found hung (zero I/O
progress for minutes, confirmed via /proc/<pid>/io) writing a single
~120GB file, most likely an HDF5-on-NFS locking issue from holding 68
yearly file handles open simultaneously against this cluster's networked
filesystem. Deriving straight from the already-coarsened elevation/vap
fields sidesteps that file-size problem entirely.

Unit conversions are baked into the output here (not left to
global_forcing_builder.py's MetSourceConfig.unit_override), so
TERRACLIMATE_MET can reuse the exact same builder code path as
ERA5_MET/GLDAS_MET without special-casing:
  - t_air: (tmax+tmin)/2, degC -> K (+273.15)
  - rain: ppt (mm/month accumulated) -> mm/day (divide by days-in-month)
  - press_srf: kPa -> Pa (x1000), so the SAME unit_override=(0.01,"hPa")
    entry already used for ERA5/GLDAS's Pa-native press_srf works unchanged
  - swvis_srf_down (from srad) and wind_air (from ws): already native
    W/m2 and m/s, matching ERA5/GLDAS -- no conversion needed.
  - q_air: kg/kg (specific_humidity_from_vapor_pressure's native output),
    same as ERA5's q_air -- reuses ERA5_MET's (1000.0, "g kg-1") override.

TerraClimate does not report longwave radiation or cloud cover at all, so
those two QUINCY forcing variables simply aren't available from this
source -- TERRACLIMATE_MET's variable list (build_global_forcing_terraclimate.py)
omits them rather than fabricating a value.

Usage:
  cd conversion
  python coarsen_terraclimate_to_0.5deg.py --start-year 1958 --end-year 2025
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_logger, specific_humidity_from_vapor_pressure, standard_atmosphere_pressure_kpa

LOG = get_logger("terraclimate-coarsen")

DEFAULT_OUT_DIR = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/terraclimate")
COARSEN_FACTOR = 12  # 1/24deg -> 0.5deg (4320/12=360, 8640/12=720, exact)
ALL_OUTPUT_VARS = ["t_air", "rain", "swvis_srf_down", "wind_air", "press_srf", "q_air", "t_air_min", "t_air_max"]


def _coarsen(da: xr.DataArray) -> xr.DataArray:
    return da.coarsen(lat=COARSEN_FACTOR, lon=COARSEN_FACTOR, boundary="exact").mean()


def _find_monthly_file(monthly_dir: Path, var: str) -> Path:
    matches = sorted(monthly_dir.glob(f"terraclimate_{var}_*_monthly.nc"))
    if not matches:
        raise SystemExit(f"No terraclimate_{var}_*_monthly.nc found under {monthly_dir}")
    return matches[-1]


def _load_dem(raw_dir: Path) -> xr.DataArray:
    dem_path = raw_dir / "ancillary" / "terraclim_dem.nc"
    if not dem_path.exists():
        raise SystemExit(f"{dem_path} not found -- run download_terraclimate_monthly.py --with-dem first.")
    ds = xr.open_dataset(dem_path)
    return ds["elevation"]


def process(start_year: int, end_year: int, raw_dir: Path, monthly_4km_dir: Path, out_dir: Path,
            variables: list[str] | None = None) -> None:
    variables = set(variables) if variables else set(ALL_OUTPUT_VARS)
    out_subdir = out_dir / "monthly" / "0.5deg"
    out_subdir.mkdir(parents=True, exist_ok=True)
    time_slice = slice(f"{start_year}-01-01", f"{end_year}-12-31")

    def out_path(var):
        return out_subdir / f"terraclimate_{var}_{start_year}-{end_year}_monthly.nc"

    def already_done(var):
        p = out_path(var)
        if p.exists():
            LOG.info(f"  already have {p.name}, skipping")
            return True
        return False

    if "t_air" in variables and not already_done("t_air"):
        tmax = xr.open_dataset(_find_monthly_file(monthly_4km_dir, "tmax"), chunks={"time": 12})["tmax"].sel(time=time_slice)
        tmin = xr.open_dataset(_find_monthly_file(monthly_4km_dir, "tmin"), chunks={"time": 12})["tmin"].sel(time=time_slice)
        t_air = _coarsen((tmax + tmin) / 2.0 + 273.15)
        t_air.attrs = {"units": "K", "long_name": "near-surface air temperature ((tmax+tmin)/2)"}
        LOG.info("  coarsening t_air...")
        t_air.load().to_dataset(name="t_air").to_netcdf(
            out_path("t_air"), encoding={"t_air": {"zlib": True, "complevel": 4}})
        LOG.info(f"  wrote {out_path('t_air')}")

    if "rain" in variables and not already_done("rain"):
        ppt = xr.open_dataset(_find_monthly_file(monthly_4km_dir, "ppt"), chunks={"time": 12})["ppt"].sel(time=time_slice)
        rain = _coarsen(ppt / ppt["time"].dt.days_in_month)
        rain.attrs = {"units": "mm day-1", "long_name": "Total precipitation"}
        LOG.info("  coarsening rain...")
        rain.load().to_dataset(name="rain").to_netcdf(
            out_path("rain"), encoding={"rain": {"zlib": True, "complevel": 4}})
        LOG.info(f"  wrote {out_path('rain')}")

    if "swvis_srf_down" in variables and not already_done("swvis_srf_down"):
        srad = xr.open_dataset(_find_monthly_file(monthly_4km_dir, "srad"), chunks={"time": 12})["srad"].sel(time=time_slice)
        swvis = _coarsen(srad)
        swvis.attrs = {"units": "W m-2", "long_name": "Visible-band surface downward shortwave radiation"}
        LOG.info("  coarsening swvis_srf_down...")
        swvis.load().to_dataset(name="swvis_srf_down").to_netcdf(
            out_path("swvis_srf_down"), encoding={"swvis_srf_down": {"zlib": True, "complevel": 4}})
        LOG.info(f"  wrote {out_path('swvis_srf_down')}")

    if "wind_air" in variables and not already_done("wind_air"):
        ws = xr.open_dataset(_find_monthly_file(monthly_4km_dir, "ws"), chunks={"time": 12})["ws"].sel(time=time_slice)
        wind_air = _coarsen(ws)
        wind_air.attrs = {"units": "m s-1", "long_name": "Wind speed"}
        LOG.info("  coarsening wind_air...")
        wind_air.load().to_dataset(name="wind_air").to_netcdf(
            out_path("wind_air"), encoding={"wind_air": {"zlib": True, "complevel": 4}})
        LOG.info(f"  wrote {out_path('wind_air')}")

    if "t_air_min" in variables and not already_done("t_air_min"):
        tmin = xr.open_dataset(_find_monthly_file(monthly_4km_dir, "tmin"), chunks={"time": 12})["tmin"].sel(time=time_slice)
        t_air_min = _coarsen(tmin + 273.15)
        t_air_min.attrs = {"units": "K", "long_name": "monthly mean of daily minimum 2m air temperature"}
        LOG.info("  coarsening t_air_min...")
        t_air_min.load().to_dataset(name="t_air_min").to_netcdf(
            out_path("t_air_min"), encoding={"t_air_min": {"zlib": True, "complevel": 4}})
        LOG.info(f"  wrote {out_path('t_air_min')}")

    if "t_air_max" in variables and not already_done("t_air_max"):
        tmax = xr.open_dataset(_find_monthly_file(monthly_4km_dir, "tmax"), chunks={"time": 12})["tmax"].sel(time=time_slice)
        t_air_max = _coarsen(tmax + 273.15)
        t_air_max.attrs = {"units": "K", "long_name": "monthly mean of daily maximum 2m air temperature"}
        LOG.info("  coarsening t_air_max...")
        t_air_max.load().to_dataset(name="t_air_max").to_netcdf(
            out_path("t_air_max"), encoding={"t_air_max": {"zlib": True, "complevel": 4}})
        LOG.info(f"  wrote {out_path('t_air_max')}")

    need_press = "press_srf" in variables and not already_done("press_srf")
    need_q = "q_air" in variables and not already_done("q_air")
    if need_press or need_q:
        elevation_coarse = _coarsen(_load_dem(raw_dir)).load()
        pressure_kpa = standard_atmosphere_pressure_kpa(elevation_coarse)

        if need_press:
            press_pa = pressure_kpa * 1000.0
            press_pa.attrs = {
                "units": "Pa",
                "long_name": "surface pressure (derived from elevation, standard atmosphere)",
                "comment": pressure_kpa.attrs.get("comment", ""),
            }
            press_pa.to_dataset(name="press_srf").to_netcdf(
                out_path("press_srf"), encoding={"press_srf": {"zlib": True, "complevel": 4}})
            LOG.info(f"  wrote {out_path('press_srf')}")

        if need_q:
            vap = xr.open_dataset(_find_monthly_file(monthly_4km_dir, "vap"), chunks={"time": 12})["vap"].sel(time=time_slice)
            LOG.info("  coarsening vap for q_air derivation...")
            vap_coarse = _coarsen(vap).load()
            q_air = specific_humidity_from_vapor_pressure(vap_coarse, pressure_kpa)
            q_air.load().to_dataset(name="q_air").to_netcdf(
                out_path("q_air"), encoding={"q_air": {"zlib": True, "complevel": 4}})
            LOG.info(f"  wrote {out_path('q_air')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--monthly-4km-dir", type=Path, default=None)
    parser.add_argument("--variables", nargs="+", choices=ALL_OUTPUT_VARS, default=None,
                         help=f"Subset of {ALL_OUTPUT_VARS} to build (default: all). Each is fully "
                              f"independent I/O-wise (reads its own source file(s), writes its own "
                              f"output) -- run several as separate parallel processes to use more "
                              f"of an idle, high-core/high-RAM machine's I/O concurrency than a "
                              f"single sequential run can.")
    args = parser.parse_args()

    raw_dir = args.raw_dir or (args.out_dir / "raw")
    monthly_4km_dir = args.monthly_4km_dir or (args.out_dir / "monthly" / "4km")
    process(args.start_year, args.end_year, raw_dir, monthly_4km_dir, args.out_dir, variables=args.variables)
    LOG.info("Done.")


if __name__ == "__main__":
    main()
