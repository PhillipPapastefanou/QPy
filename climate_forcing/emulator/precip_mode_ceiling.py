"""Cheap check (no network training) of whether precip's point-level extreme-year
predictability CEILING would improve with more SVD modes, before committing to a
full retrain. Runs one randomized_svd at a generous k_max, then truncates to
several smaller k to see how the "oracle" (best-possible-loadings) per-point
annual-anomaly correlation moves with mode count - since singular vectors are
ordered by variance explained, truncating a k_max decomposition gives the same
answer as rerunning SVD at each smaller k, so this only costs ONE decomposition.

Usage:
    python -m climate_forcing.emulator.precip_mode_ceiling --input /path/to/....zarr
"""

import argparse

import numpy as np
import xarray as xr
from sklearn.utils.extmath import randomized_svd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--var", default="precip_total")
    ap.add_argument("--k-max", type=int, default=250)
    ap.add_argument("--k-values", type=int, nargs="+", default=[24, 48, 64, 96, 128, 160, 200, 250])
    ap.add_argument("--n-points", type=int, default=2000)
    args = ap.parse_args()

    ds = xr.open_zarr(args.input, consolidated=False) if args.input.endswith(".zarr") else xr.open_dataset(args.input)
    land_mask = ~np.isnan(ds[args.var].isel(time=0).values)
    land_flat = land_mask.ravel()
    n_time = ds.sizes["time"]

    print(f"loading {args.var} ...")
    data = ds[args.var].transpose("time", "lat", "lon").values.astype(np.float32)
    matrix = data.reshape(n_time, -1).T[land_flat]
    work = np.log1p(np.clip(matrix, 0, None))
    level = work.mean(axis=1, keepdims=True)
    anomaly = work - level

    print(f"running randomized_svd with k_max={args.k_max} on {anomaly.shape} ...")
    U, S, Vt = randomized_svd(anomaly, n_components=args.k_max, random_state=0)

    y0, m0 = (int(v) for v in str(np.datetime_as_string(ds["time"].values[0], unit="M")).split("-"))
    years = np.array([y0 + (m0 - 1 + t) // 12 for t in range(n_time)])
    months = np.array([((m0 - 1 + t) % 12) + 1 for t in range(n_time)])
    uyears = np.unique(years)

    rng = np.random.default_rng(0)
    sample_idx = rng.choice(anomaly.shape[0], size=min(args.n_points, anomaly.shape[0]), replace=False)

    def annual_anomaly(series, months_, years_, uyears_):
        clim = np.array([series[months_ == mo].mean() for mo in range(1, 13)])
        anom = series - clim[months_ - 1]
        return np.array([anom[years_ == y].mean() for y in uyears_])

    truth_native = np.expm1(work[sample_idx])
    real_annual = [annual_anomaly(truth_native[i], months, years, uyears) for i in range(len(sample_idx))]

    for k in args.k_values:
        if k > args.k_max:
            continue
        basis_k = Vt[:k]
        recon = level[sample_idx] + (U[sample_idx, :k] * S[:k]) @ basis_k
        recon_native = np.expm1(recon)
        corrs = np.full(len(sample_idx), np.nan)
        for i in range(len(sample_idx)):
            if real_annual[i].std() <= 1e-9:
                continue
            pred_annual = annual_anomaly(recon_native[i], months, years, uyears)
            corrs[i] = np.corrcoef(real_annual[i], pred_annual)[0, 1]
        valid = ~np.isnan(corrs)
        var_expl = 1 - ((anomaly - (U[:, :k] * S[:k]) @ basis_k) ** 2).sum() / (anomaly ** 2).sum()
        print(f"k={k:4d}  var_explained={var_expl:.3f}  "
              f"oracle per-point annual-anomaly corr: mean={np.mean(corrs[valid]):.3f} "
              f"median={np.median(corrs[valid]):.3f}  p10={np.percentile(corrs[valid], 10):.3f}")


if __name__ == "__main__":
    main()
