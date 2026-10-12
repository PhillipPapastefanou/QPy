#!/usr/bin/env python3
"""
Global maps of every gridded forcing file under driver_data/: for the first
and the last year in the file, the per-cell mean, maximum and minimum over
that year's time steps (12 months, or 365/366 days for daily files).

Output mirrors driver_data's layout under climate_forcing/output/, e.g.
  driver_data/era5_land/monthly/0.5deg/era5land_t_air_min_1950-2024_monthly.nc
  -> output/era5_land/monthly/0.5deg/era5land_t_air_min_1950-2024_monthly.png
Global forcing stores (several variables per file) give one png per
variable: output/global_forcing/<store>/<variable>.png.

Each figure: rows = first / last year, columns = mean / max / min; the two
panels of a column share one colour scale so the years compare directly.
Grid orientation (descending latitude, 0..360 longitude) is normalised for
display only; values are plotted as stored (units from the file).

Usage:
  python plot_forcing_maps.py --list                 # print the file list
  python plot_forcing_maps.py --index 3              # plot file #3 of the list
  python plot_forcing_maps.py --file path/to/x.nc    # plot one file
  sbatch plot_forcing_maps.sbatch                    # all files, array job
"""
from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np

DRIVER_DATA = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data")
OUT_ROOT = Path(__file__).resolve().parent.parent / "output"

# product folders holding per-variable gridded files (raw/cache folders excluded)
GLOBS = [
    "era5/monthly/*/*.nc",
    "era5_land/monthly/*/*.nc",
    "gldas/monthly/*/*.nc",
    "gldas/daily/*/*.nc",
    "terraclimate/monthly/*/*.nc",
    "crujra/monthly/*/*.nc",
    "crujra/daily/*/*.nc",
    "global_forcing/*.nc",
]
FLAG_WORDS = ("from_era5", "gapfilled", "fallback", "land_fraction")
MAX_DISPLAY_COLS = 2400  # coarser display (stride) for the 4 km TerraClimate grid


def list_files() -> list[Path]:
    files = []
    for g in GLOBS:
        files += sorted(p for p in DRIVER_DATA.glob(g) if "test" not in p.name)
    return files


def coord_names(ds) -> tuple[str, str]:
    lat = next(n for n in ("lat", "latitude") if n in ds.variables)
    lon = next(n for n in ("lon", "longitude") if n in ds.variables)
    return lat, lon


def map_variables(ds, lat: str, lon: str) -> list[str]:
    out = []
    for name, v in ds.variables.items():
        if v.dimensions[-2:] == (lat, lon) and "time" in v.dimensions and v.ndim == 3 \
                and not any(w in name for w in FLAG_WORDS) and v.dtype.kind == "f":
            out.append(name)
    return out


def year_slices(ds) -> list[tuple[int, slice]]:
    """(year, index slice) for the first and last calendar year in the file."""
    t = ds["time"]
    n = len(t)
    raw = t[:]
    cal = getattr(t, "calendar", "standard")
    if np.ma.is_masked(raw):
        # broken time axis (e.g. crujra tmp/wind daily): rebuild from units, 365-day years
        start = nc.num2date(0, t.units, cal).year
        per = 365 if n > 12 * 200 else 12
        years = start + np.arange(n) // per
    else:
        years = np.array([d.year for d in nc.num2date(raw, t.units, cal)])
    out = []
    for y in (years[0], years[-1]):
        idx = np.flatnonzero(years == y)
        out.append((int(y), slice(int(idx[0]), int(idx[-1]) + 1)))
    return out


def year_stats(v, sl: slice) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Mean/max/min over time, reading in blocks to bound memory."""
    n = sl.stop - sl.start
    step = n if n <= 12 else 31
    s = mx = mn = None
    cnt = None
    for i in range(sl.start, sl.stop, step):
        x = v[i:min(i + step, sl.stop)]
        x = np.ma.filled(x.astype(np.float32), np.nan)
        x[x < -1e20] = np.nan
        x[x > 1e20] = np.nan
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            bs, bc = np.nansum(x, 0), np.sum(np.isfinite(x), 0)
            bmax, bmin = np.nanmax(x, 0), np.nanmin(x, 0)
        if s is None:
            s, cnt, mx, mn = bs, bc, bmax, bmin
        else:
            s += bs
            cnt += bc
            mx = np.fmax(mx, bmax)
            mn = np.fmin(mn, bmin)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(cnt > 0, s / cnt, np.nan)
    return mean, mx, mn


def orient(field: np.ndarray, lats: np.ndarray, lons: np.ndarray):
    """North-up, longitude -180..180, for imshow."""
    if lats[0] < lats[-1]:
        field, lats = field[::-1], lats[::-1]
    lons = np.where(lons >= 180, lons - 360, lons)
    order = np.argsort(lons, kind="stable")
    return field[:, order], lats, lons[order]


def plot(path: Path, var: str, units: str, title: str, stats, lats, lons, out: Path) -> None:
    stride = max(1, int(np.ceil(len(lons) / MAX_DISPLAY_COLS)))
    fig, axes = plt.subplots(2, 3, figsize=(18, 7.2), constrained_layout=True)
    names = ["mean", "max", "min"]
    for j, name in enumerate(names):
        cols = [orient(stats[r][1][j], lats, lons) for r in range(2)]
        vals = np.concatenate([c[0][np.isfinite(c[0])] for c in cols]) if any(
            np.isfinite(c[0]).any() for c in cols) else np.array([0.0, 1.0])
        vmin, vmax = np.percentile(vals, [1, 99]) if vals.size else (0, 1)
        if vmin == vmax:
            vmin, vmax = vmin - 0.5, vmax + 0.5
        cmap = "RdBu" if vmin < 0 < vmax and abs(vmin) > 0.2 * vmax else "viridis"
        for r in range(2):
            f, la, lo = cols[r]
            ax = axes[r, j]
            im = ax.imshow(f[::stride, ::stride], extent=[lo[0], lo[-1], la[-1], la[0]],
                           origin="upper", vmin=vmin, vmax=vmax, cmap=cmap, interpolation="nearest",
                           aspect="auto")
            ax.set_facecolor("0.85")
            ax.set_title(f"{stats[r][0]} {name}  (cell mean {np.nanmean(f):.4g}, "
                         f"range {np.nanmin(f):.4g}..{np.nanmax(f):.4g})", fontsize=9)
            ax.set_xticks(range(-180, 181, 60))
            ax.set_yticks(range(-90, 91, 30))
            ax.tick_params(labelsize=7)
        fig.colorbar(im, ax=axes[:, j], orientation="horizontal", shrink=0.8, label=f"{var} [{units}]")
    fig.suptitle(title, fontsize=11)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=90)
    plt.close(fig)


def process(path: Path) -> None:
    rel = path.relative_to(DRIVER_DATA)
    multi = rel.parts[0] == "global_forcing"
    with nc.Dataset(path) as ds:
        lat, lon = coord_names(ds)
        lats, lons = ds[lat][:].astype(float), ds[lon][:].astype(float)
        variables = map_variables(ds, lat, lon)
        if not variables:
            print(f"skip {rel}: no (time, lat, lon) variable")
            return
        years = year_slices(ds)
        for var in variables:
            v = ds[var]
            v.set_auto_maskandscale(True)
            out = (OUT_ROOT / rel.with_suffix("") / f"{var}.png") if multi else \
                (OUT_ROOT / rel.with_suffix(".png"))
            stats = [(y, year_stats(v, sl)) for y, sl in years]
            units = getattr(v, "units", "") or "units not set"
            title = f"{rel}  --  {var}  ({getattr(v, 'long_name', '')})\n" \
                    f"per-cell mean / max / min over the time steps of the first and last year"
            plot(path, var, units, title, stats, lats, lons, out)
            print(f"wrote {out.relative_to(OUT_ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--index", type=int)
    g.add_argument("--file", type=Path)
    args = ap.parse_args()
    files = list_files()
    if args.list:
        for i, p in enumerate(files):
            print(i, p.relative_to(DRIVER_DATA))
        return
    process(args.file.resolve() if args.file else files[args.index])


if __name__ == "__main__":
    main()
