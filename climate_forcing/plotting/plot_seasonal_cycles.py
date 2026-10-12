#!/usr/bin/env python3
"""
Compare mean-annual-cycle (climatological monthly) near-surface temperature
across 3 datasets at 9 sites spanning distinct continents/biomes, 3x3 grid.

Datasets used, and why these specific baselines:
  - ERA5 (t_air, native 0.25deg): fully downloaded, unit-corrected. 1991-2020.
  - TerraClimate ((tmax+tmin)/2): its "raw" yearly tmax/tmin caches have
    all 68 years (1958-2025) -- read directly rather than through the
    final concatenated files. TerraClimate ships tmax/tmin, not mean temp,
    so this approximates it the standard way; using tmax alone (as this
    plot used to, before tmin finished downloading) systematically runs
    hot by roughly the local diurnal range -- see the "why is terra
    different" discussion this was written to resolve.
  - GLDAS Noah v2.1 (t_air, native 0.25deg): added 2026-09-07 once the
    monthly GLDAS download finished. Only starts in 2000 (vs. ERA5's 1940,
    TerraClimate's 1958, CRU-JRA's 1901), so its climatology baseline is
    2000-2020 -- the shortest and most recent of the four, called out in
    its legend label like the others' differing baselines.

GSWP3-W5E5 was dropped from this comparison (2026-09-06, at user's request)
-- ISIMIP3a obsclim is a fixed historical product capped at 2019, not a
rolling dataset, so it can't reach 2024/2025 the way the other three can.

CRU-JRA v3.0 was dropped from this comparison on 2026-09-07 -- its
precipitation was confirmed wrong (17-32% of CRUNCEPv7's independently-
verified reference at every cross-checked site), later root-caused
(2026-09-07) to a missing CRU-TS bias-correction step: CEDA's own
Computation Record for v2.4/v2.5 documents "adjustment factor is acquired
(crupre/jrapre) and all values adjusted" -- a per-cell, per-month rescale
of raw JRA-55 precip against CRU TS gauge totals -- and v3.0 has no such
Computation Record at all, unlike every documented CRU-JRA version. v3.0's
temperature is fine (only precip is broken), but since v2.5 has the correct
bias-corrected precip AND fine temperature, added back here as v2.5
instead (2026-09-07, at user's request) once its download landed. v3.0
keeps downloading in the background for whatever else it's useful for, just
isn't plotted here.

Different baseline periods per dataset is a real caveat (climate is not
static over a century), not just cosmetic -- it's called out in the plot title/legend.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DRIVER_ROOT = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data")
OUT_PNG = Path(__file__).parent.parent / "output" / "site_comparison" / "seasonal_cycles_9sites.png"

# name, continent, biome, lon, lat
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

# dataviz skill's validated categorical slots (fixed order, not cycled);
# GLDAS added 2026-09-07 using tab:purple, distinct from the others and
# from the gray zero-line/grid.
COLORS = {"ERA5": "#2a78d6", "CRU-JRA": "#eb6834", "TerraClimate": "#1baf7a", "GLDAS": "#9467bd"}


def nearest_sel(da, lon, lat, lon_name="lon", lat_name="lat"):
    lons = da[lon_name].values
    # normalize target lon into whatever convention this grid uses (0-360 vs -180-180)
    target_lon = lon
    if lons.max() > 180 and lon < 0:
        target_lon = lon + 360
    return da.sel({lon_name: target_lon, lat_name: lat}, method="nearest")


def era5_climatology():
    print("[ERA5] loading local t_air 1940-2025 file, slicing 1991-2020...")
    ds = xr.open_dataset(DRIVER_ROOT / "era5" / "monthly" / "0.25deg" / "era5_t_air_1940-2025_monthly.nc")
    da = ds["t_air"].sel(time=slice("1991-01-01", "2020-12-31")) - 273.15
    clim = da.groupby("time.month").mean("time")
    out = {}
    for name, _, _, lon, lat in LOCATIONS:
        out[name] = nearest_sel(clim, lon, lat, "longitude", "latitude").values
    ds.close()
    return out


def terraclimate_climatology():
    print("[TerraClimate] reading converted monthly tmax+tmin files (1958-2025), averaging to mean temp...")
    # Reads the actual converted monthly product (driver_data/terraclimate/
    # monthly/4km/) rather than the raw per-year cache directly -- point
    # extraction against the concatenated file is lazy the same way it was
    # against the raw yearly files (netCDF4 backend supports partial reads
    # via .sel), so this doesn't reintroduce the ~227 GiB full-grid-
    # concatenation problem the raw-file approach was originally written to
    # avoid; it's the same access pattern, just against one file instead of
    # 68 (2026-09-07, at user's request, for consistency with GLDAS/ERA5
    # which already read the converted product).
    f_max = DRIVER_ROOT / "terraclimate" / "monthly" / "4km" / "terraclimate_tmax_1958-2025_monthly.nc"
    f_min = DRIVER_ROOT / "terraclimate" / "monthly" / "4km" / "terraclimate_tmin_1958-2025_monthly.nc"
    ds_max = xr.open_dataset(f_max)
    ds_min = xr.open_dataset(f_min)
    # TerraClimate ships tmax/tmin, not a mean-temp variable directly --
    # (tmax+tmin)/2 is the standard approximation and matches ERA5/CRU-JRA/
    # GSWP3-W5E5's mean temperature instead of systematically running hot
    # (tmax alone overstates the seasonal cycle by roughly the local mean
    # diurnal range -- see the "why is terra different" discussion).
    out = {}
    for name, _, _, lon, lat in LOCATIONS:
        tmax_pt = nearest_sel(ds_max["tmax"], lon, lat, "lon", "lat")
        tmin_pt = nearest_sel(ds_min["tmin"], lon, lat, "lon", "lat")
        mean_c = (tmax_pt + tmin_pt) / 2.0
        out[name] = mean_c.groupby("time.month").mean("time").values
    ds_max.close()
    ds_min.close()
    return out


def crujra_climatology():
    # v2.5, not v3.0 -- v3.0's precip is wrong (see docstring); temperature
    # ("tmp") is fine in either version, but v2.5 is used throughout for
    # consistency now that it's the active CRU-JRA version.
    matches = sorted((DRIVER_ROOT / "crujra" / "monthly" / "0.5deg").glob("crujra_v2.5_tmp_*_monthly.nc"))
    if not matches:
        print("[CRU-JRA v2.5] no monthly tmp file yet, skipping")
        return None, None
    f = matches[-1]
    ds = xr.open_dataset(f)
    da = ds["tmp"] - 273.15
    year_min, year_max = int(da["time.year"].min()), int(da["time.year"].max())
    print(f"[CRU-JRA v2.5] loading {f.name}, climatology over {year_min}-{year_max}...")
    clim = da.groupby("time.month").mean("time")
    out = {}
    for name, _, _, lon, lat in LOCATIONS:
        out[name] = nearest_sel(clim, lon, lat).values
    ds.close()
    return out, f"{year_min}-{year_max}"


def gldas_climatology():
    print("[GLDAS] loading local t_air 2000-2025 file, slicing 2000-2020...")
    ds = xr.open_dataset(DRIVER_ROOT / "gldas" / "monthly" / "0.25deg" / "gldas_t_air_2000-2025_monthly.nc")
    da = ds["t_air"].sel(time=slice("2000-01-01", "2020-12-31")) - 273.15
    clim = da.groupby("time.month").mean("time")
    out = {}
    for name, _, _, lon, lat in LOCATIONS:
        out[name] = nearest_sel(clim, lon, lat).values
    ds.close()
    return out


def main():
    era5 = era5_climatology()
    terra = terraclimate_climatology()
    gldas = gldas_climatology()
    crujra, crujra_baseline = crujra_climatology()

    fig, axes = plt.subplots(3, 3, figsize=(15, 12), sharex=True)
    months = np.arange(1, 13)

    for ax, (name, continent, biome, lon, lat) in zip(axes.flat, LOCATIONS):
        ax.plot(months, era5[name], color=COLORS["ERA5"], lw=2, label="ERA5 (1991-2020)")
        ax.plot(months, terra[name], color=COLORS["TerraClimate"], lw=2, label="TerraClimate (1958-2025)")
        ax.plot(months, gldas[name], color=COLORS["GLDAS"], lw=2, label="GLDAS (2000-2020)")
        if crujra is not None:
            ax.plot(months, crujra[name], color=COLORS["CRU-JRA"], lw=2, label=f"CRU-JRA v2.5 ({crujra_baseline})")

        ax.set_title(f"{name}\n{continent} — {biome}", fontsize=10, fontweight="bold")
        ax.set_xticks(months)
        ax.grid(True, alpha=0.25)
        ax.axhline(0, color="gray", lw=0.5, alpha=0.5)

    for ax in axes[-1, :]:
        ax.set_xlabel("Month")
    for ax in axes[:, 0]:
        ax.set_ylabel("Temperature (°C)")

    n_datasets = 4 if crujra is not None else 3
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=n_datasets, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle(f"Mean annual temperature cycle across {n_datasets} datasets, 9 sites\n"
                 "(note: differing baseline periods per dataset -- see legend)",
                 fontsize=12, y=1.01)
    fig.tight_layout(rect=[0, 0.04, 1, 0.98])
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    print(f"Wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
