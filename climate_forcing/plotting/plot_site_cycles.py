#!/usr/bin/env python3
"""
Seasonal cycles at the 9 reference sites (same sites and 3x3 layout as the
old climate_forcing/seasonal_cycles_9sites*.png, which this replaces).

Two modes:

  per file   (--index N / --file F): for one gridded forcing file under
             driver_data/ (same file list as plot_forcing_maps.py), each
             (time, lat, lon) variable gets a 3x3 figure: per site the
             multi-year mean annual cycle with the min..max range over all
             years shaded, plus the first and the last year. Daily files are
             averaged to months first. Values as stored (file units).
             Written next to the global maps:
               output/<same path as in driver_data>_sites.png
               output/global_forcing/<store>/<variable>_sites.png

  comparison (--compare): one figure per variable comparing the datasets
             at 0.5deg in common units over a shared period:
               output/site_comparison/<variable>_<start>-<end>.png

Site values are the nearest grid cell with data (searching up to 2 cells
around the nearest one, so coastal sites still get a land cell).

Usage:
  python plot_site_cycles.py --index 3
  python plot_site_cycles.py --compare [--start 2000 --end 2020]
  sbatch plot_site_cycles.sbatch            # all files + comparison
"""
from __future__ import annotations

import argparse
import calendar
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np

from plot_forcing_maps import DRIVER_DATA, FLAG_WORDS, OUT_ROOT, list_files

# name, biome, lon, lat
SITES = [
    ("Manaus, Brazil", "Tropical rainforest", -60.0, -3.1),
    ("Tamanrasset, Algeria", "Hot desert (Sahara)", 5.5, 22.8),
    ("Serengeti, Tanzania", "Tropical savanna", 35.0, -2.5),
    ("Yakutsk, Russia", "Boreal forest/taiga", 129.7, 62.0),
    ("Ulaanbaatar, Mongolia", "Cold steppe/desert", 106.9, 47.9),
    ("Pontianak, Indonesia", "Tropical rainforest", 109.3, 0.0),
    ("Madrid, Spain", "Mediterranean", -3.7, 40.4),
    ("Kansas, USA", "Temperate grassland", -99.0, 39.0),
    ("Alice Springs, Australia", "Arid/desert", 133.9, -23.7),
]
MONTHS = np.arange(1, 13)


# ------------------------------------------------------------------ reading
def coord_names(ds):
    lat = next(n for n in ("lat", "latitude") if n in ds.variables)
    lon = next(n for n in ("lon", "longitude") if n in ds.variables)
    return lat, lon


def year_month(ds) -> tuple[np.ndarray, np.ndarray]:
    """(year, month) of every time step; rebuilds a masked/empty time axis
    (CRU-JRA tmp/wind daily) as consecutive days from the units' origin."""
    t = ds["time"]
    raw = t[:]
    cal = getattr(t, "calendar", "standard")
    if np.ma.is_masked(raw):
        raw = np.arange(len(t), dtype=float)
    dates = nc.num2date(np.asarray(raw), t.units, cal)
    return np.array([d.year for d in dates]), np.array([d.month for d in dates])


def site_index(v, lats, lons, lon, lat, probe: int):
    """Nearest cell to (lon, lat) that has data at time step `probe`."""
    lon_q = lon % 360 if lons.max() > 180 else lon
    i0 = int(np.argmin(np.abs(lats - lat)))
    dl = np.abs(lons - lon_q)
    dl = np.minimum(dl, 360 - dl)
    j0 = int(np.argmin(dl))
    best = None
    for r in range(0, 3):
        i_lo, i_hi = max(0, i0 - r), min(len(lats), i0 + r + 1)
        js = [(j0 + d) % len(lons) for d in range(-r, r + 1)]
        block = np.ma.filled(v[probe, i_lo:i_hi, :][:, js].astype(float), np.nan)
        ok = np.argwhere(np.isfinite(block) & (np.abs(block) < 1e20))
        for a, b in ok:
            i, j = i_lo + a, js[b]
            d = (lats[i] - lat) ** 2 + min(abs(lons[j] - lon_q), 360 - abs(lons[j] - lon_q)) ** 2
            if best is None or d < best[0]:
                best = (d, i, j)
        if best is not None:
            return best[1], best[2]
    return None


def monthly_series(x: np.ndarray, years: np.ndarray, months: np.ndarray):
    """Monthly means -> dict year -> array(12) (NaN for missing months)."""
    out = {}
    for y in np.unique(years):
        row = np.full(12, np.nan)
        for m in range(1, 13):
            sel = (years == y) & (months == m)
            if sel.any():
                vals = x[sel]
                vals = vals[np.isfinite(vals)]
                if vals.size:
                    row[m - 1] = vals.mean()
        out[int(y)] = row
    return out


def read_sites(ds, var: str):
    """{site name: (dict year -> 12 monthly means, (cell lat, cell lon))}."""
    lat_n, lon_n = coord_names(ds)
    lats, lons = ds[lat_n][:].astype(float), ds[lon_n][:].astype(float)
    v = ds[var]
    v.set_auto_maskandscale(True)
    years, months = year_month(ds)
    probe = len(years) // 2
    out = {}
    for name, _, lon, lat in SITES:
        ij = site_index(v, lats, lons, lon, lat, probe)
        if ij is None:
            out[name] = None
            continue
        i, j = ij
        x = np.ma.filled(v[:, i, j].astype(float), np.nan)
        x[np.abs(x) > 1e20] = np.nan
        out[name] = (monthly_series(x, years, months), (lats[i], lons[j]))
    return out


# ------------------------------------------------------------------ per file
def plot_file_variable(rel: Path, var: str, units: str, long_name: str, sites: dict, out: Path):
    fig, axes = plt.subplots(3, 3, figsize=(15, 10.5), sharex=True)
    for ax, (name, biome, _, _) in zip(axes.ravel(), SITES):
        entry = sites.get(name)
        ax.set_title(f"{name}\n{biome}", fontsize=9)
        ax.grid(alpha=0.3)
        if entry is None:
            ax.text(0.5, 0.5, "no data near site", ha="center", va="center", transform=ax.transAxes)
            continue
        by_year, (clat, clon) = entry
        ys = sorted(by_year)
        arr = np.array([by_year[y] for y in ys])
        with np.errstate(all="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                clim, lo, hi = np.nanmean(arr, 0), np.nanmin(arr, 0), np.nanmax(arr, 0)
        ax.fill_between(MONTHS, lo, hi, color="0.8", label=f"range {ys[0]}-{ys[-1]}")
        ax.plot(MONTHS, clim, color="black", lw=2, label=f"mean {ys[0]}-{ys[-1]}")
        ax.plot(MONTHS, by_year[ys[0]], color="#2a78d6", lw=1.3, label=str(ys[0]))
        ax.plot(MONTHS, by_year[ys[-1]], color="#eb6834", lw=1.3, label=str(ys[-1]))
        ax.text(0.02, 0.97, f"cell {clat:.2f}, {clon:.2f}", transform=ax.transAxes, fontsize=7,
                va="top", color="0.4")
    for ax in axes[-1]:
        ax.set_xticks(MONTHS)
        ax.set_xticklabels([calendar.month_abbr[m][0] for m in MONTHS])
    for ax in axes[:, 0]:
        ax.set_ylabel(f"{var} [{units}]")
    handles, labels = next((a.get_legend_handles_labels() for a in axes.ravel()
                            if a.get_legend_handles_labels()[0]), ([], []))
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=9)
    fig.suptitle(f"{rel}  --  {var}  {('(' + long_name + ')') if long_name else ''}", fontsize=11)
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90)
    plt.close(fig)


def process_file(path: Path) -> None:
    rel = path.relative_to(DRIVER_DATA)
    multi = rel.parts[0] == "global_forcing"
    with nc.Dataset(path) as ds:
        lat_n, lon_n = coord_names(ds)
        variables = [n for n, v in ds.variables.items()
                     if v.ndim == 3 and v.dimensions[-2:] == (lat_n, lon_n) and "time" in v.dimensions
                     and not any(w in n for w in FLAG_WORDS) and v.dtype.kind == "f"]
        for var in variables:
            sites = read_sites(ds, var)
            out = (OUT_ROOT / rel.with_suffix("") / f"{var}_sites.png") if multi else \
                OUT_ROOT / rel.parent / f"{rel.stem}_sites.png"
            plot_file_variable(rel, var, getattr(ds[var], "units", "") or "units not set",
                               getattr(ds[var], "long_name", ""), sites, out)
            print(f"wrote {out.relative_to(OUT_ROOT)}")


# ------------------------------------------------------------------ comparison
# (label, file pattern under driver_data with {var}, variable name in file,
#  conversion to canonical units, colour)
def _days(y, m):
    return calendar.monthrange(y, m)[1]


CANON = {"t_air_min": "K", "t_air_max": "K", "t_air": "K", "precip_total": "mm day-1",
         "q_air": "g kg-1", "press_srf": "hPa", "wind_air": "m s-1",
         "swvis_srf_down": "W m-2", "lw_srf_down": "W m-2"}
SOURCES = {
    "ERA5": ("era5/monthly/0.5deg/era5_{v}_1940-2025_monthly.nc", None, "#2a78d6"),
    "ERA5-Land": ("era5_land/monthly/0.5deg/era5land_{v}_*_monthly.nc", None, "#17becf"),
    "GLDAS": ("gldas/monthly/0.5deg/gldas_{v}_*_monthly.nc", None, "#9467bd"),  # precip = rain + snow
    "TerraClimate": ("terraclimate/monthly/0.5deg/terraclimate_{v}_*_monthly.nc", None, "#1baf7a"),
    "CRU-JRA v2.5": ("crujra/monthly/0.5deg/crujra_v2.5_{v}_*_monthly.nc", None, "#eb6834"),
}
# per-source variable file names where they differ from the canonical name
NAME_MAP = {
    "GLDAS": {"precip_total": "rain", "t_air_min": "t_air_min_derived", "t_air_max": "t_air_max_derived"},
    "TerraClimate": {"precip_total": "rain"},
    "CRU-JRA v2.5": {"t_air": "tmp", "t_air_min": "tmin", "t_air_max": "tmax", "precip_total": "pre",
                     "q_air": "spfh", "press_srf": "pres", "wind_air": None,
                     "swvis_srf_down": "dswrf", "lw_srf_down": "dlwrf"},
}


def to_canonical(source: str, var: str, by_year: dict) -> dict:
    """Unit conversion to CANON[var] (CRU-JRA's attributes are unreliable, so
    conversions are by source, checked against the values 2026-10-11)."""
    out = {}
    for y, row in by_year.items():
        r = row.copy()
        if var == "q_air":
            r = r * 1000.0
        elif var == "press_srf":
            r = r / 100.0
        elif var == "precip_total" and source == "CRU-JRA v2.5":
            r = r / np.array([_days(y, m) for m in MONTHS])  # monthly total -> per day
        out[y] = r
    return out


def compare(start: int, end: int) -> None:
    for var, unit in CANON.items():
        fig, axes = plt.subplots(3, 3, figsize=(15, 10.5), sharex=True)
        used = []
        for source, (pattern, _, colour) in SOURCES.items():
            fname = NAME_MAP.get(source, {}).get(var, var)
            if fname is None:
                continue
            matches = sorted(DRIVER_DATA.glob(pattern.format(v=fname)))
            if not matches:
                continue
            with nc.Dataset(matches[0]) as ds:
                file_var = next((n for n in (fname.replace("_derived", ""), fname) if n in ds.variables), None)
                if file_var is None or "time" not in ds[file_var].dimensions:
                    continue  # e.g. TerraClimate's static press_srf
                sites = read_sites(ds, file_var)
            if source == "GLDAS" and var == "precip_total":
                # gldas_rain is liquid only; total precipitation = rain + snow (as in the forcing store)
                snow_file = next(iter(sorted(DRIVER_DATA.glob(pattern.format(v="snow")))))
                with nc.Dataset(snow_file) as ds:
                    snow = read_sites(ds, "snow")
                for name, entry in sites.items():
                    if entry is not None and snow.get(name) is not None:
                        for y, row in entry[0].items():
                            row += snow[name][0].get(y, 0.0)
            span = None
            for ax, (name, biome, _, _) in zip(axes.ravel(), SITES):
                entry = sites.get(name)
                if entry is None:
                    continue
                by_year = to_canonical(source, var, entry[0])
                ys = [y for y in by_year if start <= y <= end]
                if not ys:
                    continue
                span = (min(ys), max(ys))
                with np.errstate(all="ignore"):
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)
                        clim = np.nanmean([by_year[y] for y in ys], 0)
                ax.plot(MONTHS, clim, color=colour, lw=1.8)
            if span:
                used.append((source, colour, span))
        for ax, (name, biome, _, _) in zip(axes.ravel(), SITES):
            ax.set_title(f"{name}\n{biome}", fontsize=9)
            ax.grid(alpha=0.3)
        for ax in axes[-1]:
            ax.set_xticks(MONTHS)
            ax.set_xticklabels([calendar.month_abbr[m][0] for m in MONTHS])
        for ax in axes[:, 0]:
            ax.set_ylabel(f"{var} [{unit}]")
        handles = [plt.Line2D([], [], color=c, lw=2) for _, c, _ in used]
        labels = [f"{s} ({a}-{b})" for s, _, (a, b) in used]
        fig.legend(handles, labels, loc="lower center", ncol=len(used) or 1, fontsize=9)
        fig.suptitle(f"{var}: mean annual cycle {start}-{end} (or the overlap with each dataset), 0.5deg",
                     fontsize=11)
        fig.tight_layout(rect=(0, 0.04, 1, 0.97))
        out = OUT_ROOT / "site_comparison" / f"{var}_{start}-{end}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=90)
        plt.close(fig)
        print(f"wrote {out.relative_to(OUT_ROOT)} ({', '.join(s for s, _, _ in used)})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--index", type=int)
    g.add_argument("--file", type=Path)
    g.add_argument("--compare", action="store_true")
    ap.add_argument("--start", type=int, default=2000)
    ap.add_argument("--end", type=int, default=2020)
    args = ap.parse_args()
    if args.compare:
        compare(args.start, args.end)
    else:
        process_file(args.file.resolve() if args.file else list_files()[args.index])


if __name__ == "__main__":
    main()
