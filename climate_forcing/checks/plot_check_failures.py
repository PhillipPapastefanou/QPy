#!/usr/bin/env python3
"""
Where and by how much the forcing_checks.py checks fail on the 0.5deg monthly
products (the on-disk tests in tests/consistency/test_forcing_checks.py use
the same data: year 2010, ERA5 as reference). Writes to output/checks/:

  shortwave_vs_toa.png     months with SW > TOA per cell, and SW vs TOA by latitude
  humidity_saturation.png  months with q > 1.05 qsat(Tmax) per cell, and q/qsat vs Tmax
  wind_vs_era5.png         monthly wind vs ERA5 at the same cells, and the correlation per cell
  mask_and_tmin_tmax.png   GLDAS precip/longwave mask mismatch, TerraClimate Tmin > Tmax cells

Usage:
  python plot_check_failures.py [--year 2010]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

import forcing_checks as fc

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plotting"))
from plot_pft_maps import BLUE_RAMP, CATEGORICAL, INK, MUTED, OCEAN, SURFACE  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "output" / "checks"
DATASETS = ["gldas", "terraclimate", "era5land"]
LABELS = {"gldas": "GLDAS", "terraclimate": "TerraClimate", "era5land": "ERA5-Land", "era5": "ERA5"}
SEQ = LinearSegmentedColormap.from_list("blue", ["#ffffff"] + BLUE_RAMP).with_extremes(bad=OCEAN)


def load(name, year):
    return fc.load_monthly(fc.dataset_dir(name, "0.5deg"), fc.DATASETS[name][1], [year])


def toa_like(sw):
    t = sw["time"].to_index()
    lat = fc._lat_broadcast(sw.isel(time=0)).values
    return np.stack([fc.toa_monthly_insolation(lat, y, m) for y, m in zip(t.year, t.month)])


def months_map(ax, bad, valid, lat, lon, title):
    """Number of months per cell flagged; grey ocean where no data."""
    n = np.where(valid.any(0), bad.sum(0), np.nan).astype(float)
    im = ax.imshow(n[::-1] if lat[0] < lat[-1] else n, cmap=SEQ, vmin=0, vmax=12,
                   extent=[lon.min(), lon.max(), lat.min(), lat.max()], interpolation="nearest", aspect="auto")
    style(ax, title)
    return im


def style(ax, title, axes=False):
    ax.set_title(title, fontsize=10, color=INK, loc="left")
    if not axes:
        ax.set_xticks([])
        ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(axes and s.spine_type in ("left", "bottom"))
        s.set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)


def save(fig, name, title):
    fig.suptitle(title, x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout()
    fig.savefig(OUT_DIR / name, dpi=100, facecolor=SURFACE)
    plt.close(fig)


def plot_shortwave(data, year):
    fig, axs = plt.subplots(2, 3, figsize=(16, 8), facecolor=SURFACE)
    for j, name in enumerate(DATASETS):
        sw = data[name]["swvis_srf_down"]
        toa = toa_like(sw)
        v = sw.values
        valid = np.isfinite(v)
        over = valid & (v > toa * 1.02 + 1.0)
        excess = np.where(over, v - toa, np.nan)
        im = months_map(axs[0, j], over, valid, sw.lat.values, sw.lon.values,
                        f"{LABELS[name]}: months with SW > TOA ({over.sum()} values; "
                        f"largest excess {np.nanmax(excess) if over.any() else 0:.0f} W m-2)")
        # zonal view: every land value against the TOA for its latitude/month
        ax = axs[1, j]
        lat_all = np.broadcast_to(sw.lat.values[None, :, None], v.shape)
        ax.scatter(lat_all[valid & ~over], v[valid & ~over], s=1, color=BLUE_RAMP[2], alpha=0.15, rasterized=True,
                   label="SW <= TOA")
        ax.scatter(lat_all[over], v[over], s=4, color=CATEGORICAL[1], rasterized=True, label="SW > TOA")
        lat_line = np.linspace(-90, 90, 361)
        for m, ls in [(1, "-"), (7, "--")]:
            ax.plot(lat_line, fc.toa_monthly_insolation(lat_line, year, m), color=INK, lw=1.2, ls=ls,
                    label=f"TOA {'Jan' if m == 1 else 'Jul'}")
        ax.set_xlim(-90, 90)
        ax.set_xlabel("latitude", color=MUTED)
        ax.set_ylabel("monthly SW [W m-2]", color=MUTED)
        style(ax, f"{LABELS[name]}: SW against latitude, {year}", axes=True)
        ax.legend(fontsize=8, frameon=False, markerscale=3, loc="upper left")
    cb = fig.colorbar(im, ax=axs[0, :], orientation="vertical", fraction=0.015, pad=0.01)
    cb.set_label("months flagged", color=MUTED)
    cb.outline.set_visible(False)
    save(fig, "shortwave_vs_toa.png",
         f"Shortwave above top-of-atmosphere insolation (check: SW > 1.02 TOA + 1 W m-2), {year}")


def plot_humidity(data, year):
    fig, axs = plt.subplots(2, 3, figsize=(16, 8), facecolor=SURFACE)
    for j, name in enumerate(DATASETS):
        f = data[name]
        p = f["press_srf"].values if "press_srf" in f else 101325.0
        ratio = f["q_air"].values / fc.saturation_specific_humidity(f["t_air_max"].values, p)
        valid = np.isfinite(ratio)
        bad = valid & (ratio > 1.05)
        im = months_map(axs[0, j], bad, valid, f["q_air"].lat.values, f["q_air"].lon.values,
                        f"{LABELS[name]}: months with q > 1.05 qsat(Tmax) "
                        f"({bad[valid].mean():.2%} of values, max ratio {np.nanmax(ratio):.2f})")
        ax = axs[1, j]
        tx = f["t_air_max"].values - 273.15
        ax.scatter(tx[valid & ~bad], ratio[valid & ~bad], s=1, color=BLUE_RAMP[2], alpha=0.1, rasterized=True,
                   label="q <= 1.05 qsat")
        ax.scatter(tx[bad], ratio[bad], s=3, color=CATEGORICAL[1], rasterized=True, label="q > 1.05 qsat")
        ax.axhline(1.0, color=INK, lw=1)
        ax.set_yscale("log")
        ax.set_xlabel("monthly mean Tmax [°C]", color=MUTED)
        ax.set_ylabel("q / qsat(Tmax)", color=MUTED)
        style(ax, f"{LABELS[name]}: humidity relative to saturation at Tmax", axes=True)
        ax.legend(fontsize=8, frameon=False, markerscale=3, loc="upper right")
    cb = fig.colorbar(im, ax=axs[0, :], orientation="vertical", fraction=0.015, pad=0.01)
    cb.set_label("months flagged", color=MUTED)
    cb.outline.set_visible(False)
    save(fig, "humidity_saturation.png",
         f"Specific humidity above saturation at the monthly mean Tmax (check: q > 1.05 qsat), {year}")


def plot_wind(data, ref, year):
    fig, axs = plt.subplots(2, 3, figsize=(16, 8), facecolor=SURFACE)
    b_all = ref["wind_air"]
    for j, name in enumerate(DATASETS):
        a = data[name]["wind_air"]
        b = b_all.sel(lat=a["lat"], lon=a["lon"], method="nearest").values
        av = a.values
        ok = np.isfinite(av) & np.isfinite(b)
        r = np.corrcoef(av[ok], b[ok])[0, 1]
        ax = axs[0, j]
        ax.hexbin(b[ok], av[ok], gridsize=70, bins="log", cmap=SEQ, mincnt=1, extent=(0, 12, 0, 12))
        ax.plot([0, 12], [0, 12], color=INK, lw=1)
        ax.set_xlabel("ERA5 monthly wind [m s-1]", color=MUTED)
        ax.set_ylabel(f"{LABELS[name]} [m s-1]", color=MUTED)
        style(ax, f"{LABELS[name]} vs ERA5 wind, all land cells x 12 months: r = {r:.2f} (test needs 0.9)",
              axes=True)
        # per-cell correlation over the 12 months: where the seasonal cycles disagree
        ax = axs[1, j]
        an, bn = av - np.nanmean(av, 0), b - np.nanmean(b, 0)
        with np.errstate(invalid="ignore", divide="ignore"):
            rc = np.nansum(an * bn, 0) / np.sqrt(np.nansum(an ** 2, 0) * np.nansum(bn ** 2, 0))
        rc[~ok.any(0)] = np.nan
        lat, lon = a.lat.values, a.lon.values
        im = ax.imshow(rc[::-1] if lat[0] < lat[-1] else rc,
                       cmap=LinearSegmentedColormap.from_list("d", ["#e34948", "#f0efec", "#2a78d6"]).with_extremes(
                           bad=OCEAN), vmin=-1, vmax=1, extent=[lon.min(), lon.max(), lat.min(), lat.max()],
                       interpolation="nearest", aspect="auto")
        style(ax, f"{LABELS[name]}: correlation of the 12 monthly values with ERA5, per cell")
    cb = fig.colorbar(im, ax=axs[1, :], orientation="vertical", fraction=0.015, pad=0.01)
    cb.set_label("r (seasonal cycle)", color=MUTED)
    cb.outline.set_visible(False)
    save(fig, "wind_vs_era5.png", f"Wind speed against ERA5 (check: r >= 0.9 over all cells and months), {year}")


def plot_mask_and_temperature(data, year):
    fig, axs = plt.subplots(1, 2, figsize=(16, 4.6), facecolor=SURFACE)
    g = data["gldas"]
    m_p = np.isnan(g["precip_total"].values).all(0)
    m_l = np.isnan(g["lw_srf_down"].values).all(0)
    cat = np.full(m_p.shape, np.nan)
    cat[~m_p & ~m_l] = 0
    cat[m_p & ~m_l] = 1
    cat[~m_p & m_l] = 2
    lat, lon = g["precip_total"].lat.values, g["precip_total"].lon.values
    ax = axs[0]
    cmap = matplotlib.colors.ListedColormap(["#dcdad5", CATEGORICAL[1], CATEGORICAL[0]]).with_extremes(bad=OCEAN)
    ax.imshow(cat[::-1] if lat[0] < lat[-1] else cat, cmap=cmap, vmin=-0.5, vmax=2.5,
              extent=[lon.min(), lon.max(), lat.min(), lat.max()], interpolation="nearest", aspect="auto")
    style(ax, f"GLDAS: precip has no data but longwave has ({int((cat == 1).sum())} cells), "
              f"longwave has none but precip has ({int((cat == 2).sum())})")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in [CATEGORICAL[1], CATEGORICAL[0]]]
    ax.legend(handles, ["precip missing only", "longwave missing only"], fontsize=8, frameon=False, loc="lower left")

    t = data["terraclimate"]
    d = t["t_air_min"].values - t["t_air_max"].values
    bad = np.isfinite(d) & (d > 0.05)
    lat, lon = t["t_air_min"].lat.values, t["t_air_min"].lon.values
    im = months_map(axs[1], bad, np.isfinite(d), lat, lon,
                    f"TerraClimate: months with Tmin > Tmax ({bad.sum()} values, worst by {np.nanmax(d):.1f} K)")
    cb = fig.colorbar(im, ax=axs[1], fraction=0.025, pad=0.01)
    cb.set_label("months flagged", color=MUTED)
    cb.outline.set_visible(False)
    save(fig, "mask_and_tmin_tmax.png", f"GLDAS land mask mismatch and TerraClimate Tmin/Tmax order, {year}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2010)
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = {name: load(name, args.year) for name in DATASETS}
    ref = load("era5", args.year)
    plot_shortwave(data, args.year)
    plot_humidity(data, args.year)
    plot_wind(data, ref, args.year)
    plot_mask_and_temperature(data, args.year)
    print(f"plots in {OUT_DIR}")


if __name__ == "__main__":
    main()
