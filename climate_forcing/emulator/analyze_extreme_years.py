"""Diagnostic: is the emulator's error concentrated in specific ANOMALOUS years
(droughts, heatwaves, strong ENSO years), or spread evenly across the record?

Aggregate-variance metrics (R2, RMSE) are dominated by the seasonal cycle, which
is ~95%+ of a met variable's total variance - a model can nail R2=0.99 while
still getting a specific extreme year's anomaly badly wrong, because that
anomaly is a tiny share of total variance even though it's what matters most
for something like a land ecosystem model driven by this forcing.

This script removes the mean seasonal cycle (climatology) from both the real
data and the reconstruction, spatially averages the remaining anomaly over all
land points for each year, and reports which years the emulator's global-mean
anomaly departs most from the real global-mean anomaly - i.e. which years it
gets most wrong, not just on average but for climatically distinct years.

Usage:
    python -m climate_forcing.emulator.analyze_extreme_years \
        --input /path/to/....zarr --weights climate_forcing/emulator/weights.json
"""

import argparse

import numpy as np
import xarray as xr

from climate_forcing.emulator.train_emulator import (
    VAR_ALIASES, fourier_features, load_weights, mlp_forward_branched_np, sample_grid_np,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--top-n", type=int, default=8, help="how many worst years to print per variable")
    args = ap.parse_args()

    W, grid, trunk_layers, shared_head, precip_head_layers, basis = load_weights(args.weights)
    meta = W["meta"]
    variables = meta["variables"]

    ds = xr.open_zarr(args.input, consolidated=False) if args.input.endswith(".zarr") else xr.open_dataset(args.input)
    ds = ds.rename({src: canon for src, canon in VAR_ALIASES.items()
                     if src in ds.data_vars and canon not in ds.data_vars})
    lat, lon = ds["lat"].values, ds["lon"].values
    n_time = ds.sizes["time"]
    n_lat, n_lon = len(lat), len(lon)
    land_mask = ~np.isnan(ds[variables[0]].isel(time=0).values)
    land_flat = land_mask.ravel()

    y0, m0 = (int(v) for v in meta["time_start"].split("-"))
    years = np.array([y0 + (m0 - 1 + t) // 12 for t in range(n_time)])
    months = np.array([((m0 - 1 + t) % 12) + 1 for t in range(n_time)])

    lon2d, lat2d = np.meshgrid(lon, lat)
    lon_flat, lat_flat = lon2d.ravel()[land_flat], lat2d.ravel()[land_flat]
    feats = fourier_features(lon_flat, lat_flat)
    gfeat = sample_grid_np(grid, lon_flat, lat_flat)
    raw = mlp_forward_branched_np(np.concatenate([feats, gfeat], axis=1), trunk_layers, shared_head, precip_head_layers)
    out_mean = np.array(W["output_scaler"]["mean"])
    out_std = np.array(W["output_scaler"]["std"])
    pred_all = raw * out_std + out_mean

    offset = 0
    for var in variables:
        vinfo = W["variables"][var]
        width = vinfo["k_modes"] + 1
        block = pred_all[:, offset:offset + width]
        offset += width
        series_pred = block[:, 0:1] + block[:, 1:] @ basis[var]
        if vinfo["log1p"]:
            series_pred = np.expm1(series_pred)

        data = ds[var].transpose("time", "lat", "lon").values.astype(np.float32)
        truth = data.reshape(n_time, -1).T[land_flat]

        # global-mean (over all land points) series, real vs emulated
        real_gm = np.nanmean(truth, axis=0)
        pred_gm = np.nanmean(series_pred, axis=0)

        # remove the mean seasonal cycle (per-calendar-month climatology) from
        # each, leaving just the interannual anomaly - this is the part that
        # "extreme years" (droughts, heatwaves, El Nino/La Nina) actually live in.
        real_anom = np.array([real_gm[t] - real_gm[months == months[t]].mean() for t in range(n_time)])
        pred_anom = np.array([pred_gm[t] - pred_gm[months == months[t]].mean() for t in range(n_time)])

        # annual-mean anomaly and how far off the emulator's version is
        uyears = np.unique(years)
        real_annual = np.array([real_anom[years == y].mean() for y in uyears])
        pred_annual = np.array([pred_anom[years == y].mean() for y in uyears])
        err = pred_annual - real_annual

        unit = vinfo.get("unit", "")
        print(f"\n{var} ({unit}): annual-anomaly error, worst {args.top_n} years "
              f"(real anomaly vs emulated anomaly vs error):")
        worst = np.argsort(-np.abs(err))[:args.top_n]
        for i in worst:
            print(f"  {uyears[i]}: real={real_annual[i]:+.4g}  emulated={pred_annual[i]:+.4g}  "
                  f"error={err[i]:+.4g}")
        corr = np.corrcoef(real_annual, pred_annual)[0, 1]
        print(f"  correlation of emulated vs real annual anomaly across all {len(uyears)} years: {corr:.3f}")
        print(f"  RMS annual-anomaly error: {np.sqrt((err ** 2).mean()):.4g}  "
              f"(vs RMS real annual anomaly magnitude: {np.sqrt((real_annual ** 2).mean()):.4g})")


if __name__ == "__main__":
    main()
