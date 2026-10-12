"""Compare QUINCY cpp_port runs at one site that differ only in forcing:
the original sub-daily climate.dat vs. daily forcing regenerated from its
monthly aggregate (GWGEN / simple), plus emulator- and TerraClimate-driven
GWGEN runs. Reads <run>/our_daily_output.csv; for the forcing statistics
<run>/daily.dat (written by monthly_gwgen_ssm_run --write-daily) and the
sub-daily climate.dat.

Usage: compare_runs.py <site_dir> <subdaily_climate.dat> <reference_run> <run> [<run> ...]
"""
import sys

import numpy as np
import pandas as pd

site, subdaily, ref, runs = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
VARS = ["GPP", "Qle", "Qh", "Rnet", "Transpiration", "Evaporation", "SrfRunoff", "GwRunoff", "LAI", "FineRootC",
        "SnowHeight"]


def load(run):
    d = pd.read_csv(f"{site}/{run}/our_daily_output.csv")
    d["year"] = (d["Day"] - 1) // 365
    d["doy"] = (d["Day"] - 1) % 365
    return d


r0 = load(ref)
ann0 = r0.groupby("year")[VARS].mean()
print(f"Annual means over {len(ann0)} years; r = correlation of annual series with {ref}\n")
print(f"{'variable':14s}{ref:>22s}" + "".join(f"{r:>30s}" for r in runs))
tab = {r: load(r) for r in runs}
for v in VARS:
    line = f"{v:14s}{ann0[v].mean():22.4g}"
    for r in runs:
        a = tab[r].groupby("year")[v].mean()
        rel = (a.mean() - ann0[v].mean()) / abs(ann0[v].mean()) * 100 if ann0[v].mean() else np.nan
        cor = np.corrcoef(a, ann0[v])[0, 1] if a.std() > 0 and ann0[v].std() > 0 else np.nan
        line += f"{a.mean():12.4g} ({rel:+6.1f}%, r={cor:5.2f})"
    print(line)

print("\nMean seasonal cycle of GPP (monthly means of the daily values)")
edges = np.cumsum([0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
mon = lambda d: pd.cut(d["doy"], edges, right=False, labels=range(1, 13))
print("month " + " ".join(f"{m:6d}" for m in range(1, 13)))
for r, d in [(ref, r0)] + list(tab.items()):
    s = d.groupby(mon(d), observed=True)["GPP"].mean()
    print(f"{r[:22]:22s}" + " ".join(f"{x:6.2f}" for x in s))

# Daily weather statistics of the forcing itself.
cols = ["year", "doy", "hour", "sw", "lw", "t_air", "q_air", "press", "rain", "snow", "wind"]
sd = pd.read_csv(subdaily, sep=r"\s+", skiprows=2, names=cols, usecols=range(11))
day0 = sd.groupby(["year", "doy"]).agg(tmax=("t_air", "max"), sw=("sw", "mean"), rain=("rain", "mean"),
                                        snow=("snow", "mean"), wind=("wind", "mean")).reset_index()
day0["prec"] = day0["rain"] + day0["snow"]


def daily_stats(d):
    d = d.copy()
    d["month"] = np.searchsorted(edges[1:], d["doy"].values - 1, side="right") + 1
    g = d.groupby(["year", "month"])
    wet = d["prec"] >= 0.1
    spell = (wet & ~wet.shift(1, fill_value=False)).sum()
    return {"within-month SD Tmax [K]": g["tmax"].std().mean(),
            "within-month SD SW [W/m2]": g["sw"].std().mean(),
            "within-month SD wind [m/s]": g["wind"].std().mean(),
            "lag-1 autocorr Tmax anomaly": (d["tmax"] - g["tmax"].transform("mean")).autocorr(1),
            "wet-day fraction": wet.mean(),
            "mean wet spell [days]": wet.sum() / max(spell, 1),
            "99th pct daily precip [mm]": d["prec"].quantile(0.99)}


print("\nDaily forcing statistics (CRUNCEP site forcing vs. regenerated daily forcing)")
stats = {"subdaily (daily agg.)": daily_stats(day0)}
for r in runs:
    try:
        g = pd.read_csv(f"{site}/{r}/daily.dat", sep=r"\s+", skiprows=2,
                        names=["year", "doy", "hour", "sw", "lw", "tmin", "tmax", "q", "p", "rain", "snow", "wind"],
                        usecols=range(12))
    except FileNotFoundError:
        continue
    g["prec"] = g["rain"] + g["snow"]
    g = g[(g.year >= day0.year.min()) & (g.year <= day0.year.max())]
    stats[r] = daily_stats(g)
st = pd.DataFrame(stats)
print(st.to_string(float_format=lambda x: f"{x:.3f}"))
