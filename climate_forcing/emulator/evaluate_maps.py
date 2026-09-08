"""Diagnostic: for every grid point (not just the held-out split), reconstruct the
full emulated monthly series and compare it to the real data. Produces, per
variable:
  - snapshot_map_<var>.png: a 3x2 figure - real vs. emulated world maps at two
    representative months (Jan/Jul of the record's middle year) on top, and
    mean/max |deviation| over the whole record (native units, log color scale
    for heavy-tailed log1p variables like precip) on the bottom row, so the
    snapshots and the error summary are always seen together
  - mean_map_<var>.png: time-mean real field, time-mean emulated field (shared
    color scale), and mean/max |deviation| again - all in native units, for
    context on the field's actual (climatological, not single-month) magnitude
  - strongest_deviation_map_<var>.png: the SIGNED deviation (native units) at
    each point's single worst month (so over- vs under-prediction is visible,
    not just magnitude)

Plot titles are prefixed with a data-source label (default: derived from
--input's filename, e.g. era5_global_forcing_....zarr -> "ERA5"; override with
--source-label) so maps from different forcing products don't get mixed up.
deviation_summary.json still also records the relative (%) deviation numbers
per variable, for comparing error magnitude across variables on very different
physical scales - only the plots themselves are absolute-only.

This intentionally covers the FULL grid (train + held-out points together):
train_emulator.py's held-out RMSE/R2 (in eval_summary.json) is the honest
generalization number, but it only samples ~10% of points scattered across the
globe. These maps instead show, everywhere, how far the network's limited
capacity falls short of exactly reproducing the real field - useful for
spotting whole regions (mountains, coastlines, deserts) where the emulator
systematically struggles.

Usage:
    python -m climate_forcing.emulator.evaluate_maps \
        --input /path/to/....zarr --weights climate_forcing/emulator/weights.json \
        --output-dir climate_forcing/emulator
"""

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from climate_forcing.emulator.train_emulator import (
    VAR_ALIASES, fourier_features, load_weights, mlp_forward_branched_np, sample_grid_np,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to the .zarr (or .nc) global forcing store")
    ap.add_argument("--weights", required=True, help="Path to weights.json produced by train_emulator.py")
    ap.add_argument("--output-dir", required=True, help="Directory to write deviation_map_<var>.png + summary json")
    ap.add_argument("--source-label", default=None,
                     help="Data source name shown in plot titles, e.g. ERA5 (default: derived from "
                          "--input's filename, e.g. era5_global_forcing_....zarr -> ERA5)")
    args = ap.parse_args()

    W, grid, trunk_layers, shared_head, precip_head_layers, basis = load_weights(args.weights)
    meta = W["meta"]
    variables = meta["variables"]
    source_label = args.source_label or meta.get("source_label") \
        or os.path.basename(args.input.rstrip("/")).split("_")[0].upper()
    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Opening {args.input} ...")
    ds = xr.open_zarr(args.input, consolidated=False) if args.input.endswith(".zarr") \
        else xr.open_dataset(args.input)
    ds = ds.rename({src: canon for src, canon in VAR_ALIASES.items()
                     if src in ds.data_vars and canon not in ds.data_vars})
    # normalize lat to descending (north-to-south), matching ERA5's native order.
    # GLDAS (and possibly other sources) ship lat ascending instead; the imshow
    # calls below use origin="upper" with extent=[..., lat.min(), lat.max()],
    # which implicitly assumes row 0 of the reshaped (n_lat, n_lon) array is
    # lat.max() - true for ERA5, false (and silently flipped top-to-bottom) for
    # any dataset shipped lat-ascending.
    ds = ds.sortby("lat", ascending=False)
    lat = ds["lat"].values
    lon = ds["lon"].values
    n_time = ds.sizes["time"]
    n_lat, n_lon = len(lat), len(lon)

    # this is a land-ecosystem forcing file (QUINCY): ocean cells were stripped to
    # NaN in the met variables (the two deposition variables still cover ocean,
    # but we mask everything the same way for a consistent set of maps).
    land_mask = ~np.isnan(ds[variables[0]].isel(time=0).values)
    land_flat = land_mask.ravel()
    print(f"land fraction: {land_flat.mean():.3f}")

    def mask_ocean(field_2d):
        return np.where(land_mask, field_2d, np.nan)

    lon2d, lat2d = np.meshgrid(lon, lat)
    lon_flat, lat_flat = lon2d.ravel(), lat2d.ravel()
    feats = fourier_features(lon_flat, lat_flat)
    gfeat = sample_grid_np(grid, lon_flat, lat_flat)
    raw = mlp_forward_branched_np(np.concatenate([feats, gfeat], axis=1), trunk_layers, shared_head, precip_head_layers)
    out_mean = np.array(W["output_scaler"]["mean"])
    out_std = np.array(W["output_scaler"]["std"])
    pred_all = raw * out_std + out_mean

    # two snapshot months (Jan/Jul of the record's middle year) for real-vs-emulated
    # map comparisons - picked dynamically so this still works whatever span the
    # dataset covers.
    y0, m0 = (int(v) for v in meta["time_start"].split("-"))
    mid_year = y0 + (m0 - 1 + n_time // 2) // 12

    def month_index(year, month):
        return (year - y0) * 12 + (month - m0)

    snapshots = [(min(max(month_index(mid_year, mo), 0), n_time - 1), f"{mid_year}-{mo:02d}")
                 for mo in (1, 7)]
    print(f"snapshot months: {[label for _, label in snapshots]}")

    summary = {}
    offset = 0
    for var in variables:
        vinfo = W["variables"][var]
        width = vinfo["k_modes"] + 1
        block = pred_all[:, offset:offset + width]
        offset += width
        series_pred = block[:, 0:1] + block[:, 1:] @ basis[var]  # (n_points, n_time)
        if vinfo["log1p"]:
            series_pred = np.expm1(series_pred)

        print(f"loading {var} ...")
        data = ds[var].transpose("time", "lat", "lon").values.astype(np.float32)
        # ocean is genuinely absent (not sparse missingness) for the met variables -
        # leave it as NaN rather than filling; it propagates harmlessly into the
        # (already land-only) stats/display below instead of injecting fake values.
        # A handful of LAND points can still have sparse per-month gaps though (seen
        # in GLDAS's rain/precip_total) - a single NaN month would otherwise poison
        # that point's entire row-wise mean/max (dev.mean(axis=1) etc. below) with
        # NaN, which then poisons np.percentile too. Fill only those (never ocean),
        # same per-timestep cross-sectional mean train_emulator.py uses.
        truth = data.reshape(n_time, -1).T
        gap_mask = np.isnan(truth) & land_flat[:, None]
        if gap_mask.any():
            col_mean = np.nanmean(truth, axis=0, keepdims=True)
            truth = np.where(gap_mask, col_mean, truth)

        dev_signed = series_pred - truth
        dev = np.abs(dev_signed)
        mean_abs_dev_flat = dev.mean(axis=1)
        max_abs_dev_flat = dev.max(axis=1)

        # signed value of each point's single worst month (not just its magnitude) -
        # shows whether the emulator's biggest miss over/under-shoots, and when.
        worst_t_per_point = dev.argmax(axis=1)
        strongest_signed_flat = dev_signed[np.arange(dev.shape[0]), worst_t_per_point]

        # relative deviation: each point's error as a % of that point's own typical
        # magnitude (mean |real value| over the whole record), not the raw physical
        # unit - this is what makes e.g. t_air (K) and nhx_srf_down (mg N m-2 day-1)
        # comparable on the same 0-100%-ish scale, and reveals points where the
        # emulator does badly in *relative* terms even if the absolute error looks
        # small. Points with near-zero typical magnitude (e.g. deserts for precip)
        # are floored to 1% of the variable's global average magnitude so a few
        # near-zero points don't produce meaningless thousand-percent spikes.
        point_scale = np.abs(truth).mean(axis=1)  # NaN for ocean rows (fine - only land is ever used)
        scale_floor = max(point_scale[land_flat].mean() * 0.01, 1e-9)
        safe_scale = np.where(land_flat, np.maximum(np.nan_to_num(point_scale), scale_floor), 1.0)
        rel_mean_dev_flat = mean_abs_dev_flat / safe_scale * 100
        rel_max_dev_flat = max_abs_dev_flat / safe_scale * 100
        rel_strongest_flat = strongest_signed_flat / safe_scale * 100

        mean_abs_dev = mean_abs_dev_flat.reshape(n_lat, n_lon)
        max_abs_dev = max_abs_dev_flat.reshape(n_lat, n_lon)

        # stats are over LAND points only - this forcing exists to drive a land
        # ecosystem model, so ocean-cell deviations aren't meaningful here.
        land_worst_idx = np.flatnonzero(land_flat)[max_abs_dev_flat[land_flat].argmax()]
        summary[var] = {
            "global_mean_abs_dev": float(mean_abs_dev_flat[land_flat].mean()),
            "global_max_abs_dev": float(max_abs_dev_flat[land_flat].max()),
            "global_mean_relative_dev_pct": float(rel_mean_dev_flat[land_flat].mean()),
            "global_median_relative_dev_pct": float(np.median(rel_mean_dev_flat[land_flat])),
            "worst_point_lon": float(lon2d.ravel()[land_worst_idx]),
            "worst_point_lat": float(lat2d.ravel()[land_worst_idx]),
            "worst_point_month_index": int(worst_t_per_point[land_worst_idx]),
        }

        unit = W["variables"][var].get("unit", "")
        unit_suffix = f" ({unit})" if unit else ""

        # log1p-trained variables (precip_total) are heavy-tailed - the same
        # values that make a linear map useless (a few wet-tropics pixels blow
        # out the scale so deserts and drizzle both read as "zero") make a log
        # color scale the honest choice here. Zero/negative values can't sit on
        # a log scale, so they're floored to a small fraction of the panel's own
        # max rather than dropped, which keeps them visible as "very small"
        # instead of breaking LogNorm or vanishing.
        use_log_color = vinfo["log1p"]

        def log_floor_clip(field, vmax_ref):
            floor = max(vmax_ref * 1e-3, 1e-6)
            return np.where(np.isnan(field), np.nan, np.maximum(field, floor)), floor

        # absolute (native-unit) deviation - mean and max |deviation| over the
        # whole record, not normalized by each point's own magnitude. Simpler to
        # read directly in physical units, at the cost of not being comparable
        # across variables on wildly different scales (see deviation_summary.json
        # for the relative/% numbers instead, if that comparison is needed).
        # Plotted below as the bottom row of the combined snapshot+deviation figure.
        vmax_mean = np.percentile(mean_abs_dev_flat[land_flat], 99)
        vmax_max = np.percentile(max_abs_dev_flat[land_flat], 99)
        print(f"  {var}: global_mean_abs_dev={summary[var]['global_mean_abs_dev']:.4g}{unit_suffix}  "
              f"global_mean_relative_dev={summary[var]['global_mean_relative_dev_pct']:.3g}%")

        # time-mean real field, time-mean emulated field (same color scale, for a
        # direct visual comparison), and the mean/max |deviation| again - all in
        # native units, side by side with the actual field magnitudes for context.
        avg_real = mask_ocean(truth.mean(axis=1).reshape(n_lat, n_lon))
        avg_pred = mask_ocean(series_pred.mean(axis=1).reshape(n_lat, n_lon))
        avg_vmin = np.nanmin([np.nanmin(avg_real), np.nanmin(avg_pred)])
        avg_vmax = np.nanmax([np.nanmax(avg_real), np.nanmax(avg_pred)])
        dev_vmax_mean = vmax_mean
        dev_vmax_max = vmax_max

        fig, axes = plt.subplots(2, 2, figsize=(13, 8))
        for ax, field, title in zip(axes[0], [avg_real, avg_pred], ["real (mean over record)", "emulated (mean over record)"]):
            ax.set_facecolor("#dcdcdc")
            if use_log_color:
                clipped, floor = log_floor_clip(field, avg_vmax)
                im = ax.imshow(clipped, extent=[lon.min(), lon.max(), lat.min(), lat.max()],
                                origin="upper", aspect="auto", cmap="viridis",
                                norm=matplotlib.colors.LogNorm(vmin=floor, vmax=avg_vmax))
            else:
                im = ax.imshow(field, extent=[lon.min(), lon.max(), lat.min(), lat.max()],
                                origin="upper", aspect="auto", cmap="viridis", vmin=avg_vmin, vmax=avg_vmax)
            fig.colorbar(im, ax=ax, shrink=0.8)
            ax.set_title(f"{title}{unit_suffix}" + (" [log scale]" if use_log_color else ""))
            ax.set_xlabel("lon"); ax.set_ylabel("lat")
        for ax, field, title, vmax in zip(axes[1], [mask_ocean(mean_abs_dev), mask_ocean(max_abs_dev)],
                                           ["mean |deviation|", "max |deviation|"], [dev_vmax_mean, dev_vmax_max]):
            ax.set_facecolor("#dcdcdc")
            if use_log_color:
                clipped, floor = log_floor_clip(field, vmax)
                im = ax.imshow(clipped, extent=[lon.min(), lon.max(), lat.min(), lat.max()],
                                origin="upper", aspect="auto", cmap="inferno",
                                norm=matplotlib.colors.LogNorm(vmin=floor, vmax=vmax))
            else:
                im = ax.imshow(field, extent=[lon.min(), lon.max(), lat.min(), lat.max()],
                                origin="upper", aspect="auto", cmap="inferno", vmin=0, vmax=vmax)
            fig.colorbar(im, ax=ax, shrink=0.8, extend="max")
            ax.set_title(f"{title}{unit_suffix}" + (" [log scale]" if use_log_color else ""))
            ax.set_xlabel("lon"); ax.set_ylabel("lat")
        fig.suptitle(f"{source_label} {var}: absolute values and deviation on land "
                     f"(native units{', log color scale' if use_log_color else ''}), "
                     f"{meta['time_start']} to +{n_time} months")
        fig.tight_layout()
        path = os.path.join(args.output_dir, f"mean_map_{var}.png")
        fig.savefig(path, dpi=110)
        plt.close(fig)
        print(f"wrote {path}")

        # strongest single-month deviation, signed and absolute (red = emulator
        # overshoots, blue = undershoots, in native units)
        vext = np.percentile(np.abs(strongest_signed_flat[land_flat]), 99) or 1.0
        fig, ax = plt.subplots(figsize=(8, 4.2))
        ax.set_facecolor("#dcdcdc")
        im = ax.imshow(mask_ocean(strongest_signed_flat.reshape(n_lat, n_lon)),
                        extent=[lon.min(), lon.max(), lat.min(), lat.max()],
                        origin="upper", aspect="auto", cmap="RdBu_r", vmin=-vext, vmax=vext)
        ax.set_title(f"{source_label} {var}: strongest single-month deviation on land "
                     f"(emulated - real{unit_suffix})")
        ax.set_xlabel("lon")
        ax.set_ylabel("lat")
        fig.colorbar(im, ax=ax, shrink=0.85, extend="both")
        fig.tight_layout()
        path = os.path.join(args.output_dir, f"strongest_deviation_map_{var}.png")
        fig.savefig(path, dpi=110)
        plt.close(fig)
        print(f"wrote {path}")

        # real vs. emulated snapshots at two representative months (seasonal contrast),
        # plus a third row with the mean/max |deviation| over the whole record (native
        # units) - combined into one figure so the snapshots and the error summary for
        # a variable are always viewed together instead of across separate files.
        fig, axes = plt.subplots(3, 2, figsize=(13, 12))
        panel_vmin = min(truth[land_flat, t].min() for t, _ in snapshots)
        panel_vmax = max(truth[land_flat, t].max() for t, _ in snapshots)
        for row, (t_idx, label) in enumerate(snapshots):
            for col, (field_flat, name) in enumerate([(truth[:, t_idx], "real"), (series_pred[:, t_idx], "emulated")]):
                ax = axes[row][col]
                ax.set_facecolor("#dcdcdc")
                im = ax.imshow(mask_ocean(field_flat.reshape(n_lat, n_lon)),
                                extent=[lon.min(), lon.max(), lat.min(), lat.max()],
                                origin="upper", aspect="auto", cmap="viridis", vmin=panel_vmin, vmax=panel_vmax)
                ax.set_title(f"{name} {label}{unit_suffix}")
                ax.set_xlabel("lon")
                ax.set_ylabel("lat")
                fig.colorbar(im, ax=ax, shrink=0.8)
        for ax, field, title, vmax in zip(axes[2], [mask_ocean(mean_abs_dev), mask_ocean(max_abs_dev)],
                                           [f"mean |deviation|{unit_suffix}", f"max |deviation|{unit_suffix}"],
                                           [vmax_mean, vmax_max]):
            ax.set_facecolor("#dcdcdc")
            if use_log_color:
                clipped, floor = log_floor_clip(field, vmax)
                im = ax.imshow(clipped, extent=[lon.min(), lon.max(), lat.min(), lat.max()],
                                origin="upper", aspect="auto", cmap="inferno",
                                norm=matplotlib.colors.LogNorm(vmin=floor, vmax=vmax))
            else:
                im = ax.imshow(field, extent=[lon.min(), lon.max(), lat.min(), lat.max()],
                                origin="upper", aspect="auto", cmap="inferno", vmin=0, vmax=vmax)
            fig.colorbar(im, ax=ax, shrink=0.8, extend="max")
            ax.set_title(title + (" [log scale]" if use_log_color else ""))
            ax.set_xlabel("lon")
            ax.set_ylabel("lat")
        fig.suptitle(f"{source_label} {var}: real vs emulated snapshots and absolute deviation on land, "
                     f"{meta['time_start']} to +{n_time} months")
        fig.tight_layout()
        path = os.path.join(args.output_dir, f"snapshot_map_{var}.png")
        fig.savefig(path, dpi=110)
        plt.close(fig)
        print(f"wrote {path}")

    summary_path = os.path.join(args.output_dir, "deviation_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()
