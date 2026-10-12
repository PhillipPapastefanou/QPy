#!/usr/bin/env python3
"""
Maps of the QUINCY static inputs (conversion/build_static_inputs.py output):
one png per variable plus an overview sheet with all of them, written to
output/static/<res>/ (same layout as driver_data/static/<res>/).

Continuous fields use a 1-99 percentile colour range; class fields
(soil classes, lithology) get a discrete colour per class; qmax_org, which
has no data (-9999 everywhere = model default), is listed but not mapped.

Usage:
  python plot_static_inputs.py                       # 0.25deg file
  python plot_static_inputs.py --file path/to/quincy_static_inputs_0.5deg.nc
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap

DEFAULT_FILE = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/static/0.25deg/"
                    "quincy_static_inputs_0.25deg.nc")
OUT_ROOT = Path(__file__).resolve().parent.parent / "output" / "static"
CLASS_VARS = {"TAXOUSDA_10km", "TAXNWRB", "lith_glim"}
SKIP = {"lat", "lon", "qmax_org"}
CMAPS = {"sand_fraction": "YlOrBr", "silt_fraction": "copper_r", "clay_fraction": "OrRd",
         "BLDFIE": "cividis", "PHIHOX": "RdYlBu_r", "soil_ph": "RdYlBu_r", "bedrock_depth": "viridis",
         "awc": "Blues", "awc_pF23": "Blues", "awc_pF25": "Blues", "land_fraction": "Greens"}


def class_cmap(values: np.ndarray):
    classes = np.unique(values[np.isfinite(values)]).astype(int)
    base = plt.get_cmap("tab20").colors + plt.get_cmap("tab20b").colors + plt.get_cmap("tab20c").colors
    rng = np.random.default_rng(0)
    colours = [base[i % len(base)] for i in rng.permutation(len(classes))]
    # map class values onto 0..n-1 so any set of codes gets distinct colours
    lut = {c: i for i, c in enumerate(classes)}
    idx = np.full(values.shape, np.nan)
    ok = np.isfinite(values)
    idx[ok] = [lut[int(v)] for v in values[ok]]
    cmap = ListedColormap(colours)
    norm = BoundaryNorm(np.arange(-0.5, len(classes) + 0.5), cmap.N)
    return idx, cmap, norm, classes


def draw(ax, name: str, data: np.ndarray, lats, lons, attrs: dict, colorbar=True):
    extent = [lons[0], lons[-1], lats[0], lats[-1]]
    ax.set_facecolor("0.85")
    if name in CLASS_VARS:
        idx, cmap, norm, classes = class_cmap(data)
        im = ax.imshow(idx, origin="lower", extent=extent, cmap=cmap, norm=norm, interpolation="nearest",
                       aspect="auto")
        sub = f"{len(classes)} classes"
        if colorbar and len(classes) <= 20:
            cb = plt.colorbar(im, ax=ax, ticks=range(len(classes)), shrink=0.8)
            cb.ax.set_yticklabels([str(c) for c in classes], fontsize=6)
    else:
        f = data[np.isfinite(data)]
        vmin, vmax = (np.percentile(f, [1, 99]) if f.size else (0, 1))
        im = ax.imshow(data, origin="lower", extent=extent, cmap=CMAPS.get(name, "viridis"),
                       vmin=vmin, vmax=vmax, interpolation="nearest", aspect="auto")
        sub = f"mean {np.nanmean(data):.4g}, range {np.nanmin(data):.4g}..{np.nanmax(data):.4g}"
        if colorbar:
            plt.colorbar(im, ax=ax, shrink=0.8, label=attrs.get("units", ""))
    ax.set_title(f"{name}\n{sub}", fontsize=8)
    ax.set_ylim(-60, 90)
    ax.tick_params(labelsize=6)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", type=Path, default=DEFAULT_FILE)
    args = ap.parse_args()
    out_dir = OUT_ROOT / args.file.parent.name
    out_dir.mkdir(parents=True, exist_ok=True)

    with nc.Dataset(args.file) as ds:
        lats, lons = ds["lat"][:], ds["lon"][:]
        fields = {}
        for name, v in ds.variables.items():
            if name in SKIP or v.ndim != 2:
                continue
            fields[name] = (np.ma.filled(v[:].astype(float), np.nan), {a: v.getncattr(a) for a in v.ncattrs()})

    for name, (data, attrs) in fields.items():
        fig, ax = plt.subplots(figsize=(11, 5.2), constrained_layout=True)
        draw(ax, name, data, lats, lons, attrs)
        ax.set_title(f"{name} [{attrs.get('units', '')}] -- {attrs.get('long_name', '')}\n"
                     f"{ax.get_title().splitlines()[-1]}", fontsize=9)
        if "source" in attrs:
            fig.text(0.01, 0.005, f"source: {attrs['source']}", fontsize=6, color="0.4")
        fig.savefig(out_dir / f"{name}.png", dpi=110)
        plt.close(fig)
        print(f"wrote {out_dir / (name + '.png')}")

    n = len(fields)
    ncol = 4
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(5 * ncol, 2.9 * nrow), constrained_layout=True)
    for ax, (name, (data, attrs)) in zip(axes.ravel(), fields.items()):
        draw(ax, name, data, lats, lons, attrs, colorbar=name not in CLASS_VARS)
    for ax in axes.ravel()[n:]:
        ax.axis("off")
    fig.suptitle(f"{args.file.name} (qmax_org not shown: no data, model default 6.5537)", fontsize=11)
    fig.savefig(out_dir / "overview.png", dpi=90)
    plt.close(fig)
    print(f"wrote {out_dir / 'overview.png'}")


if __name__ == "__main__":
    main()
