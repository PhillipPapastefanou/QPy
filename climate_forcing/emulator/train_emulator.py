"""Train a tiny neural-net emulator of the global monthly forcing file.

Idea: instead of a network that memorizes the full (time) vector per point
(one output per month = 1008 outputs), decompose each variable's
point-by-time matrix into a per-point mean ("level") plus a handful of
shared temporal EOF modes (via truncated SVD). The network only has to
learn the spatial fields of the level and the per-mode loadings from
(lon, lat) - a much smaller, easier-to-learn target - while the temporal
basis (shared across all points) is stored verbatim.

Reconstruction for a query point, done in JS at viewer time:
    series(t) = level + sum_i loading[i] * temporal_basis[i, t]

Spatial model: a smooth Fourier-feature MLP alone (input = sin/cos(lon,lat))
can only represent broad, continent-scale patterns - it has no way to learn
sharp local structure like coastlines, mountains, or patchy convective
precipitation. So the spatial input is a smooth Fourier encoding of
(lon, lat) CONCATENATED with a bilinearly-interpolated lookup into a
trainable feature grid (a la Instant-NGP/NeRF-style hybrid representations):
the grid is a plain nn.Parameter of shape (GRID_LAT, GRID_LON, GRID_CHANNELS)
optimized jointly with the decoder MLP by backprop, so it's free to memorize
whatever local detail actually helps, while still being queryable at any
continuous (lon, lat) via interpolation (both here and in the browser).

Decoder: a shared trunk feeds a single shared final layer for 9 of the 10
variables, PLUS a separate dedicated head (its own extra hidden layer) just
for precip_total. This came from a diagnostic (analyze_extreme_years_pointwise.py)
showing that as precip's mode count grew, the network increasingly couldn't
exploit the extra modes (oracle-vs-network gap widened) - a single shared final
layer serving all 10 variables' combined output was the bottleneck. Giving
precip its own head (branching off the same shared trunk) targets that directly
without taking capacity away from the other 9 variables, which keep exactly the
trunk-depth they had before.

Output: weights.json (small metadata: shapes, per-variable settings,
de-standardization stats) + weights.bin (one flat float32 blob: the feature
grid, then the trunk layers' W/b, then the shared head's W/b, then the precip
head layers' W/b, then each variable's temporal basis, in that fixed order -
so the sizes in weights.json are enough to slice it back apart). No ML
framework is required at inference time - viewer.html reimplements the forward
pass (grid bilinear sample + a few small matrix multiplies) by hand.

Usage:
    python -m climate_forcing.emulator.train_emulator \
        --input /path/to/quincy_global_forcing_0.5deg_1940-auto.zarr \
        --output /path/to/climate_forcing/emulator/weights.json
"""

import argparse
import json
import os
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import xarray as xr
from sklearn.utils.extmath import randomized_svd

# canonical/default variable schema (matches ERA5's naming). precip_total MUST
# be last: it's the only variable with its own decoder head (see Emulator)
# rather than sharing the common final layer, and the head's output is simply
# appended after the shared block - see forward(). Other datasets (GLDAS, ...)
# may use different source names for the same physical quantity (VAR_ALIASES
# below renames them to the canonical name before training) and may be missing
# a variable entirely (main() silently drops any canonical name not present in
# --input, rather than erroring, so K_MODES_OVERRIDE/LOG1P_VARS/etc. below stay
# a single shared config across every dataset regardless of which subset it has).
# t_air_min/t_air_max replace the mean t_air (2026-09-11, matching
# global_forcing_builder.py): the weather generator's MonthlyForcingRecord has
# only tmin/tmax, no mean-t_air field.
VARIABLES = [
    "t_air_min", "t_air_max", "q_air", "press_srf", "wind_air",
    "cloud_cover", "swvis_srf_down", "lw_srf_down", "nhx_srf_down", "noy_srf_down",
    "precip_total",
]
N_LON_HARM = 6
N_LAT_HARM = 6
K_MODES = 24

# feature grid: 1deg cells (half the native 0.5deg resolution - full resolution
# would blow the size budget), circular in longitude, clamped at the poles.
# 128 channels (up from 96) gives more local memorization capacity per cell -
# precip's realized R2 lags well behind its SVD ceiling (0.855 var. explained by
# its modes vs 0.71 held-out R2), suggesting the network/grid, not the temporal
# decomposition, is the bottleneck for its patchy, sub-grid-cell spatial pattern.
GRID_LAT = 181   # rows: lat = 90 .. -90 step 1
GRID_LON = 360   # cols: lon = 0 .. 359 step 1 (wraps)
GRID_CHANNELS = 128

# precip is heavy-tailed (mostly-zero, occasional extreme months) and spatially
# patchy/convective rather than smooth, so the default settings undersell it badly
# (24 linear SVD modes on raw mm only captured ~60% of its variance). log1p tames
# the skew before decomposition (inverted with expm1 at reconstruction time).
# Unlike every other variable here, precip's per-point extreme-year predictability
# CEILING (see precip_mode_ceiling.py) keeps climbing well past 96 modes with no
# sign of flattening (oracle per-point annual-anomaly corr: 0.82 @ 96 modes, 0.90
# @ 200, 0.92 @ 250) - i.e. it's under-provisioned with temporal modes, not
# network-capacity-limited the way nhx/noy were. Basis storage cost is trivial
# (k*n_time floats), so there's little reason not to give it more room. Going
# from 96->160 modes did move the network's actual (not just oracle) per-point
# score (mean corr 0.749->0.771), confirming this lever keeps paying off even
# though the achievability gap (oracle vs network) widens a bit each step up.
K_MODES_OVERRIDE = {"precip_total": 160}

# even with a bigger output share, precip's mapping (lon,lat) -> loadings is
# noisier than the smooth met variables, so it can lag behind in a plain shared
# MSE (easier variables converge faster and dominate the early-stopping signal).
# Up-weighting its contribution to the loss, and using a robust (Huber) loss for
# just its block, keeps gradient attention on it and stops rare extreme-rain
# months from swamping the loadings' training signal the way squared error would.
#
# nhx/noy deposition get the same treatment for the same reason, but the gap
# there is much bigger: a held-out diagnostic (analyze_extreme_years_pointwise.py)
# comparing the network's predicted loadings against the best-possible ("oracle")
# loadings for the SAME retained modes found per-point interannual-anomaly
# correlation of only ~0.4-0.7 (network) vs ~0.94-0.98 (oracle) - i.e. the 24
# modes already contain almost all the real signal, but the network was badly
# under-fitting it. Deposition is even more spatially concentrated/patchy than
# precip (near-zero over most land, large only near agriculture/industry
# sources), so it's exactly the same heavy-tailed-target problem, just with no
# special handling at all before this.
LOG1P_VARS = {"precip_total", "nhx_srf_down", "noy_srf_down"}
LOSS_WEIGHT_OVERRIDE = {"precip_total": 2.0, "nhx_srf_down": 2.0, "noy_srf_down": 2.0}
HUBER_VARS = {"precip_total", "nhx_srf_down", "noy_srf_down"}

# source-dataset variable name -> canonical name (see VARIABLES comment above).
# GLDAS calls precipitation "rain" instead of "precip_total"; add more entries
# here as other forcing products turn up different naming.
VAR_ALIASES = {"rain": "precip_total"}


def k_for(var):
    return K_MODES_OVERRIDE.get(var, K_MODES)


def fourier_features(lon_deg, lat_deg):
    """(N,) lon/lat in degrees -> (N, D) feature matrix. Mirrored exactly in viewer.html."""
    lon_rad = np.deg2rad(lon_deg)
    lat_rad = np.deg2rad(lat_deg)
    lat_norm = lat_deg / 90.0

    feats = [lat_norm]
    for k in range(1, N_LON_HARM + 1):
        feats.append(np.sin(k * lon_rad))
        feats.append(np.cos(k * lon_rad))
    for k in range(1, N_LAT_HARM + 1):
        feats.append(np.sin(k * lat_rad))
        feats.append(np.cos(k * lat_rad))
    feats.append(lat_norm * np.sin(lon_rad))
    feats.append(lat_norm * np.cos(lon_rad))
    return np.stack(feats, axis=-1)


class Emulator(nn.Module):
    """Input x is [fourier_features..., lon_deg, lat_deg] (the last 2 columns are
    raw degrees, used only for the grid lookup - see forward()).

    Decoder is a shared trunk -> [shared final layer for 9 variables] plus a
    separate dedicated head (extra hidden layer) for precip_total, branching
    off the same trunk output - see module docstring for why."""

    def __init__(self, n_fourier, n_out, precip_width, grid_shape=(GRID_LAT, GRID_LON, GRID_CHANNELS),
                 hidden=(128, 128), precip_head_hidden=256, precip_grid_shape=None):
        super().__init__()
        self.grid_h, self.grid_w, self.grid_c = grid_shape
        self.grid = nn.Parameter(torch.empty(*grid_shape).uniform_(-0.01, 0.01))
        # optional second feature grid read only by the precip head (experimental,
        # --precip-grid-deg): precip's patchy pattern gets its own local capacity
        # without competing with the smooth variables for the shared grid's channels
        self.pgrid = None if precip_grid_shape is None else \
            nn.Parameter(torch.empty(*precip_grid_shape).uniform_(-0.01, 0.01))
        pgrid_c = 0 if precip_grid_shape is None else precip_grid_shape[2]

        dims = [n_fourier + self.grid_c] + list(hidden)
        trunk_layers = []
        for i in range(len(dims) - 1):
            trunk_layers.append(nn.Linear(dims[i], dims[i + 1]))
            trunk_layers.append(nn.Tanh())
        self.trunk = nn.Sequential(*trunk_layers)

        shared_width = n_out - precip_width
        self.shared_head = nn.Linear(dims[-1], shared_width)
        self.precip_head = nn.Sequential(
            nn.Linear(dims[-1] + pgrid_c, precip_head_hidden), nn.Tanh(),
            nn.Linear(precip_head_hidden, precip_width),
        )

    def sample_grid(self, lon_deg, lat_deg, g=None):
        """Bilinear lookup, circular in longitude, clamped at the poles.
        Mirrored exactly by sampleGrid() in viewer.html."""
        g = self.grid if g is None else g
        H, W = g.shape[0], g.shape[1]
        lon = torch.remainder(lon_deg, 360.0)
        x = lon / 360.0 * W
        y = (90.0 - lat_deg) / 180.0 * (H - 1)

        x0 = torch.floor(x).long() % W
        x1 = (x0 + 1) % W
        y0 = torch.clamp(torch.floor(y).long(), 0, H - 2)
        y1 = y0 + 1

        fx = (x - torch.floor(x)).unsqueeze(-1)
        fy = (y - y0.float()).unsqueeze(-1)

        top = g[y0, x0] * (1 - fx) + g[y0, x1] * fx
        bot = g[y1, x0] * (1 - fx) + g[y1, x1] * fx
        return top * (1 - fy) + bot * fy

    def forward(self, x):
        feats, lon_deg, lat_deg = x[:, :-2], x[:, -2], x[:, -1]
        gfeat = self.sample_grid(lon_deg, lat_deg)
        trunk_out = self.trunk(torch.cat([feats, gfeat], dim=1))
        shared_out = self.shared_head(trunk_out)
        precip_in = trunk_out if self.pgrid is None else \
            torch.cat([trunk_out, self.sample_grid(lon_deg, lat_deg, self.pgrid)], dim=1)
        precip_out = self.precip_head(precip_in)
        return torch.cat([shared_out, precip_out], dim=1)


def load_weights(json_path):
    """Load weights.json + its sidecar .bin into plain numpy arrays:
    (meta_all, grid, trunk_layers, shared_head, precip_head_layers, basis).
    trunk_layers/precip_head_layers are lists of (W, b) numpy arrays; shared_head
    is a single (W, b) pair; basis is {variable: (k, n_time) array}. Shared by
    evaluate_maps.py so the binary layout is only defined in one place (see
    module docstring)."""
    with open(json_path) as f:
        meta_all = json.load(f)
    bin_path = os.path.join(os.path.dirname(json_path) or ".", meta_all["meta"]["bin_file"])
    blob = np.fromfile(bin_path, dtype=np.float32)

    pos = 0

    def take(shape):
        nonlocal pos
        n = int(np.prod(shape))
        arr = blob[pos:pos + n].reshape(shape)
        pos += n
        return arr

    grid = take(meta_all["meta"]["grid_shape"])
    mlp = meta_all["mlp"]
    trunk_layers = [(take(l["W_shape"]), take(l["b_shape"])) for l in mlp["trunk_layers"]]
    shared_head = (take(mlp["shared_head"]["W_shape"]), take(mlp["shared_head"]["b_shape"]))
    precip_head_layers = [(take(l["W_shape"]), take(l["b_shape"])) for l in mlp["precip_head_layers"]]
    basis = {var: take(meta_all["variables"][var]["basis_shape"]) for var in meta_all["meta"]["variables"]}
    return meta_all, grid, trunk_layers, shared_head, precip_head_layers, basis


def sample_grid_np(grid, lon_deg, lat_deg):
    """numpy mirror of Emulator.sample_grid / viewer.html's sampleGrid()."""
    H, W, _ = grid.shape
    lon = np.mod(lon_deg, 360.0)
    x = lon / 360.0 * W
    y = (90.0 - lat_deg) / 180.0 * (H - 1)
    x0 = np.floor(x).astype(np.int64) % W
    x1 = (x0 + 1) % W
    y0 = np.clip(np.floor(y).astype(np.int64), 0, H - 2)
    y1 = y0 + 1
    fx = (x - np.floor(x))[:, None]
    fy = (y - y0.astype(np.float64))[:, None]
    top = grid[y0, x0] * (1 - fx) + grid[y0, x1] * fx
    bot = grid[y1, x0] * (1 - fx) + grid[y1, x1] * fx
    return top * (1 - fy) + bot * fy


def mlp_forward_np(x, layers):
    h = x
    for i, (W, b) in enumerate(layers):
        h = h @ W + b
        if i < len(layers) - 1:
            h = np.tanh(h)
    return h


def mlp_forward_branched_np(x, trunk_layers, shared_head, precip_head_layers):
    """numpy mirror of Emulator.forward()'s trunk -> {shared_head, precip_head}
    branching. Returns the same flat (shared..., precip...) concatenation as the
    torch model, matching VARIABLES' order (precip_total last). Unlike
    mlp_forward_np, every trunk layer gets a tanh (the trunk is a pure
    Linear+Tanh stack - shared_head/precip_head's final layers are the
    un-activated projections)."""
    h = x
    for W, b in trunk_layers:
        h = np.tanh(h @ W + b)
    trunk_out = h
    W_s, b_s = shared_head
    shared_out = trunk_out @ W_s + b_s
    precip_out = mlp_forward_np(trunk_out, precip_head_layers)
    return np.concatenate([shared_out, precip_out], axis=1)


def decompose(matrix, k):
    """matrix: (n_points, n_time) -> level (n_points,), loadings (n_points, k), basis (k, n_time)."""
    level = matrix.mean(axis=1)
    anomaly = matrix - level[:, None]
    U, S, Vt = randomized_svd(anomaly, n_components=k, random_state=0)
    loadings = U * S[None, :]
    return level, loadings, Vt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to the .zarr (or .nc) global forcing store")
    ap.add_argument("--output", required=True, help="Path to write weights.json")
    ap.add_argument("--sample-stride", type=int, default=1,
                     help="Use every Nth grid point for training (1 = all points)")
    ap.add_argument("--torch-threads", type=int, default=0,
                     help="torch.set_num_threads (0 = leave at default, e.g. from $SLURM_CPUS_PER_TASK)")
    ap.add_argument("--source-label", default=None,
                     help="Data source name recorded in weights.json and shown by viewer.html, e.g. ERA5 "
                          "(default: derived from --input's filename, e.g. era5_global_forcing_....zarr -> ERA5)")
    # experiment switches (defaults reproduce the production configuration)
    # "variance" is the default since 2026-10-11: on ERA5 it raised held-out precip R2 0.774 -> 0.832
    # (pressure 0.966 -> 0.983, N deposition 0.942 -> 0.978) at identical size; "standardized" is the
    # previous behaviour, kept for comparison
    ap.add_argument("--loss-weighting", choices=["standardized", "variance"], default="variance",
                     help="standardized: every output column scaled to unit std (each SVD mode weighs the "
                          "same); variance: one scale per variable so the loss equals the reconstruction "
                          "error of the series (modes weighted by the variance they carry)")
    ap.add_argument("--k-precip", type=int, default=None, help="SVD modes for precip_total")
    ap.add_argument("--grid-deg", type=float, default=1.0, help="shared feature grid spacing (deg)")
    ap.add_argument("--grid-channels", type=int, default=GRID_CHANNELS)
    ap.add_argument("--precip-grid-deg", type=float, default=0.0,
                     help="spacing of a dedicated precip feature grid (0 = none)")
    ap.add_argument("--precip-grid-channels", type=int, default=32)
    args = ap.parse_args()
    if args.k_precip:
        K_MODES_OVERRIDE["precip_total"] = args.k_precip
    source_label = args.source_label or os.path.basename(args.input.rstrip("/")).split("_")[0].upper()

    t0 = time.time()
    print(f"Opening {args.input} ...")
    ds = xr.open_zarr(args.input, consolidated=False) if args.input.endswith(".zarr") \
        else xr.open_dataset(args.input)
    ds = ds.rename({src: canon for src, canon in VAR_ALIASES.items()
                     if src in ds.data_vars and canon not in ds.data_vars})

    wanted = list(VARIABLES)
    if "t_air_min" not in ds.data_vars and "t_air_max" not in ds.data_vars and "t_air" in ds.data_vars:
        # stores without Tmin/Tmax (ERA5 so far) keep their mean temperature rather
        # than losing temperature altogether
        wanted = ["t_air"] + [v for v in wanted if v not in ("t_air_min", "t_air_max")]
        print("note: no t_air_min/t_air_max in the store - training on mean t_air instead")
    variables = [v for v in wanted if v in ds.data_vars]
    missing = [v for v in wanted if v not in ds.data_vars]
    if missing:
        print(f"note: {args.input} has no {missing} - training on {variables} instead")

    # some sources report a variable as a time-invariant climatology instead
    # of a real time series (e.g. TerraClimate's press_srf, derived once from
    # elevation - see global_forcing_builder.py's MetSourceConfig.static_variables).
    # the whole pipeline below (SVD temporal basis, per-point loadings) only
    # makes sense for a variable that actually varies over time, so drop
    # anything missing a time dimension rather than crashing on it.
    static = [v for v in variables if "time" not in ds[v].dims]
    if static:
        variables = [v for v in variables if v not in static]
        print(f"note: {static} has no time dimension (time-invariant climatology) - "
              f"skipping, since there's no time series to emulate")
    if variables[-1] != "precip_total":
        print(f"note: precip_total not present, so {variables[-1]} (the new last variable) "
              f"gets the dedicated decoder head instead - see Emulator/module docstring")

    lat = ds["lat"].values
    lon = ds["lon"].values
    n_time = ds.sizes["time"]
    time_start = str(np.datetime_as_string(ds["time"].values[0], unit="M"))
    print(f"grid: {len(lat)} lat x {len(lon)} lon, {n_time} months, start {time_start}")

    # this is a land-ecosystem forcing file (QUINCY): ocean cells have been
    # stripped to NaN in the met variables (t_air_min's static NaN pattern is the
    # reference - the two deposition variables still cover ocean too, but we
    # train everything on the same land-only point set for a single shared model).
    land_mask_flat = (~np.isnan(ds[variables[0]].isel(time=0).values)).ravel()[::args.sample_stride]
    print(f"land fraction: {land_mask_flat.mean():.3f} ({land_mask_flat.sum()} of {land_mask_flat.size} points)")

    lon2d, lat2d = np.meshgrid(lon, lat)
    lon_flat = lon2d.ravel()[::args.sample_stride][land_mask_flat]
    lat_flat = lat2d.ravel()[::args.sample_stride][land_mask_flat]
    n_fourier = fourier_features(lon_flat[:1], lat_flat[:1]).shape[1]
    # last 2 columns are raw lon/lat degrees, consumed by Emulator.forward() for the grid lookup
    features = np.concatenate([
        fourier_features(lon_flat, lat_flat),
        lon_flat[:, None], lat_flat[:, None],
    ], axis=1).astype(np.float32)
    print(f"features: {features.shape} ({n_fourier} fourier + lon,lat)")

    n_points = features.shape[0]
    rng = np.random.default_rng(0)
    test_mask = rng.random(n_points) < 0.1
    train_idx = np.where(~test_mask)[0]
    test_idx = np.where(test_mask)[0]
    print(f"holdout split: {len(train_idx)} train points, {len(test_idx)} held-out points")

    # internal validation split (for early stopping + progress reporting during training),
    # carved out of train_idx and decided now so both truth slices can be gathered in one
    # pass over each variable's raw matrix below (loading it twice would be wasteful).
    val_perm = np.random.default_rng(2).permutation(len(train_idx))
    n_val = max(1, int(0.05 * len(train_idx)))
    val_pos, fit_pos = val_perm[:n_val], val_perm[n_val:]
    val_idx = train_idx[val_pos]

    targets = []
    out_mean = []
    out_std = []
    payload_vars = {}
    basis_np = {}
    test_truth = {}
    val_truth = {}
    block_slices = {}

    for var in variables:
        k = k_for(var)
        log1p = var in LOG1P_VARS
        print(f"decomposing {var} (k={k}, log1p={log1p}) ...")
        data = ds[var].transpose("time", "lat", "lon").values.astype(np.float32)
        matrix = data.reshape(n_time, -1).T[::args.sample_stride][land_mask_flat]
        if np.isnan(matrix).any():
            # rare sparse gaps within land, not the (already excluded) ocean mask
            col_mean = np.nanmean(matrix, axis=0, keepdims=True)
            matrix = np.where(np.isnan(matrix), col_mean, matrix)

        test_truth[var] = matrix[test_idx]
        val_truth[var] = matrix[val_idx]

        work_matrix = np.log1p(np.clip(matrix, 0, None)) if log1p else matrix

        level, loadings, basis = decompose(work_matrix, k)
        block = np.concatenate([level[:, None], loadings], axis=1)  # (n_points, k+1)
        block_slices[var] = (sum(b.shape[1] for b in targets), block.shape[1])
        targets.append(block)

        mean = block.mean(axis=0)
        std = block.std(axis=0)
        std[std < 1e-8] = 1.0
        if args.loss_weighting == "variance":
            # one scale for the whole block: with orthonormal basis rows, the squared
            # series error per month is dlevel^2 + sum_j dloading_j^2 / n_time, so
            # scaling the loadings by sqrt(n_time) more than the level and summing the
            # block's squared errors gives exactly the reconstruction MSE / total variance
            total_sd = np.sqrt(std[0] ** 2 + (std[1:] ** 2).sum() / n_time)
            std = np.full_like(std, total_sd)
            std[1:] *= np.sqrt(n_time)
        out_mean.append(mean)
        out_std.append(std)

        recon = block[:, 0:1] + loadings @ basis
        var_expl = 1 - ((work_matrix - recon) ** 2).sum() / \
            ((work_matrix - work_matrix.mean(axis=1, keepdims=True)) ** 2).sum()
        basis_np[var] = basis
        payload_vars[var] = {
            "unit": ds[var].attrs.get("units", ""),
            "log1p": log1p,
            "k_modes": k,
        }
        space = "log-space" if log1p else "native units"
        print(f"  level range [{level.min():.3g}, {level.max():.3g}] ({space}), "
              f"variance explained by {k} SVD modes: {var_expl:.3f}")

    Y = np.concatenate(targets, axis=1)
    out_mean = np.concatenate(out_mean)
    out_std = np.concatenate(out_std)
    Y_scaled = ((Y - out_mean) / out_std).astype(np.float32)

    torch.manual_seed(0)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    n_threads = args.torch_threads
    if n_threads:
        torch.set_num_threads(n_threads)
    print(f"training MLP on {device} (threads={torch.get_num_threads()}): "
          f"X {features[train_idx].shape} -> Y {Y_scaled[train_idx].shape}")

    fit_idx = train_idx[fit_pos]
    X_fit = torch.from_numpy(features[fit_idx]).to(device)
    Y_fit = torch.from_numpy(Y_scaled[fit_idx]).to(device)
    X_val = torch.from_numpy(features[val_idx]).to(device)
    Y_val = torch.from_numpy(Y_scaled[val_idx]).to(device)

    def score_against(pred_raw, truth_dict):
        """Per-variable dict of {rmse, r2, min/max per-point-series RMSE} in native units."""
        out = {}
        for var in variables:
            start, width = block_slices[var]
            block = pred_raw[:, start:start + width]
            series_pred = block[:, 0:1] + block[:, 1:] @ basis_np[var]
            if payload_vars[var]["log1p"]:
                series_pred = np.expm1(series_pred)
            truth = truth_dict[var]
            per_point_rmse = np.sqrt(((series_pred - truth) ** 2).mean(axis=1))
            ss_res = ((series_pred - truth) ** 2).sum()
            ss_tot = ((truth - truth.mean()) ** 2).sum()
            out[var] = {
                "rmse": float(per_point_rmse.mean()),
                "r2": float(1 - ss_res / ss_tot),
                "min_series_rmse": float(per_point_rmse.min()),
                "max_series_rmse": float(per_point_rmse.max()),
            }
        return out

    def print_scores(scores, label):
        print(f"  [{label}] per-variable RMSE (mean, and min..max across individual series):")
        for var, s in scores.items():
            print(f"      {var:16s} rmse={s['rmse']:.4g}  R2={s['r2']:.3f}  "
                  f"series_rmse=[{s['min_series_rmse']:.3g} .. {s['max_series_rmse']:.3g}]")

    precip_width = k_for(variables[-1]) + 1
    grid_shape = (int(round(180 / args.grid_deg)) + 1, int(round(360 / args.grid_deg)), args.grid_channels)
    pgrid_shape = None if not args.precip_grid_deg else \
        (int(round(180 / args.precip_grid_deg)) + 1, int(round(360 / args.precip_grid_deg)),
         args.precip_grid_channels)
    model = Emulator(n_fourier, Y_scaled.shape[1], precip_width, grid_shape=grid_shape,
                     hidden=(192, 192, 192), precip_grid_shape=pgrid_shape).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    precip_head_params = sum(p.numel() for p in model.precip_head.parameters())
    print(f"model: {n_params:,} params = {n_params * 4 / 2**20:.1f} MB float32 / "
          f"{n_params * 2 / 2**20:.1f} MB float16 ({model.grid.numel():,} in the feature grid, "
          f"{0 if model.pgrid is None else model.pgrid.numel():,} in the precip grid, "
          f"{precip_head_params:,} in {variables[-1]}'s dedicated head)")
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)

    def loss_fn(pred, target):
        """Per-variable loss: MSE for the smooth met variables, Huber for the
        heavy-tailed ones in HUBER_VARS, each block weighted by
        LOSS_WEIGHT_OVERRIDE (default 1.0) before averaging - see the comment
        by those constants for why."""
        total, total_weight = 0.0, 0.0
        for var in variables:
            start, width = block_slices[var]
            p, t = pred[:, start:start + width], target[:, start:start + width]
            if args.loss_weighting == "variance":
                elem = F.smooth_l1_loss(p, t, reduction="none", beta=0.1) if var in HUBER_VARS \
                    else (p - t) ** 2
                block_loss = elem.mean(0).sum()
            else:
                block_loss = F.smooth_l1_loss(p, t) if var in HUBER_VARS else F.mse_loss(p, t)
            w = LOSS_WEIGHT_OVERRIDE.get(var, 1.0)
            total = total + w * block_loss
            total_weight += w
        return total / total_weight

    def predict_tensor(Xt):
        was_training = model.training
        model.eval()
        with torch.no_grad():
            out = model(Xt).cpu().numpy()
        if was_training:
            model.train()
        return out

    batch_size = 512
    n_fit = X_fit.shape[0]
    best_val, best_state, bad_epochs = float("inf"), None, 0
    patience, max_epochs, eval_every = 20, 400, 20

    for epoch in range(max_epochs):
        model.train()
        order = torch.randperm(n_fit, device=device)
        epoch_loss = 0.0
        for start in range(0, n_fit, batch_size):
            b = order[start:start + batch_size]
            opt.zero_grad()
            loss = loss_fn(model(X_fit[b]), Y_fit[b])
            loss.backward()
            opt.step()
            epoch_loss += loss.item() * len(b)
        epoch_loss /= n_fit

        model.eval()
        with torch.no_grad():
            val_loss = loss_fn(model(X_val), Y_val).item()

        improved = val_loss < best_val - 1e-6
        if improved:
            best_val = val_loss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            bad_epochs = 0
        else:
            bad_epochs += 1

        if epoch % 10 == 0 or improved:
            print(f"  epoch {epoch:4d}  train_loss={epoch_loss:.5f}  val_loss={val_loss:.5f}"
                  f"{'  *' if improved else ''}")

        if epoch % eval_every == 0 or bad_epochs >= patience:
            val_pred_raw = predict_tensor(X_val) * out_std + out_mean
            print_scores(score_against(val_pred_raw, val_truth), f"epoch {epoch} val")

        if bad_epochs >= patience:
            print(f"early stopping at epoch {epoch} (best val_loss={best_val:.5f})")
            break

    model.load_state_dict(best_state)
    model.eval()

    def predict(X):
        with torch.no_grad():
            return model(torch.from_numpy(X.astype(np.float32)).to(device)).cpu().numpy()

    pred_train = predict(features[train_idx])
    resid = pred_train - Y_scaled[train_idx]
    nrmse = np.sqrt((resid ** 2).mean(axis=0))
    print(f"per-output normalized RMSE (train, in std units): "
          f"min {nrmse.min():.3f} mean {nrmse.mean():.3f} max {nrmse.max():.3f}")

    print("held-out evaluation (full reconstructed monthly series vs. real data, never seen in training):")
    pred_test_scaled = predict(features[test_idx])
    pred_test = pred_test_scaled * out_std + out_mean
    lon_test = lon_flat[test_idx]
    lat_test = lat_flat[test_idx]
    eval_summary = score_against(pred_test, test_truth)
    print_scores(eval_summary, "held-out test")
    # same model with every parameter rounded to float16 (what a half-precision
    # weights.bin would give)
    fp32_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    with torch.no_grad():
        for prm in model.parameters():
            prm.copy_(prm.half().float())
    eval_fp16 = score_against(predict(features[test_idx]) * out_std + out_mean, test_truth)
    print_scores(eval_fp16, "held-out test, parameters rounded to float16")
    model.load_state_dict(fp32_state)

    plot_pos = np.random.default_rng(1).choice(len(test_idx), size=min(4, len(test_idx)), replace=False)
    plot_vars = [v for v in ("t_air", "t_air_min", "t_air_max", "precip_total") if v in variables]
    plot_samples = {}
    for var in plot_vars:
        start, width = block_slices[var]
        block = pred_test[:, start:start + width]
        series_pred = block[:, 0:1] + block[:, 1:] @ basis_np[var]
        if payload_vars[var]["log1p"]:
            series_pred = np.expm1(series_pred)
        truth = test_truth[var]
        plot_samples[var] = {
            "pred": series_pred[plot_pos], "truth": truth[plot_pos],
            "lon": lon_test[plot_pos], "lat": lat_test[plot_pos],
        }

    if plot_samples:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        n_rows = len(plot_samples)
        n_cols = len(plot_pos)
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 2.6 * n_rows), squeeze=False)
        for ri, var in enumerate(plot_samples):
            s = plot_samples[var]
            for ci in range(n_cols):
                ax = axes[ri][ci]
                ax.plot(s["truth"][ci], label="real", color="black", lw=1)
                ax.plot(s["pred"][ci], label="emulated", color="tab:orange", lw=1)
                ax.set_title(f"{var} @ lon={s['lon'][ci]:.1f}, lat={s['lat'][ci]:.1f}", fontsize=9)
                if ri == 0 and ci == 0:
                    ax.legend(fontsize=8)
        fig.tight_layout()
        analysis_dir = os.path.join(os.path.dirname(args.output) or ".", "analysis")
        os.makedirs(analysis_dir, exist_ok=True)
        plot_path = os.path.join(analysis_dir, "eval_plot.png")
        fig.savefig(plot_path, dpi=110)
        print(f"wrote {plot_path}")

    eval_path = os.path.join(os.path.dirname(args.output) or ".", "eval_summary.json")
    with open(eval_path, "w") as f:
        json.dump({"n_test_points": int(len(test_idx)), "per_variable": eval_summary,
                   "per_variable_fp16_params": eval_fp16, "config": vars(args),
                   "n_params": int(n_params)}, f, indent=2)
    print(f"wrote {eval_path}")

    # binary payload: a flat float32 blob in a fixed order (grid, trunk layers'
    # W/b, shared head's W/b, precip head layers' W/b, then each variable's
    # temporal basis) - weights.json below records the shapes so viewer.html can
    # slice the ArrayBuffer back apart without needing an explicit offset table.
    binary_chunks = []

    def add_array(arr):
        arr = np.ascontiguousarray(arr, dtype=np.float32)
        binary_chunks.append(arr.tobytes())
        return list(arr.shape)

    def linear_shapes(module):
        """(n_in, n_out) W (transposed to match viewer.html's h[i]*W[i][j]) + b, for each
        nn.Linear in a Sequential (Tanh/other non-Linear layers are skipped)."""
        out = []
        for m in (module if isinstance(module, nn.Sequential) else [module]):
            if not isinstance(m, nn.Linear):
                continue
            W = m.weight.detach().cpu().numpy().T
            b = m.bias.detach().cpu().numpy()
            out.append({"W_shape": add_array(W), "b_shape": add_array(b)})
        return out

    grid_shape = add_array(model.grid.detach().cpu().numpy())
    trunk_layer_shapes = linear_shapes(model.trunk)
    shared_head_shapes = linear_shapes(model.shared_head)[0]
    precip_head_layer_shapes = linear_shapes(model.precip_head)

    for var in variables:
        payload_vars[var]["basis_shape"] = add_array(basis_np[var])
    precip_grid_shape = None if model.pgrid is None else add_array(model.pgrid.detach().cpu().numpy())

    bin_path = os.path.splitext(args.output)[0] + ".bin"
    with open(bin_path, "wb") as f:
        for chunk in binary_chunks:
            f.write(chunk)

    payload = {
        "meta": {
            "source_label": source_label,
            "time_start": time_start,
            "n_time": int(n_time),
            "variables": variables,
            "n_lon_harm": N_LON_HARM,
            "n_lat_harm": N_LAT_HARM,
            "grid_shape": grid_shape,
            "precip_grid_shape": precip_grid_shape,
            "bin_file": os.path.basename(bin_path),
        },
        "output_scaler": {
            "mean": [round(float(v), 6) for v in out_mean],
            "std": [round(float(v), 6) for v in out_std],
        },
        "mlp": {
            "activation": "tanh",
            "trunk_layers": trunk_layer_shapes,
            "shared_head": shared_head_shapes,
            "precip_head_layers": precip_head_layer_shapes,
        },
        "variables": payload_vars,
    }

    with open(args.output, "w") as f:
        json.dump(payload, f)

    size_kb = os.path.getsize(args.output) / 1024
    bin_mb = os.path.getsize(bin_path) / (1024 * 1024)
    print(f"wrote {args.output} ({size_kb:.0f} KB) and {bin_path} ({bin_mb:.1f} MB) "
          f"in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
