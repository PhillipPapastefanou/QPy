"""3x3 grid of the 9 reference sites (same sites/layout as
climate_forcing/seasonal_cycles_9sites_2020.png), one panel per site,
comparing ERA5 vs GLDAS vs TerraClimate for a single variable/year.

Point extraction for ERA5/GLDAS goes through the Zarr companion stores
(fast point/timeseries access, see global_forcing_builder.py). TerraClimate
doesn't have an equivalent Zarr global-forcing store yet
(build_global_forcing_terraclimate.py is still a NotImplementedError stub)
-- instead this reads its already-built monthly NetCDF cache directly from
climate_forcing's driver_data/terraclimate/monthly/ output (see
climate_forcing/README.md), converting each variable's native units to the
same K / g kg-1 / hPa / m s-1 / W m-2 / mm day-1 convention the ERA5/GLDAS
Zarr stores already use.

Usage:
    python -m src.forcing.plot_seasonal_cycles_9sites \\
        --era5 /path/to/era5_global_forcing_0.5deg_1940-2025.zarr \\
        --gldas /path/to/gldas_global_forcing_0.5deg_2000-2025.zarr \\
        --year 2020 --output-dir climate_forcing

Plots the variables common to ERA5/GLDAS 1:1 (t_air, q_air, press_srf,
wind_air, swvis_srf_down, lw_srf_down), plus precip_total - compared as
ERA5's precip_total against GLDAS's "rain" output variable, which the
build pipeline already sums from GLDAS's separate rain+snow to match
QUINCY's "rain" convention of total precipitation (see GLDAS_MET.combine_vars
in global_forcing_builder.py). ERA5's cloud_cover has no GLDAS equivalent
at all, so is skipped.

TerraClimate has no downwelling longwave at all (not measured by that
product -- see download_terraclimate_monthly.py). All other TerraClimate
variables here, including t_air_min/t_air_max, are read from the final,
already-coarsened 0.5deg product (climate_forcing/conversion/
coarsen_terraclimate_to_0.5deg.py's output under driver_data/terraclimate/
monthly/0.5deg/), matching ERA5/GLDAS/CRU-JRA's own native 0.5deg grid --
not the native 1/24deg (4km) files, and not the older, since-superseded
derive_terraclimate_humidity_pressure.py output (that script's q_air/
press_srf were left at native 4km resolution and its final concat+write
step for the full record was found hung on this cluster's networked
filesystem -- see coarsen_terraclimate_to_0.5deg.py's own docstring;
press_srf is a static, time-invariant field either way -- elevation-based
standard-atmosphere pressure has no seasonal cycle in this approximation --
so it's broadcast across all 12 months here rather than skipped).

CRU-JRA v3.0 was plotted here too (2026-09-07) but removed the same day,
after its precipitation was confirmed wrong (17-32% of an independent
CRUNCEPv7 reference at every cross-checked site). Root-caused (2026-09-07)
to a missing CRU-TS bias-correction step: CEDA's own Computation Record
for v2.4/v2.5 documents precip as raw JRA-55 rescaled by a per-cell,
per-month (CRU TS total / JRA total) factor, and v3.0 has no such
Computation Record at all, unlike every documented CRU-JRA version --
consistent with v3.0's precip being that same raw, uncorrected JRA-55
field. v3.0's other variables (temperature, radiation, humidity, pressure,
wind) checked out fine against v2.5 -- only precip is broken. Added back
here as v2.5 instead (2026-09-07, at user's request), which has the
correct bias-corrected precip and the same good non-precip variables.
"""

import argparse
import calendar
import os
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import netCDF4
import numpy as np
import xarray as xr
import zarr

matplotlib.use("Agg")

from src.forcing.global_forcing_builder import nearest_index

# Same 9 sites/regions/biomes as climate_forcing/seasonal_cycles_9sites_2020.png
SITES = [
    ("Manaus, Brazil", "South America - Tropical rainforest", -3.10, -60.02),
    ("Tamanrasset, Algeria", "Africa - Hot desert (Sahara)", 22.79, 5.53),
    ("Serengeti, Tanzania", "Africa - Tropical savanna", -2.33, 34.83),
    ("Yakutsk, Russia", "Asia - Boreal forest/taiga", 62.03, 129.73),
    ("Ulaanbaatar, Mongolia", "Asia - Cold steppe/desert", 47.89, 106.91),
    ("Pontianak, Indonesia", "Asia - Tropical rainforest", -0.02, 109.34),
    ("Madrid, Spain", "Europe - Mediterranean", 40.42, -3.70),
    ("Kansas, USA", "North America - Temperate grassland", 38.50, -98.00),
    ("Alice Springs, Australia", "Australia - Arid/desert", -23.70, 133.88),
]

COMMON_VARIABLES = ["t_air", "q_air", "press_srf", "wind_air", "swvis_srf_down", "lw_srf_down"]

# (label, era5_var, gldas_vars-to-sum) - a plain 1:1 match for most
# variables. GLDAS's "rain" output already equals its rain+snow summed
# (done in the build pipeline, see GLDAS_MET.combine_vars), so precip_total
# is also a plain 1:1 match here.
VAR_SPECS = [(v, v, [v]) for v in COMMON_VARIABLES] + [("precip_total", "precip_total", ["rain"])]

# t_air_min/t_air_max: unlike every other variable here, neither ERA5 nor
# GLDAS has an entry in its global_forcing zarr for these (the zarr only
# carries what the neural-net climate emulator predicts, i.e. monthly-mean
# t_air, not tmin/tmax -- see PORT_NOTES_CLIMATE_EMULATOR.md in the QUINCY
# C++ port for why that gap exists and how it's derived here instead).
# era5_var/gldas_vars are None as a sentinel: plot_variable() reads these
# two straight from the derived files below (era5_derived_site_series /
# gldas_derived_site_series) rather than through a zarr group.
MIN_MAX_LABELS = ["t_air_min", "t_air_max"]
MIN_MAX_VAR_SPECS = [(label, None, None) for label in MIN_MAX_LABELS]

COLORS = {"ERA5": "tab:blue", "GLDAS": "tab:orange", "CRU-JRA": "tab:green", "TerraClimate": "tab:purple"}

DRIVER_ROOT = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data")
# Final, 0.5deg-coarsened TerraClimate only (see module docstring) -- not the
# native 4km monthly/4km/ files.
TERRACLIMATE_DIR = DRIVER_ROOT / "terraclimate" / "monthly" / "0.5deg"
CRUJRA_DIR = DRIVER_ROOT / "crujra" / "monthly" / "0.5deg"
GLDAS_DIR = DRIVER_ROOT / "gldas" / "monthly" / "0.5deg"
ERA5_DAILY_DIR = DRIVER_ROOT / "era5" / "daily" / "0.5deg"

# label -> (native variable, native file glob, unit-conversion fn or None).
# All already at 0.5deg (coarsen_terraclimate_to_0.5deg.py); lw_srf_down
# (not available at all) is handled specially below, not here. press_srf
# has no time dimension (static, elevation-derived) -- terraclimate_site_series()
# broadcasts it across all 12 months.
TERRACLIMATE_VARS = {
    "t_air": ("t_air", "terraclimate_t_air_*_monthly.nc", None),  # already K
    "q_air": ("q_air", "terraclimate_q_air_*_monthly.nc", lambda v: v * 1000.0),  # kg/kg -> g/kg
    "press_srf": ("press_srf", "terraclimate_press_srf_*_monthly.nc", lambda v: v * 0.01),  # Pa -> hPa
    "wind_air": ("wind_air", "terraclimate_wind_air_*_monthly.nc", None),  # already m/s
    "swvis_srf_down": ("swvis_srf_down", "terraclimate_swvis_srf_down_*_monthly.nc", None),  # already W/m2
    "precip_total": ("rain", "terraclimate_rain_*_monthly.nc", None),  # already mm/day
    "t_air_min": ("t_air_min", "terraclimate_t_air_min_*_monthly.nc", None),  # already K
    "t_air_max": ("t_air_max", "terraclimate_t_air_max_*_monthly.nc", None),  # already K
}

# GLDAS has no native tmin/tmax either; these come from
# climate_forcing/conversion/derive_gldas_tmin_tmax.py's local reprocessing
# of GLDAS's already-downloaded raw 3-hourly Tair_f_inst (approximate: 8
# synoptic samples/day, not a true continuous-record extreme -- see that
# script's own docstring). Already K, matching ERA5/GLDAS/CRU-JRA t_air.
GLDAS_DERIVED_VARS = {
    "t_air_min": ("t_air_min", "gldas_t_air_min_derived_*_monthly.nc", None),
    "t_air_max": ("t_air_max", "gldas_t_air_max_derived_*_monthly.nc", None),
}

# ERA5 has no tmin/tmax in the global_forcing zarr either (same reason as
# GLDAS above), but unlike GLDAS a real daily product exists via CDS's
# server-side daily-statistics service (download/download_era5_daily.py
# --groups tmax tmin) -- genuinely daily (one row/day), so read directly and
# resample to monthly mean-of-daily-max/min here, matching the
# mean-of-extremes convention CRU-JRA/TerraClimate's own tmin/tmax already
# use. Already K (ERA5 t2m is Kelvin).
ERA5_DERIVED_VARS = {
    "t_air_min": ("t_air_min", "era5_t_air_min_*_daily.nc"),
    "t_air_max": ("t_air_max", "era5_t_air_max_*_daily.nc"),
}

# label -> (native variable, native file glob, unit-conversion fn or None);
# uses v2.5, not v3.0 -- see docstring. t_air (native "tmp") is a plain
# read, no conversion (CRU-JRA temperature is already Kelvin, matching
# ERA5/GLDAS). wind_air is handled specially below (needs ugrd+vgrd
# combined, not a single file).
CRUJRA_VARS = {
    "t_air": ("tmp", "crujra_v2.5_tmp_*_monthly.nc", None),  # already K
    "q_air": ("spfh", "crujra_v2.5_spfh_*_monthly.nc", lambda v: v * 1000.0),  # kg/kg -> g/kg
    "press_srf": ("pres", "crujra_v2.5_pres_*_monthly.nc", lambda v: v * 0.01),  # Pa -> hPa
    "swvis_srf_down": ("dswrf", "crujra_v2.5_dswrf_*_monthly.nc", None),  # already W/m2
    "lw_srf_down": ("dlwrf", "crujra_v2.5_dlwrf_*_monthly.nc", None),  # already W/m2
    "precip_total": ("pre", "crujra_v2.5_pre_*_monthly.nc", "days_in_month"),  # mm/month -> mm/day
    "t_air_min": ("tmin", "crujra_v2.5_tmin_*_monthly.nc", None),  # already K
    "t_air_max": ("tmax", "crujra_v2.5_tmax_*_monthly.nc", None),  # already K
}


def year_month_index(zarr_group, year):
    time_num = zarr_group["time"][:]
    units = zarr_group["time"].attrs["units"]
    calendar_name = zarr_group["time"].attrs.get("calendar", "standard")
    dates = netCDF4.num2date(time_num, units, calendar_name)
    idx = [i for i, d in enumerate(dates) if d.year == year]
    if len(idx) != 12:
        raise ValueError(f"Expected 12 months for {year}, found {len(idx)} (check the source covers that year)")
    return idx


def site_series(zarr_group, var, lat, lon, month_idx):
    lat_arr = zarr_group["lat"][:]
    lon_arr = zarr_group["lon"][:]
    lat_idx = nearest_index(np.array([lat]), lat_arr)[0]
    lon_idx = nearest_index(np.array([lon]), lon_arr, wrap=360.0)[0]
    full = zarr_group[var][:, lat_idx, lon_idx]
    return np.array([full[i] for i in month_idx])


def site_series_sum(zarr_group, variables, lat, lon, month_idx):
    total = None
    for var in variables:
        vals = site_series(zarr_group, var, lat, lon, month_idx)
        total = vals if total is None else total + vals
    return total


def _latest_matching_file(directory: Path, pattern: str) -> Path | None:
    matches = sorted(directory.glob(pattern))
    return matches[-1] if matches else None


def _apply_days_in_month(vals: np.ndarray, year: int) -> np.ndarray:
    days = np.array([calendar.monthrange(year, m)[1] for m in range(1, 13)])
    return vals / days


def terraclimate_site_series(label: str, lat: float, lon: float, year: int):
    if label == "lw_srf_down":
        return None  # TerraClimate has no longwave radiation product at all
    if label not in TERRACLIMATE_VARS:
        return None
    var, pattern, conv = TERRACLIMATE_VARS[label]
    f = _latest_matching_file(TERRACLIMATE_DIR, pattern)
    if f is None:
        return None
    ds = xr.open_dataset(f)
    try:
        da = ds[var].sel(lon=lon, lat=lat, method="nearest")
        if "time" in da.dims:
            da = da.sel(time=str(year))
            if da.sizes.get("time", 0) != 12:
                return None
            vals = da.values.astype("float64")
        else:
            # static field (press_srf: elevation-based standard-atmosphere
            # estimate, no seasonal cycle in this approximation) -- same
            # value every month.
            vals = np.full(12, float(da.values))
    finally:
        ds.close()
    if conv == "days_in_month":
        vals = _apply_days_in_month(vals, year)
    elif conv is not None:
        vals = conv(vals)
    return vals


def crujra_wind_series(lat: float, lon: float, year: int):
    f_u = _latest_matching_file(CRUJRA_DIR, "crujra_v2.5_ugrd_*_monthly.nc")
    f_v = _latest_matching_file(CRUJRA_DIR, "crujra_v2.5_vgrd_*_monthly.nc")
    if f_u is None or f_v is None:
        return None
    ds_u, ds_v = xr.open_dataset(f_u), xr.open_dataset(f_v)
    try:
        u = ds_u["ugrd"].sel(lon=lon, lat=lat, method="nearest").sel(time=str(year))
        v = ds_v["vgrd"].sel(lon=lon, lat=lat, method="nearest").sel(time=str(year))
        if u.sizes.get("time", 0) != 12 or v.sizes.get("time", 0) != 12:
            return None
        speed = np.sqrt(u.values ** 2 + v.values ** 2)
    finally:
        ds_u.close()
        ds_v.close()
    return speed


def crujra_site_series(label: str, lat: float, lon: float, year: int):
    if label == "wind_air":
        return crujra_wind_series(lat, lon, year)
    if label not in CRUJRA_VARS:
        return None
    var, pattern, conv = CRUJRA_VARS[label]
    f = _latest_matching_file(CRUJRA_DIR, pattern)
    if f is None:
        return None
    ds = xr.open_dataset(f)
    try:
        da = ds[var].sel(lon=lon, lat=lat, method="nearest").sel(time=str(year))
        if da.sizes.get("time", 0) != 12:
            return None
        vals = da.values.astype("float64")
    finally:
        ds.close()
    if conv == "days_in_month":
        vals = _apply_days_in_month(vals, year)
    elif conv is not None:
        vals = conv(vals)
    return vals


def gldas_derived_site_series(label: str, lat: float, lon: float, year: int):
    if label not in GLDAS_DERIVED_VARS:
        return None
    var, pattern = GLDAS_DERIVED_VARS[label]
    f = _latest_matching_file(GLDAS_DIR, pattern)
    if f is None:
        return None
    ds = xr.open_dataset(f)
    try:
        da = ds[var].sel(lon=lon, lat=lat, method="nearest").sel(time=str(year))
        if da.sizes.get("time", 0) != 12:
            return None
        vals = da.values.astype("float64")
    finally:
        ds.close()
    return vals


def era5_derived_site_series(label: str, lat: float, lon: float, year: int):
    if label not in ERA5_DERIVED_VARS:
        return None
    var, pattern = ERA5_DERIVED_VARS[label]
    f = _latest_matching_file(ERA5_DAILY_DIR, pattern)
    if f is None:
        return None
    ds = xr.open_dataset(f)
    try:
        lon_coord = lon
        if float(ds["lon"].max()) > 180.0:  # 0-360 grid convention
            lon_coord = lon % 360.0
        da = ds[var].sel(lon=lon_coord, lat=lat, method="nearest").sel(time=str(year))
        monthly = da.resample(time="MS").mean()
        if monthly.sizes.get("time", 0) != 12:
            return None
        vals = monthly.values.astype("float64")
    finally:
        ds.close()
    return vals


def plot_variable(era5_group, gldas_group, era5_months, gldas_months, label, era5_var, gldas_vars, year, out_path):
    is_min_max = era5_var is None  # sentinel set by MIN_MAX_VAR_SPECS -- see its own comment
    units = "K" if is_min_max else era5_group[era5_var].attrs.get("units", "")
    fig, axes = plt.subplots(3, 3, figsize=(16, 12))
    fig.suptitle(f"{label} [{units}] across ERA5 / GLDAS / TerraClimate / CRU-JRA v2.5, 9 sites -- year {year}\n"
                 f"(single calendar year, not a climatological average)",
                 fontsize=13)

    months = np.arange(1, 13)
    for ax, (name, region, lat, lon) in zip(axes.flat, SITES):
        if is_min_max:
            era5_vals = era5_derived_site_series(label, lat, lon, year)
            if era5_vals is not None and not np.all(np.isnan(era5_vals)):
                ax.plot(months, era5_vals, label="ERA5", color=COLORS["ERA5"])
            else:
                ax.text(0.5, 0.12, f"ERA5: no {label} data for {year}",
                        transform=ax.transAxes, ha="center", va="bottom", fontsize=7, color="gray")

            gldas_vals = gldas_derived_site_series(label, lat, lon, year)
            if gldas_vals is not None and not np.all(np.isnan(gldas_vals)):
                ax.plot(months, gldas_vals, label="GLDAS", color=COLORS["GLDAS"])
            else:
                ax.text(0.5, 0.06, f"GLDAS: no {label} data for {year}",
                        transform=ax.transAxes, ha="center", va="bottom", fontsize=7, color="gray")
        else:
            era5_vals = site_series(era5_group, era5_var, lat, lon, era5_months)
            ax.plot(months, era5_vals, label="ERA5", color=COLORS["ERA5"])

            try:
                gldas_vals = site_series_sum(gldas_group, gldas_vars, lat, lon, gldas_months)
                if np.all(np.isnan(gldas_vals)):
                    raise ValueError("all-NaN (ocean/no-data in GLDAS's land-only grid)")
                ax.plot(months, gldas_vals, label="GLDAS", color=COLORS["GLDAS"])
            except (KeyError, ValueError):
                pass

        terra_vals = terraclimate_site_series(label, lat, lon, year)
        if terra_vals is not None and not np.all(np.isnan(terra_vals)):
            ax.plot(months, terra_vals, label="TerraClimate", color=COLORS["TerraClimate"])
        elif label == "lw_srf_down":
            ax.text(0.5, 0.06, "TerraClimate: no longwave data (not measured)",
                    transform=ax.transAxes, ha="center", va="bottom", fontsize=7, color="gray")

        crujra_vals = crujra_site_series(label, lat, lon, year)
        if crujra_vals is not None and not np.all(np.isnan(crujra_vals)):
            ax.plot(months, crujra_vals, label="CRU-JRA v2.5", color=COLORS["CRU-JRA"])

        ax.set_title(f"{name}\n{region}", fontsize=10, fontweight="bold")
        ax.set_xlabel("Month")
        ax.set_xticks(months)

    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=[0, 0.03, 1, 0.94])
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--era5", required=True, help="ERA5 global forcing .zarr path")
    p.add_argument("--gldas", required=True, help="GLDAS global forcing .zarr path")
    p.add_argument("--year", type=int, default=2020)
    p.add_argument("--output-dir", required=True)
    all_labels = [l for l, _, _ in VAR_SPECS] + MIN_MAX_LABELS
    p.add_argument("--variables", nargs="+", default=None,
                    help="Labels to plot (default: all of " + ", ".join(all_labels) + ")")
    return p.parse_args()


def main():
    args = parse_args()
    era5_group = zarr.open_group(zarr.storage.LocalStore(args.era5), mode="r")
    gldas_group = zarr.open_group(zarr.storage.LocalStore(args.gldas), mode="r")

    era5_months = year_month_index(era5_group, args.year)
    gldas_months = year_month_index(gldas_group, args.year)

    specs_by_label = {label: (era5_var, gldas_vars) for label, era5_var, gldas_vars in VAR_SPECS + MIN_MAX_VAR_SPECS}
    labels = args.variables or list(specs_by_label)

    os.makedirs(args.output_dir, exist_ok=True)
    for label in labels:
        era5_var, gldas_vars = specs_by_label[label]
        out_path = os.path.join(args.output_dir, f"seasonal_cycles_9sites_era5_gldas_{label}_{args.year}.png")
        plot_variable(era5_group, gldas_group, era5_months, gldas_months, label, era5_var, gldas_vars,
                      args.year, out_path)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
