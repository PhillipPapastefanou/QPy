#!/usr/bin/env python3
"""
Same 9-site x 3x3 seasonal-cycle comparison as plot_seasonal_cycles.py, but
using a single specific calendar year of data per dataset instead of a
multi-decade climatological average. Produces one PNG per requested year.

Coverage notes:
  - ERA5 (t_air): covers all requested years (1940-2025 local file).
  - TerraClimate ((tmax+tmin)/2): reads the single cached raw yearly tmax
    and tmin files directly, averaged -- see plot_seasonal_cycles.py's
    docstring for why tmax alone isn't used.
  - GLDAS Noah v2.1 (t_air): added 2026-09-07. Only covers 2000-2025, so
    any requested year before 2000 is skipped for GLDAS specifically (the
    other three still plot normally).

GSWP3-W5E5 was dropped from this comparison (2026-09-06, at user's
request) -- ISIMIP3a obsclim is capped at 2019, so it couldn't appear in
the 2020/2024 plots anyway, and doesn't add anything for 2000/2010 either.

CRU-JRA v3.0 was dropped on 2026-09-07 -- its precipitation was confirmed
wrong against an independent reference (CRUNCEPv7), later root-caused
(2026-09-07) to a missing CRU-TS bias-correction step that every other
documented CRU-JRA version applies (see plot_seasonal_cycles.py's
docstring for the full mechanism). v2.5 has that correction and fine
temperature, so it's used here instead (2026-09-07, at user's request)
once its download landed. v3.0 keeps downloading in the background for
whatever else it's useful for, just isn't plotted here.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DRIVER_ROOT = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data")
OUT_DIR = Path(__file__).parent.parent  # climate_forcing/ toolkit root

YEARS = [2000, 2010, 2020, 2024]

LOCATIONS = [
    ("Manaus, Brazil",        "South America", "Tropical rainforest", -60.0,  -3.1),
    ("Tamanrasset, Algeria",  "Africa",         "Hot desert (Sahara)",   5.5,  22.8),
    ("Serengeti, Tanzania",   "Africa",         "Tropical savanna",     35.0,  -2.5),
    ("Yakutsk, Russia",       "Asia",           "Boreal forest/taiga", 129.7,  62.0),
    ("Ulaanbaatar, Mongolia", "Asia",           "Cold steppe/desert",  106.9,  47.9),
    ("Pontianak, Indonesia",  "Asia",           "Tropical rainforest", 109.3,   0.0),
    ("Madrid, Spain",         "Europe",         "Mediterranean",        -3.7,  40.4),
    ("Kansas, USA",           "North America",  "Temperate grassland", -99.0,  39.0),
    ("Alice Springs, Australia","Australia",    "Arid/desert",         133.9, -23.7),
]

COLORS = {"ERA5": "#2a78d6", "CRU-JRA": "#eb6834", "TerraClimate": "#1baf7a", "GLDAS": "#9467bd"}


def nearest_sel(da, lon, lat, lon_name="lon", lat_name="lat"):
    lons = da[lon_name].values
    target_lon = lon
    if lons.max() > 180 and lon < 0:
        target_lon = lon + 360
    return da.sel({lon_name: target_lon, lat_name: lat}, method="nearest")


def era5_year(year: int):
    ds = xr.open_dataset(DRIVER_ROOT / "era5" / "monthly" / "0.25deg" / "era5_t_air_1940-2025_monthly.nc")
    da = ds["t_air"].sel(time=str(year)) - 273.15
    out = {}
    for name, _, _, lon, lat in LOCATIONS:
        vals = nearest_sel(da, lon, lat, "longitude", "latitude").values
        out[name] = vals if len(vals) == 12 else None
    ds.close()
    return out


def _latest_monthly_file(directory: Path, pattern: str) -> Path | None:
    matches = sorted(directory.glob(pattern))
    return matches[-1] if matches else None


def terraclimate_year(year: int):
    # Reads the converted monthly product (driver_data/terraclimate/
    # monthly/4km/) instead of the raw per-year cache (2026-09-07, at
    # user's request, for consistency with GLDAS/ERA5).
    f_max = _latest_monthly_file(DRIVER_ROOT / "terraclimate" / "monthly" / "4km", "terraclimate_tmax_*_monthly.nc")
    f_min = _latest_monthly_file(DRIVER_ROOT / "terraclimate" / "monthly" / "4km", "terraclimate_tmin_*_monthly.nc")
    if f_max is None or f_min is None:
        print("[TerraClimate] no converted monthly tmax/tmin file found, skipping")
        return None
    # (tmax+tmin)/2 approximates mean temp -- tmax alone runs hot by
    # roughly the local diurnal range, see plot_seasonal_cycles.py.
    ds_max = xr.open_dataset(f_max)
    ds_min = xr.open_dataset(f_min)
    tmax = ds_max["tmax"].sel(time=str(year))
    tmin = ds_min["tmin"].sel(time=str(year))
    if tmax.sizes.get("time", 0) != 12 or tmin.sizes.get("time", 0) != 12:
        print(f"[TerraClimate] {year} not covered, skipping")
        ds_max.close()
        ds_min.close()
        return None
    out = {}
    for name, _, _, lon, lat in LOCATIONS:
        vals_max = nearest_sel(tmax, lon, lat, "lon", "lat").values
        vals_min = nearest_sel(tmin, lon, lat, "lon", "lat").values
        out[name] = (vals_max + vals_min) / 2.0
    ds_max.close()
    ds_min.close()
    return out


def crujra_year(year: int):
    # v2.5, not v3.0 -- see docstring. "tmp" = mean temperature.
    f = _latest_monthly_file(DRIVER_ROOT / "crujra" / "monthly" / "0.5deg", "crujra_v2.5_tmp_*_monthly.nc")
    if f is None:
        print("[CRU-JRA v2.5] no monthly tmp file found, skipping")
        return None
    ds = xr.open_dataset(f)
    da = ds["tmp"].sel(time=str(year)) - 273.15
    if da.sizes.get("time", 0) != 12:
        print(f"[CRU-JRA v2.5] {year} not covered, skipping")
        ds.close()
        return None
    out = {}
    for name, _, _, lon, lat in LOCATIONS:
        vals = nearest_sel(da, lon, lat).values
        out[name] = vals if len(vals) == 12 else None
    ds.close()
    return out


def gldas_year(year: int):
    f = DRIVER_ROOT / "gldas" / "monthly" / "0.25deg" / "gldas_t_air_2000-2025_monthly.nc"
    if year < 2000:
        print(f"[GLDAS] {year} is before GLDAS coverage (2000-2025), skipping")
        return None
    if not f.exists():
        print(f"[GLDAS] no cached file, skipping")
        return None
    ds = xr.open_dataset(f)
    da = ds["t_air"].sel(time=str(year)) - 273.15
    out = {}
    for name, _, _, lon, lat in LOCATIONS:
        vals = nearest_sel(da, lon, lat).values
        out[name] = vals if len(vals) == 12 else None
    ds.close()
    return out


def plot_year(year: int, era5, terra, gldas, crujra):
    fig, axes = plt.subplots(3, 3, figsize=(15, 12), sharex=True)
    months = np.arange(1, 13)

    for ax, (name, continent, biome, lon, lat) in zip(axes.flat, LOCATIONS):
        if era5 and era5.get(name) is not None:
            ax.plot(months, era5[name], color=COLORS["ERA5"], lw=2, label="ERA5")
        if terra and terra.get(name) is not None:
            ax.plot(months, terra[name], color=COLORS["TerraClimate"], lw=2, label="TerraClimate")
        if gldas and gldas.get(name) is not None:
            ax.plot(months, gldas[name], color=COLORS["GLDAS"], lw=2, label="GLDAS")
        if crujra and crujra.get(name) is not None:
            ax.plot(months, crujra[name], color=COLORS["CRU-JRA"], lw=2, label="CRU-JRA v2.5")

        ax.set_title(f"{name}\n{continent} — {biome}", fontsize=10, fontweight="bold")
        ax.set_xticks(months)
        ax.grid(True, alpha=0.25)
        ax.axhline(0, color="gray", lw=0.5, alpha=0.5)

    for ax in axes[-1, :]:
        ax.set_xlabel("Month")
    for ax in axes[:, 0]:
        ax.set_ylabel("Temperature (°C)")

    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle(f"Annual temperature cycle across datasets, 9 sites -- year {year}\n"
                 "(single calendar year, not a climatological average)",
                 fontsize=12, y=1.01)
    fig.tight_layout(rect=[0, 0.04, 1, 0.98])
    out_png = OUT_DIR / f"seasonal_cycles_9sites_{year}.png"
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out_png}")


def main():
    for year in YEARS:
        print(f"=== Year {year} ===")
        era5 = era5_year(year)
        terra = terraclimate_year(year)
        gldas = gldas_year(year)
        crujra = crujra_year(year)
        plot_year(year, era5, terra, gldas, crujra)


if __name__ == "__main__":
    main()
