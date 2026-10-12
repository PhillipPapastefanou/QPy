"""Aggregate a sub-daily QUINCY climate.dat (365-day years) to the monthly
table cpp_port's monthly_gwgen_ssm_run reads, so a run on the original file
and a run on GWGEN's reconstruction of it can be compared.

tmin/tmax: monthly mean of the daily min/max of t_air; wet_days: days with
rain + snow >= 0.1 mm; precip_total: mean daily rate; everything else: mean.

Usage: climate_dat_to_monthly.py <climate.dat> <out.csv> [start_year end_year]
"""
import sys

import numpy as np
import pandas as pd

src, out = sys.argv[1], sys.argv[2]
cols = ["year", "doy", "hour", "sw", "lw", "t_air", "q_air", "press", "rain", "snow", "wind",
        "co2", "dc13", "dc14", "nhx", "noy", "p"]
df = pd.read_csv(src, sep=r"\s+", skiprows=2, names=cols)
df["year"] = df["year"].round().astype(int)
df["doy"] = df["doy"].round().astype(int)
if len(sys.argv) > 3:
    df = df[(df.year >= int(sys.argv[3])) & (df.year <= int(sys.argv[4]))]

month_end = np.cumsum([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
day = df.groupby(["year", "doy"]).agg(
    tmin=("t_air", "min"), tmax=("t_air", "max"), sw=("sw", "mean"), lw=("lw", "mean"),
    q_air=("q_air", "mean"), press=("press", "mean"), rain=("rain", "mean"), snow=("snow", "mean"),
    wind=("wind", "mean"), co2=("co2", "mean"), nhx=("nhx", "mean"), noy=("noy", "mean")).reset_index()
if (day.groupby("year").size() != 365).any():
    raise SystemExit("expected 365 days in every year")
day["month"] = np.searchsorted(month_end, day["doy"].values) + 1
day["precip"] = day["rain"] + day["snow"]  # rain/snow columns are daily-rate units [mm/day]
day["wet"] = day["precip"] >= 0.1

m = day.groupby(["year", "month"]).agg(
    tmin=("tmin", "mean"), tmax=("tmax", "mean"), swvis_srf_down=("sw", "mean"),
    lw_srf_down=("lw", "mean"), q_air=("q_air", "mean"), press_srf=("press", "mean"),
    precip_total=("precip", "mean"), wind_air=("wind", "mean"), wet_days=("wet", "sum"),
    nhx_srf_down=("nhx", "mean"), noy_srf_down=("noy", "mean"), co2_mixing_ratio=("co2", "mean")).reset_index()
m.to_csv(out, sep=" ", index=False, float_format="%.6g")
print(f"wrote {out}: {len(m)} months {m.year.min()}-{m.year.max()}", file=sys.stderr)
