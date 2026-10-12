"""Standalone inference for the forcing emulators -- numpy only, no torch.

Copy this file plus one dataset's weights.json and weights.bin (e.g.
emulator/models/gldas/) into any project:

    from emulator_predict import ForcingEmulator
    em = ForcingEmulator("gldas/weights.json")
    em.variables                      # ['t_air_min', 't_air_max', ..., 'precip_total']
    em.times                          # monthly time axis: list of "YYYY-MM"
    s = em.predict(lon=11.3, lat=47.1)               # {var: (n_time,) monthly series}
    s = em.predict(lon=[11.3, -60.0], lat=[47.1, -3.1], variables=["precip_total"])  # {var: (2, n_time)}

Units are the forcing store's (weights.json variables[var]["unit"]): K,
g kg-1, hPa, m s-1, W m-2, mm day-1, mg N m-2 day-1. Longitude -180..180 or
0..360, latitude -90..90; any point can be queried, but the emulators were
trained on land cells only, so ocean values are meaningless.

The forward pass mirrors train_emulator.Emulator / viewer.html exactly:
  features = [Fourier(lon, lat), bilinear sample of the feature grid]
  trunk    = tanh(...) layers
  outputs  = [shared head | precip head (+ optional precip grid)], then
             y * std + mean -> per variable [level, loadings]
  series   = level + loadings @ basis   (expm1 for log1p variables)
"""
from __future__ import annotations

import json
import os

import numpy as np


def _fourier(lon_deg, lat_deg, n_lon, n_lat):
    lon, lat = np.deg2rad(lon_deg), np.deg2rad(lat_deg)
    lat_norm = lat_deg / 90.0
    f = [lat_norm]
    for k in range(1, n_lon + 1):
        f += [np.sin(k * lon), np.cos(k * lon)]
    for k in range(1, n_lat + 1):
        f += [np.sin(k * lat), np.cos(k * lat)]
    f += [lat_norm * np.sin(lon), lat_norm * np.cos(lon)]
    return np.stack(f, axis=-1)


def _sample_grid(grid, lon_deg, lat_deg):
    H, W, _ = grid.shape
    x = np.mod(lon_deg, 360.0) / 360.0 * W
    y = (90.0 - lat_deg) / 180.0 * (H - 1)
    x0 = np.floor(x).astype(np.int64) % W
    x1 = (x0 + 1) % W
    y0 = np.clip(np.floor(y).astype(np.int64), 0, H - 2)
    y1 = y0 + 1
    fx = (x - np.floor(x))[:, None]
    fy = (y - y0)[:, None]
    top = grid[y0, x0] * (1 - fx) + grid[y0, x1] * fx
    bot = grid[y1, x0] * (1 - fx) + grid[y1, x1] * fx
    return top * (1 - fy) + bot * fy


class ForcingEmulator:
    def __init__(self, weights_json: str):
        with open(weights_json) as f:
            self.meta_all = json.load(f)
        meta = self.meta_all["meta"]
        blob = np.fromfile(os.path.join(os.path.dirname(weights_json) or ".", meta["bin_file"]),
                           dtype=np.float32)
        pos = 0

        def take(shape):
            nonlocal pos
            n = int(np.prod(shape))
            arr = blob[pos:pos + n].reshape(shape)
            pos += n
            return arr

        mlp = self.meta_all["mlp"]
        self.grid = take(meta["grid_shape"])
        self.trunk = [(take(l["W_shape"]), take(l["b_shape"])) for l in mlp["trunk_layers"]]
        self.shared_head = (take(mlp["shared_head"]["W_shape"]), take(mlp["shared_head"]["b_shape"]))
        self.precip_head = [(take(l["W_shape"]), take(l["b_shape"])) for l in mlp["precip_head_layers"]]
        self.variables = meta["variables"]
        self.var_info = self.meta_all["variables"]
        self.basis = {v: take(self.var_info[v]["basis_shape"]) for v in self.variables}
        pg = meta.get("precip_grid_shape")
        self.precip_grid = take(pg) if pg else None
        assert pos == blob.size, f"weights.bin has {blob.size} floats, layout uses {pos}"
        self.mean = np.asarray(self.meta_all["output_scaler"]["mean"], dtype=np.float64)
        self.std = np.asarray(self.meta_all["output_scaler"]["std"], dtype=np.float64)
        self.n_lon, self.n_lat = meta["n_lon_harm"], meta["n_lat_harm"]
        y0, m0 = map(int, meta["time_start"].split("-"))
        self.times = [f"{y0 + (m0 - 1 + i) // 12}-{(m0 - 1 + i) % 12 + 1:02d}" for i in range(meta["n_time"])]
        self.units = {v: self.var_info[v]["unit"] for v in self.variables}

    def _raw(self, lon, lat):
        x = np.concatenate([_fourier(lon, lat, self.n_lon, self.n_lat), _sample_grid(self.grid, lon, lat)], axis=1)
        h = x
        for W, b in self.trunk:
            h = np.tanh(h @ W + b)
        shared = h @ self.shared_head[0] + self.shared_head[1]
        p = h if self.precip_grid is None else np.concatenate([h, _sample_grid(self.precip_grid, lon, lat)], axis=1)
        for i, (W, b) in enumerate(self.precip_head):
            p = p @ W + b
            if i < len(self.precip_head) - 1:
                p = np.tanh(p)
        return np.concatenate([shared, p], axis=1) * self.std + self.mean

    def predict(self, lon, lat, variables=None):
        """Monthly series at (lon, lat): {var: (n_time,)} for scalars, {var: (n_points, n_time)} for arrays."""
        scalar = np.ndim(lon) == 0
        lon = np.atleast_1d(np.asarray(lon, dtype=np.float64))
        lat = np.atleast_1d(np.asarray(lat, dtype=np.float64))
        raw = self._raw(lon, lat)
        out, start = {}, 0
        for v in self.variables:
            width = self.var_info[v]["k_modes"] + 1
            if variables is None or v in variables:
                block = raw[:, start:start + width]
                s = block[:, :1] + block[:, 1:] @ self.basis[v]
                if self.var_info[v]["log1p"]:
                    s = np.expm1(s)
                out[v] = s[0] if scalar else s
            start += width
        return out
