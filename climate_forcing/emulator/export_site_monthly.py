"""Export one location's monthly forcing as the table QUINCY's C++ port reads
(cpp_port demo/monthly_gwgen_ssm_run.cpp -> generate_daily_forcing() -> GWGEN
-> run_ssm()).

Climate comes from an emulator (--emulator DIR with weights.json/weights.bin)
or, for comparison, from a global forcing file alone (--forcing only).
Variables the emulator does not predict (TerraClimate: press_srf; all:
co2_mixing_ratio) are taken from the nearest cell of --forcing when given,
otherwise written as nan (the C++ side then falls back: pressure from
--elevation, CO2 from --co2).

Columns: year month tmin tmax swvis_srf_down lw_srf_down q_air press_srf
precip_total wind_air nhx_srf_down noy_srf_down co2_mixing_ratio
(K, W m-2, g kg-1, hPa, mm day-1 as monthly mean rate, m s-1, mg N m-2 day-1, ppm).

Examples:
  python export_site_monthly.py --emulator terraclimate --lon 10.45 --lat 51.08 \\
      --forcing .../terraclimate_global_forcing_0.5deg_1958-2025.nc --out hainich_emulator.csv
  python export_site_monthly.py --lon 10.45 --lat 51.08 \\
      --forcing .../terraclimate_global_forcing_0.5deg_1958-2025.nc --out hainich_terraclimate.csv
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emulator_predict import ForcingEmulator  # noqa: E402

COLUMNS = ["tmin", "tmax", "swvis_srf_down", "lw_srf_down", "q_air", "press_srf", "precip_total",
           "wind_air", "nhx_srf_down", "noy_srf_down", "co2_mixing_ratio"]
# table column <- emulator / forcing-store variable
SOURCE_NAME = {"tmin": "t_air_min", "tmax": "t_air_max"}


def from_emulator(path: str, lon: float, lat: float) -> tuple[list[str], dict[str, np.ndarray]]:
    weights = path if path.endswith(".json") else os.path.join(path, "weights.json")
    em = ForcingEmulator(weights)
    if "t_air_min" not in em.variables:
        raise SystemExit(f"{weights}: emulator has no t_air_min/t_air_max (variables: {em.variables})")
    s = em.predict(lon=lon, lat=lat)
    out = {c: s[SOURCE_NAME.get(c, c)] for c in COLUMNS if SOURCE_NAME.get(c, c) in s}
    return em.times, out


def from_forcing(path: str, lon: float, lat: float) -> tuple[list[str], dict[str, np.ndarray], tuple[float, float]]:
    import xarray as xr

    ds = xr.open_dataset(path)
    # Nearest cell with data (the emulator answers anywhere; the store is land-only).
    land = np.isfinite(ds["t_air_min"].isel(time=0)).values
    la, lo = np.meshgrid(ds.lat.values, ds.lon.values, indexing="ij")
    d2 = (la - lat) ** 2 + ((lo - lon + 180.0) % 360.0 - 180.0) ** 2 * np.cos(np.deg2rad(lat)) ** 2
    iy, ix = np.unravel_index(np.argmin(np.where(land, d2, np.inf)), d2.shape)
    cell = ds.isel(lat=iy, lon=ix)
    n_time = cell.sizes["time"]
    out = {}
    for c in COLUMNS:
        name = SOURCE_NAME.get(c, c)
        if c == "precip_total":
            if "rain" not in cell:
                continue
            v = cell["rain"].values + (cell["snow"].values if "snow" in cell else 0.0)
        elif name in cell:
            v = cell[name].values
        else:
            continue
        out[c] = np.broadcast_to(v, (n_time,)).astype(np.float64)
    times = [str(t)[:7] for t in cell.time.values.astype("datetime64[M]")]
    return times, out, (float(ds.lat.values[iy]), float(ds.lon.values[ix]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--emulator", help="emulator directory (or its weights.json); "
                    "a bare name like 'terraclimate' is looked up next to this script")
    ap.add_argument("--forcing", help="global forcing .nc: fills what the emulator lacks, "
                    "or supplies everything without --emulator")
    ap.add_argument("--start-year", type=int)
    ap.add_argument("--end-year", type=int)
    a = ap.parse_args()
    if not a.emulator and not a.forcing:
        ap.error("need --emulator and/or --forcing")

    data: dict[str, np.ndarray] = {}
    times = None
    if a.forcing:
        f_times, f_data, (clat, clon) = from_forcing(a.forcing, a.lon, a.lat)
        print(f"forcing: nearest land cell {clat:.2f}N {clon:.2f}E, {len(f_times)} months", file=sys.stderr)
        times, data = f_times, f_data
    if a.emulator:
        path = a.emulator
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        e_times, e_data = from_emulator(path, a.lon, a.lat)
        print(f"emulator {path}: {len(e_times)} months, variables {sorted(e_data)}", file=sys.stderr)
        if times is not None and times != e_times:
            # Align the forcing fill-ins to the emulator's time axis.
            idx = {t: i for i, t in enumerate(times)}
            missing = [t for t in e_times if t not in idx]
            if missing:
                raise SystemExit(f"--forcing does not cover emulator months {missing[0]}..{missing[-1]}")
            sel = np.array([idx[t] for t in e_times])
            data = {k: v[sel] for k, v in data.items()}
        times = e_times
        data.update(e_data)  # emulator wins where both have a variable

    years = np.array([int(t[:4]) for t in times])
    months = np.array([int(t[5:7]) for t in times])
    keep = np.ones(len(times), bool)
    if a.start_year:
        keep &= years >= a.start_year
    if a.end_year:
        keep &= years <= a.end_year
    # Whole calendar years only.
    first = np.argmax(keep & (months == 1))
    last = len(times) - 1 - np.argmax((keep & (months == 12))[::-1])
    keep[:first] = False
    keep[last + 1:] = False
    if keep.sum() == 0 or keep.sum() % 12:
        raise SystemExit("no whole calendar years in the selected range")

    with open(a.out, "w") as f:
        f.write("year month " + " ".join(COLUMNS) + "\n")
        for i in np.nonzero(keep)[0]:
            vals = [data[c][i] if c in data else np.nan for c in COLUMNS]
            f.write(f"{years[i]} {months[i]} " + " ".join(f"{v:.6g}" for v in vals) + "\n")
    missing = [c for c in COLUMNS if c not in data]
    print(f"wrote {a.out}: {keep.sum()} months {years[keep][0]}-{years[keep][-1]}"
          + (f"; missing (nan): {', '.join(missing)}" if missing else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
