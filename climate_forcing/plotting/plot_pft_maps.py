#!/usr/bin/env python3
"""
Plots of the PFT fields in the QUINCY static file (written by
conversion/build_pft_map.py), saved to <static dir>/plots/:

  pft_fraction.png          pft_fraction per PFT (small multiples)
  pft_dominant_map.png      dominant natural PFT, all PFTs on one map
  pft_dominant_natural.png  where each natural PFT is the dominant one (one panel each)
  pft_vs_sites.png          pft_dominant_natural vs the GLOBAL site table PFT

Usage:
  python plot_pft_maps.py               # 0.25deg
  python plot_pft_maps.py --res 0.5
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
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, ListedColormap

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.quincy.base.PFTTypes import PftFluxnet, GetQuincyPFTfromFluxnetPFT  # noqa: E402

STATIC_ROOT = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/static")
GLOBAL_SITES = Path("/Net/Groups/BSI/data/quincy/input/point/GLOBAL/global_all_sites_1901-2018_list.dat")
LONG_NAMES = ["moist broadleaved evergreen", "dry broadleaved evergreen", "raingreen broadleaved deciduous",
              "summergreen broadleaved deciduous", "needle-leaved evergreen", "summergreen needle-leaved",
              "C3 grass", "C4 grass", "C3 pasture", "C4 pasture", "C3 crop", "C4 crop", "bare soil", "urban"]
SHOWN = [0, 1, 2, 3, 4, 5, 6, 7, 10, 11, 12]   # TeP, TrP, UAR are 0 everywhere
SURFACE, OCEAN, LAND, INK, MUTED = "#fcfcfb", "#f0efec", "#dcdad5", "#222222", "#555555"
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
BARE = "#b5b2ab"
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
LAT_MIN = -60   # nothing south of 60S but Antarctica (no SoilGrids data)


def _style(ax, title):
    ax.set_title(title, fontsize=10, color=INK, loc="left")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def _show(ax, field, lat, cmap, **kw):
    rows = lat >= LAT_MIN
    return ax.imshow(field[rows][::-1], cmap=cmap, extent=[-180, 180, LAT_MIN, 90],
                     interpolation="nearest", **kw)


def plot_fractions(frac, names, lat, out):
    cmap = LinearSegmentedColormap.from_list("blue", BLUE_RAMP)
    cmap.set_bad(OCEAN)
    fig, axs = plt.subplots(4, 3, figsize=(15, 9.5), facecolor=SURFACE)
    for ax, i in zip(axs.flat, SHOWN):
        im = _show(ax, frac[i], lat, cmap, vmin=0, vmax=1)
        _style(ax, f"{i + 1} {names[i]} - {LONG_NAMES[i]}")
    ax = axs.flat[-1]
    ax.axis("off")
    cb = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.5, aspect=15)
    cb.set_label("fraction of land cell", color=MUTED)
    cb.outline.set_visible(False)
    fig.suptitle("QUINCY PFT fractions (pft_fraction), from CLM4; TeP, TrP, UAR are 0 everywhere",
                 x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout()
    fig.savefig(out, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def plot_dominant(dom, names, lat, out):
    # one panel per PFT: cells where it is the dominant natural PFT, on grey land
    fig, axs = plt.subplots(3, 3, figsize=(15, 7.5), facecolor=SURFACE)
    land = dom > 0
    n_land = land.sum()
    for ax, i in zip(axs.flat, list(range(8)) + [12]):
        field = np.where(land, (dom == i + 1).astype(float), np.nan)
        _show(ax, field, lat, ListedColormap([LAND, BLUE_RAMP[5]]).with_extremes(bad=OCEAN), vmin=0, vmax=1)
        share = (dom == i + 1).sum() / n_land
        _style(ax, f"{i + 1} {names[i]} - {LONG_NAMES[i]}  ({share:.0%} of land cells)")
    fig.suptitle("Dominant natural PFT (pft_dominant_natural): dark = this PFT has the largest share "
                 "among PFTs 1-8; BSO = no natural vegetation", x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout()
    fig.savefig(out, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def plot_dominant_map(dom, names, lat, out):
    # all natural PFTs on one map: the 8 categorical slots in fixed order, bare soil neutral;
    # adjacent classes are not all CVD-separable, pft_dominant_natural.png is the accessible view
    colors = CATEGORICAL + [BARE]
    cmap = ListedColormap(colors).with_extremes(bad=OCEAN)
    field = np.where(dom > 0, np.where(dom == 13, 9, dom), np.nan)
    fig, ax = plt.subplots(figsize=(14, 7.2), facecolor=SURFACE)
    _show(ax, field, lat, cmap, vmin=0.5, vmax=9.5)
    _style(ax, "")
    n_land = (dom > 0).sum()
    labels = [f"{i + 1} {names[i]} - {LONG_NAMES[i]} ({(dom == i + 1).sum() / n_land:.0%})" for i in range(8)]
    labels.append(f"13 BSO - no natural vegetation ({(dom == 13).sum() / n_land:.0%})")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors]
    ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=3, frameon=False,
              fontsize=9.5, labelcolor=INK, handlelength=1.2)
    fig.suptitle("Dominant natural QUINCY PFT (pft_dominant_natural), share of land cells in brackets",
                 x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout()
    fig.savefig(out, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def plot_sites(dom, frac, names, lat, lon, out):
    df = pd.read_csv(GLOBAL_SITES, sep=r"\s+")
    iy = np.abs(lat[None, :] - df.lat.values[:, None]).argmin(1)
    ix = np.abs(lon[None, :] - df.lon.values[:, None]).argmin(1)
    site = np.array([GetQuincyPFTfromFluxnetPFT(PftFluxnet[p]).value for p in df.PFT])
    mapped = dom[iy, ix]
    cats = list(range(1, 9)) + [13]
    tab = pd.crosstab(pd.Categorical(site, cats[:-1]), pd.Categorical(mapped, cats), dropna=False)
    agree = np.mean(mapped == site)
    present = np.mean(frac[site - 1, iy, ix] > 0)

    fig, ax = plt.subplots(figsize=(8, 6.5), facecolor=SURFACE)
    cmap = LinearSegmentedColormap.from_list("blue", ["#ffffff"] + BLUE_RAMP)
    m = tab.values
    ax.imshow(m, cmap=cmap, vmin=0, vmax=m.max())
    for (r, c), v in np.ndenumerate(m):
        if v:
            ax.text(c, r, str(v), ha="center", va="center", fontsize=9,
                    color="#ffffff" if v > 0.5 * m.max() else INK)
    ax.set_xticks(range(len(cats)), [names[c - 1] for c in cats])
    ax.set_yticks(range(8), [names[c - 1] for c in cats[:-1]])
    ax.set_xlabel("map: pft_dominant_natural", color=MUTED)
    ax.set_ylabel("GLOBAL site table PFT", color=MUTED)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, colors=MUTED)
    ax.set_title(f"Map vs {len(df)} GLOBAL sites: same PFT at {agree:.0%}; "
                 f"site PFT present in the cell at {present:.0%}", fontsize=11, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(out, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--res", type=float, default=0.25)
    args = ap.parse_args()
    tag = f"{args.res:g}deg"
    path = STATIC_ROOT / tag / f"quincy_static_inputs_{tag}.nc"
    with nc.Dataset(path) as ds:
        lat, lon = np.asarray(ds["lat"][:], float), np.asarray(ds["lon"][:], float)
        names = ds["pft"].short_names.split()
        frac = np.ma.filled(ds["pft_fraction"][:].astype(float), np.nan)
        dom = np.ma.filled(ds["pft_dominant_natural"][:], 0).astype(int)
    out_dir = STATIC_ROOT / tag / "plots"
    out_dir.mkdir(exist_ok=True)
    plot_fractions(frac, names, lat, out_dir / "pft_fraction.png")
    plot_dominant_map(dom, names, lat, out_dir / "pft_dominant_map.png")
    plot_dominant(dom, names, lat, out_dir / "pft_dominant_natural.png")
    plot_sites(dom, frac, names, lat, lon, out_dir / "pft_vs_sites.png")
    print(f"wrote plots to {out_dir}")


if __name__ == "__main__":
    main()
