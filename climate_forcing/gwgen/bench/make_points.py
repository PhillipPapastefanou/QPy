"""Writes N random GLDAS 0.5deg land points (lat > -60), 2000-2025 monthly, as
the whitespace table bench.cpp / check_port.cpp read:
pt lat lon year month tmin tmax prec_rate sw wind.

Usage: make_points.py <gldas_global_forcing.nc> <n_points> <out.csv>
"""
import sys

import numpy as np
import xarray as xr

src, n, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
ds = xr.open_dataset(src)
vs = ['t_air_min', 't_air_max', 'rain', 'swvis_srf_down', 'wind_air']
m = np.isfinite(ds.t_air_min.isel(time=0).values) & (ds.lat.values[:, None] > -60)
iy, ix = np.nonzero(m)
k = np.random.default_rng(0).choice(len(iy), n, replace=False)
iy, ix = iy[k], ix[k]
arr = {v: ds[v].values[:, iy, ix] for v in vs}
nt = arr['rain'].shape[0]
with open(out, 'w') as f:
    f.write('pt lat lon year month tmin tmax prec_rate sw wind\n')
    for p in range(n):
        for t in range(nt):
            f.write(f'{p} {ds.lat.values[iy[p]]:.2f} {ds.lon.values[ix[p]]:.2f} {2000 + t // 12} {t % 12 + 1} '
                    + ' '.join(f'{arr[v][t, p]:.5g}' for v in vs) + '\n')
