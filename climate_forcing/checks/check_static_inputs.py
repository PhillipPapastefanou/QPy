#!/usr/bin/env python3
"""
Check of the QUINCY static file (build_static_inputs.py + build_pft_map.py):
consistency tests printed to stdout (exit code 1 if any FAILs) and overview
maps saved to <static dir>/plots/:

  static_continuous.png  every continuous field (colour range = 2nd-98th percentile)
  static_classes.png     soil classes and lithology: 8 most common classes + other

Usage:
  python check_static_inputs.py               # 0.25deg
  python check_static_inputs.py --res 0.5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, ListedColormap

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plotting"))
from plot_pft_maps import (BLUE_RAMP, CATEGORICAL, INK, LAT_MIN, MUTED, OCEAN, STATIC_ROOT,  # noqa: E402
                           SURFACE, _show, _style)

CONTINUOUS = ["land_fraction", "sand_fraction", "silt_fraction", "clay_fraction", "BLDFIE", "PHIHOX",
              "bedrock_depth", "awc", "Labile_Inorganic_P", "Seconday_Mineral__P", "Occluded_P", "Apatite_P",
              "veg_fraction"]
CLASSES = ["TAXOUSDA_10km", "TAXNWRB", "lith_glim"]
OTHER = "#b5b2ab"
# plausible physical ranges (inclusive) -- a value outside is a FAIL
RANGES = {"land_fraction": (0, 1), "sand_fraction": (0, 1), "silt_fraction": (0, 1), "clay_fraction": (0, 1),
          "BLDFIE": (100, 2200), "PHIHOX": (30, 110), "bedrock_depth": (0, 2), "awc": (0, 800),
          "Labile_Inorganic_P": (0, 1000), "Seconday_Mineral__P": (0, 1000), "Occluded_P": (0, 2000),
          "Apatite_P": (0, 2000), "veg_fraction": (0, 1), "lith_glim": (1, 16),
          "pft_dominant": (1, 13), "pft_dominant_natural": (1, 13)}


def read(path):
    with nc.Dataset(path) as ds:
        lat = np.asarray(ds["lat"][:], float)
        f = {k: np.ma.filled(v[:].astype(float), np.nan) for k, v in ds.variables.items()
             if k not in ("lat", "lon", "pft")}
        units = {k: getattr(ds[k], "units", "") for k in f}
    return lat, f, units


def run_checks(f):
    results = []

    def check(name, ok, detail):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

    land = np.isfinite(f["sand_fraction"])
    check("land mask", land.sum() > 0, f"{land.sum()} land cells ({land.mean():.1%} of grid)")
    for k, x in f.items():
        if k in ("land_fraction", "qmax_org"):
            continue
        x2 = x if x.ndim == 2 else x[0]
        miss, extra = (land & ~np.isfinite(x2)).sum(), (~land & np.isfinite(x2)).sum()
        check(f"{k} mask", miss == 0 and extra == 0, f"{miss} land cells missing, {extra} values off land")
    for k, (lo, hi) in RANGES.items():
        x = f[k][np.isfinite(f[k])]
        check(f"{k} range", x.min() >= lo and x.max() <= hi, f"{x.min():.4g}..{x.max():.4g} (allowed {lo}..{hi})")
    tex = (f["sand_fraction"] + f["silt_fraction"] + f["clay_fraction"])[land]
    check("sand+silt+clay = 1", np.abs(tex - 1).max() < 0.01, f"max |sum-1| = {np.abs(tex - 1).max():.4f}")
    pft = np.nansum(f["pft_fraction"], 0)[land]
    check("sum of pft_fraction = 1", np.abs(pft - 1).max() < 0.01, f"max |sum-1| = {np.abs(pft - 1).max():.4f}")
    veg = (1 - f["pft_fraction"][12])[land]
    check("veg_fraction = 1 - BSO", np.abs(veg - f["veg_fraction"][land]).max() < 0.002,
          f"max diff {np.abs(veg - f['veg_fraction'][land]).max():.4f}")
    for k, n in [("pft_dominant", 12), ("pft_dominant_natural", 8)]:
        # the dominant PFT was picked before the fractions were rounded, so on
        # rounded ties any of the tied PFTs is right: compare fractions, not ids
        sub = f["pft_fraction"][:n][:, land]
        got = f[k][land].astype(int)
        bare = got == 13
        ok_bare = sub[:, bare].sum(0) == 0
        picked = sub[np.minimum(got, n) - 1, np.arange(got.size)][~bare]
        ok_veg = picked == sub.max(0)[~bare]
        n_bad = (~ok_bare).sum() + (~ok_veg).sum()
        check(f"{k} = largest of PFTs 1-{n}", n_bad == 0,
              f"{n_bad} land cells where another PFT has a larger stored fraction; "
              f"13 only where PFTs 1-{n} are all 0")
    empty = [i + 1 for i in range(14) if np.nanmax(f["pft_fraction"][i]) == 0]
    check("PFTs with no cover", empty == [9, 10, 14], f"{empty} (expected 9 TeP, 10 TrP, 14 UAR)")
    check("qmax_org placeholder", np.all(f["qmax_org"] == -9999), "all -9999 (QUINCY default 6.5537)")
    return all(results)


def plot_continuous(lat, f, units, out):
    cmap = LinearSegmentedColormap.from_list("blue", BLUE_RAMP)
    cmap.set_bad(OCEAN)
    fig, axs = plt.subplots(5, 3, figsize=(15, 13), facecolor=SURFACE)
    for ax, k in zip(axs.flat, CONTINUOUS):
        x = f[k]
        lo, hi = np.nanpercentile(x, [2, 98])
        im = _show(ax, x, lat, cmap, vmin=lo, vmax=hi)
        _style(ax, f"{k} [{units[k]}]")
        cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
        cb.outline.set_visible(False)
        cb.ax.tick_params(labelsize=8, colors=MUTED, length=0)
    for ax in axs.flat[len(CONTINUOUS):]:
        ax.axis("off")
    fig.suptitle("QUINCY static inputs: continuous fields (colour range = 2nd-98th percentile)",
                 x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout()
    fig.savefig(out, dpi=100, facecolor=SURFACE)
    plt.close(fig)


def plot_classes(lat, f, out):
    fig, axs = plt.subplots(1, 3, figsize=(18, 4.8), facecolor=SURFACE)
    for ax, k in zip(axs, CLASSES):
        x = f[k]
        vals, counts = np.unique(x[np.isfinite(x)], return_counts=True)
        top = vals[np.argsort(counts)[::-1][:8]]
        field = np.full(x.shape, np.nan)
        field[np.isfinite(x)] = 9
        for i, v in enumerate(top):
            field[x == v] = i + 1
        _show(ax, field, lat, ListedColormap(CATEGORICAL + [OTHER]).with_extremes(bad=OCEAN), vmin=0.5, vmax=9.5)
        _style(ax, f"{k}: {len(vals)} classes, 8 most common shown")
        handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in CATEGORICAL[:len(top)] + [OTHER]]
        ax.legend(handles, [f"class {int(v)}" for v in top] + ["other"], loc="upper center",
                  bbox_to_anchor=(0.5, -0.02), ncol=5, frameon=False, fontsize=8.5, labelcolor=INK,
                  handlelength=1)
    fig.suptitle("QUINCY static inputs: soil classes and lithology", x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout()
    fig.savefig(out, dpi=100, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--res", type=float, default=0.25)
    args = ap.parse_args()
    tag = f"{args.res:g}deg"
    path = STATIC_ROOT / tag / f"quincy_static_inputs_{tag}.nc"
    print(f"checking {path}")
    lat, f, units = read(path)
    ok = run_checks(f)
    out_dir = STATIC_ROOT / tag / "plots"
    out_dir.mkdir(exist_ok=True)
    plot_continuous(lat, f, units, out_dir / "static_continuous.png")
    plot_classes(lat, f, out_dir / "static_classes.png")
    print(f"plots in {out_dir}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
