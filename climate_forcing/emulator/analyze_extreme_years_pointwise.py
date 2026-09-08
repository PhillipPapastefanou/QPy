"""Follow-up to analyze_extreme_years.py: that script found the GLOBAL-MEAN
annual anomaly is captured almost perfectly (r=0.99-1.0) for every variable -
so if extreme years still look wrong, the problem likely isn't a global bias,
it's specific POINTS/regions during extreme years getting averaged away in a
global mean. This checks that directly: for a sample of individual land
points, compute the same per-point deseasonalized annual-anomaly correlation
(real vs emulated) and report the distribution - if this is much worse than
the near-perfect global number, that confirms the issue is spatial resolution
of the temporal decomposition (localized extreme events truncated out of the
retained SVD modes), not a systematic global bias a residual-correction stage
would fix.

Usage:
    python -m climate_forcing.emulator.analyze_extreme_years_pointwise \
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
    ap.add_argument("--n-points", type=int, default=2000, help="random land points to sample")
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
    uyears = np.unique(years)

    rng = np.random.default_rng(0)
    land_idx = np.flatnonzero(land_flat)
    sample_idx = rng.choice(land_idx, size=min(args.n_points, len(land_idx)), replace=False)

    lon2d, lat2d = np.meshgrid(lon, lat)
    lon_s, lat_s = lon2d.ravel()[sample_idx], lat2d.ravel()[sample_idx]
    feats = fourier_features(lon_s, lat_s)
    gfeat = sample_grid_np(grid, lon_s, lat_s)
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
        truth = data.reshape(n_time, -1).T[sample_idx]

        # "oracle" reconstruction: the BEST POSSIBLE fit using this variable's
        # actual retained K modes (basis[var], the same fixed temporal basis the
        # network's loadings target) - via least-squares projection of the real
        # anomaly onto that basis, instead of the network's predicted loadings.
        # This isolates SVD-truncation ceiling (how good the oracle is) from
        # network prediction error (gap between oracle and the network's actual
        # per-point correlation computed below) - two different problems needing
        # two different fixes (more modes vs. better spatial prediction).
        work_truth = np.log1p(np.clip(truth, 0, None)) if vinfo["log1p"] else truth
        level_oracle = work_truth.mean(axis=1, keepdims=True)
        anomaly = work_truth - level_oracle
        Bt = basis[var]  # (k, n_time)
        loadings_oracle = anomaly @ Bt.T @ np.linalg.pinv(Bt @ Bt.T)
        series_oracle = level_oracle + loadings_oracle @ Bt
        if vinfo["log1p"]:
            series_oracle = np.expm1(series_oracle)

        # per-point: remove that point's own seasonal cycle, aggregate to annual
        # anomaly, then correlate real vs emulated/oracle across years - same
        # recipe as the global-mean script, just per-point instead of spatially
        # averaged.
        def annual_anomaly(series):
            clim = np.array([series[months == mo].mean() for mo in range(1, 13)])
            anom = series - clim[months - 1]
            return np.array([anom[years == y].mean() for y in uyears])

        corrs = np.full(len(sample_idx), np.nan)
        oracle_corrs = np.full(len(sample_idx), np.nan)
        for i in range(len(sample_idx)):
            real_annual = annual_anomaly(truth[i])
            if real_annual.std() <= 1e-9:
                continue
            pred_annual = annual_anomaly(series_pred[i])
            oracle_annual = annual_anomaly(series_oracle[i])
            corrs[i] = np.corrcoef(real_annual, pred_annual)[0, 1]
            oracle_corrs[i] = np.corrcoef(real_annual, oracle_annual)[0, 1]

        valid = ~np.isnan(corrs)
        print(f"{var}: per-point annual-anomaly correlation over {valid.sum()} land points - "
              f"NETWORK mean={np.mean(corrs[valid]):.3f} median={np.median(corrs[valid]):.3f} "
              f"p10={np.percentile(corrs[valid], 10):.3f}  |  "
              f"ORACLE(same {vinfo['k_modes']} modes, perfect loadings) "
              f"mean={np.mean(oracle_corrs[valid]):.3f} median={np.median(oracle_corrs[valid]):.3f} "
              f"p10={np.percentile(oracle_corrs[valid], 10):.3f}")


if __name__ == "__main__":
    main()
