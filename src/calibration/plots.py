"""Plots written after every round and at the end of a calibration.

Per round (<round_dir>/plots/):
  fit_<metric>.png   observations vs. the best member and the bands of the
                     elite (best 10% of a round's size) and 5x the elite, of all rounds so far
  parameters.png     parameter distribution of the round vs. the elite,
                     with the round's range and the next round's range
  correlations.png   rank correlations between the elite's parameters
  diurnal.png        mean 24-hour cycle of the sub-daily metrics: observations
                     vs. the best member and the elite, at the observation times
Overall (<output_root>/):
  progress.png       score of all members per round and the best score
  ranges.png         how each parameter range shrank over the rounds
  tradeoffs.png      RMSE relative to the score's reference for every pair of
                     objectives: how well they can be fit at the same time
"""
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib.colors import LinearSegmentedColormap

from .member_task import series_path

INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
GRAY = "#c3c2b7"
BLUE = "#2a78d6"        # best member / top 10%
BLUE_MID = "#86b6ef"    # top 10% band
BLUE_LIGHT = "#cde2fb"  # top 50% band
RED = "#e34948"         # negative pole of the diverging scale
NEUTRAL = "#f0efec"     # diverging midpoint
DIVERGING = LinearSegmentedColormap.from_list("red_blue", [RED, NEUTRAL, BLUE])
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "axes.edgecolor": INK_2, "axes.labelcolor": INK, "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
    "legend.frameon": False, "figure.dpi": 120,
})


def _load_series(output_root, rows):
    """Model series of the given members (rows of the results table) as one long DataFrame."""
    parts = []
    for _, r in rows.iterrows():
        path = series_path(os.path.join(output_root, r["round_dir"]), int(r["member"]))
        if os.path.isfile(path):
            df = pd.read_csv(path, parse_dates=["date"])
            df["uid"] = r["uid"]
            parts.append(df)
    return pd.concat(parts, ignore_index=True) if parts else None


def _break_gaps(df, factor=5.0):
    """Insert NaN rows where the time step is more than `factor` times the
    typical one, so lines and bands are not drawn across data gaps."""
    if len(df) < 3:
        return df
    step = df.index.to_series().diff()
    gaps = step > factor * step.median()
    if not gaps.any():
        return df
    breaks = pd.DataFrame(np.nan, index=df.index[gaps] - pd.Timedelta(seconds=1), columns=df.columns)
    return pd.concat([df, breaks]).sort_index()


def plot_fits(output_root, plot_dir, ranked, n_elite, metrics, round_label):
    """ranked: ok members of all rounds so far, best first. Bands: the n_elite
    best members ("best 10%" of a round) and the 5*n_elite best ("best 50%")."""
    top10 = ranked.head(n_elite)
    top50 = ranked.head(5 * n_elite)
    series = _load_series(output_root, top50)
    if series is None:
        return
    best_uid = ranked.iloc[0]["uid"]

    for metric in metrics:
        s = series[series["metric"] == metric.name]
        if s.empty:
            continue
        wide = s.pivot_table(index="date", columns="uid", values="model")
        obs = s.drop_duplicates("date").set_index("date")["obs"].sort_index()
        b10 = wide[[u for u in top10["uid"] if u in wide.columns]]

        fig, ax = plt.subplots(figsize=(13, 4))
        best_label = f"best member (RMSE {ranked.iloc[0][f'rmse_{metric.name}']:.3g})"
        if len(obs) < 50:
            # Few observation dates: ranges as bars per date, nothing drawn in between
            ax.vlines(wide.index, wide.min(axis=1), wide.max(axis=1), color=BLUE_LIGHT, lw=12,
                      label=f"best {wide.shape[1]} members")
            ax.vlines(b10.index, b10.min(axis=1), b10.max(axis=1), color=BLUE_MID, lw=12,
                      label=f"best {b10.shape[1]} members (elite)")
            ax.plot(obs.index, obs.values, "o", color=INK, ms=7, label="observations")
            if best_uid in wide.columns:
                ax.plot(wide.index, wide[best_uid], "D", color=BLUE, ms=7, label=best_label)
        else:
            wide, b10 = _break_gaps(wide), _break_gaps(b10)
            ax.fill_between(wide.index, wide.min(axis=1, skipna=False), wide.max(axis=1, skipna=False),
                            color=BLUE_LIGHT, lw=0, label=f"best {wide.shape[1]} members")
            ax.fill_between(b10.index, b10.min(axis=1, skipna=False), b10.max(axis=1, skipna=False),
                            color=BLUE_MID, lw=0, label=f"best {b10.shape[1]} members (elite)")
            ax.plot(obs.index, obs.values, ".", color=INK, ms=2, label="observations")
            if best_uid in wide.columns:
                ax.plot(wide.index, wide[best_uid], "-", color=BLUE, lw=1.5, label=best_label)
        kind = "target range midpoint" if metric.is_range_constraint else metric.obs_column
        ax.set_title(f"{metric.name}: {metric.category}/{metric.variable} vs {kind} - after {round_label}",
                     loc="left", color=INK)
        ax.set_ylabel(metric.variable)
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))
        fig.tight_layout()
        fig.savefig(os.path.join(plot_dir, f"fit_{metric.name}.png"))
        plt.close(fig)


def plot_parameters(plot_dir, round_members, elite, specs, lo, hi, next_lo, next_hi, round_label):
    """round_members/elite: natural-unit DataFrames with one column per calibrated parameter.
    lo/hi, next_lo/next_hi: range holding ~95% of this/next round's samples (internal units)."""
    n = len(specs)
    ncol = 4
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.6 * ncol, 2.8 * nrow), squeeze=False)
    for k, spec in enumerate(specs):
        ax = axes[k // ncol][k % ncol]
        if spec.scale == "log":
            bins = np.logspace(spec.internal_min, spec.internal_max, 25)
            ax.set_xscale("log")
        else:
            bins = np.linspace(spec.min, spec.max, 25)
        ax.hist(round_members[spec.name], bins=bins, color=GRAY, label=f"{round_label} (all)")
        ax.hist(elite[spec.name], bins=bins, color=BLUE, label="elite (best so far)")
        for x in (spec.from_internal(lo[k]), spec.from_internal(hi[k])):
            ax.axvline(x, color=INK_2, ls="--", lw=1)
        if next_lo is not None:
            for x in (spec.from_internal(next_lo[k]), spec.from_internal(next_hi[k])):
                ax.axvline(x, color=BLUE, lw=1.5)
        ax.set_title(spec.name + (" (log10 axis)" if spec.scale == "log" else ""), loc="left", color=INK)
        ax.set_xlim(spec.min, spec.max)
        if spec.scale == "log":
            # Real values at 1-2-5 steps, evenly spaced on the log axis
            ax.xaxis.set_major_locator(matplotlib.ticker.LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
            ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:g}"))
            ax.xaxis.set_minor_locator(matplotlib.ticker.LogLocator(base=10, subs=np.arange(1, 10)))
            ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        else:
            ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4))
    for k in range(n, nrow * ncol):
        axes[k // ncol][k % ncol].axis("off")
    handles, labels = axes[0][0].get_legend_handles_labels()
    handles += [plt.Line2D([], [], color=INK_2, ls="--"), plt.Line2D([], [], color=BLUE, lw=1.5)]
    labels += ["sampled range of this round", "sampled range of next round"]
    fig.legend(handles, labels, loc="upper center", ncol=4)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(os.path.join(plot_dir, "parameters.png"))
    plt.close(fig)


def plot_progress(output_root, results, history, metrics):
    rounds = sorted(results["round"].unique())
    fig, axes = plt.subplots(1, 1 + len(metrics), figsize=(4 * (1 + len(metrics)), 3.6), squeeze=False)
    ax = axes[0][0]
    ok = results[results["ok"]]
    ax.boxplot([ok.loc[ok["round"] == r, "score"] for r in rounds], positions=rounds, widths=0.5,
               showfliers=False, patch_artist=True,
               boxprops=dict(facecolor=GRAY, color=INK_2), medianprops=dict(color=INK),
               whiskerprops=dict(color=INK_2), capprops=dict(color=INK_2))
    ax.plot(history["round"], history["best_score"], "-o", color=BLUE, lw=2, ms=8, label="best so far")
    ax.set_yscale("log")
    ax.set_xlabel("round")
    ax.set_title("score (lower is better)", loc="left", color=INK)
    ax.legend()
    for k, m in enumerate(metrics):
        ax = axes[0][k + 1]
        ax.plot(history["round"], history[f"best_rmse_{m.name}"], "-o", color=BLUE, lw=2, ms=8)
        ax.set_xlabel("round")
        ax.set_xticks(rounds)
        ax.set_title(f"{m.name}: RMSE of best member", loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(output_root, "progress.png"))
    plt.close(fig)


def plot_ranges(output_root, ranges, specs):
    """ranges: list (one per round) of (lo, hi) in internal units."""
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(specs) + 1.5))
    n_rounds = len(ranges)
    # Light (first round) to dark (last round)
    colors = [BLUE_RAMP[int(round(i))] for i in np.linspace(1, len(BLUE_RAMP) - 1, n_rounds)]
    height = 0.8 / n_rounds
    for r, (lo, hi) in enumerate(ranges):
        for k, spec in enumerate(specs):
            span = spec.internal_max - spec.internal_min
            a, b = (lo[k] - spec.internal_min) / span, (hi[k] - spec.internal_min) / span
            ax.barh(k + (r - (n_rounds - 1) / 2) * height, b - a, left=a, height=height * 0.9,
                    color=colors[r], label=f"round {r}" if k == 0 else None)
    ax.set_yticks(range(len(specs)))
    ax.set_yticklabels([s.name + (" (log)" if s.scale == "log" else "") for s in specs])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("position within the original range (0 = min, 1 = max)")
    ax.set_title("sampled parameter range per round (~95% of members)", loc="left", color=INK, pad=28)
    fig.legend(loc="upper center", ncol=n_rounds)
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.5 / (0.5 * len(specs) + 1.5)))
    fig.savefig(os.path.join(output_root, "ranges.png"))
    plt.close(fig)


def plot_correlations(plot_dir, correlations, round_label):
    """correlations: square DataFrame of Spearman correlations between the elite's parameters."""
    names = list(correlations.columns)
    n = len(names)
    fig, ax = plt.subplots(figsize=(0.6 * n + 3, 0.6 * n + 1.5))
    im = ax.imshow(correlations.values, cmap=DIVERGING, vmin=-1, vmax=1)
    ax.grid(False)
    ax.set_xticks(range(n))
    ax.set_xticklabels(names, rotation=45, ha="right")
    ax.set_yticks(range(n))
    ax.set_yticklabels(names)
    for i in range(n):
        for j in range(n):
            if i != j:
                ax.text(j, i, f"{correlations.values[i, j]:.2f}", ha="center", va="center",
                        fontsize=8, color=INK)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Spearman correlation")
    ax.set_title(f"parameter correlations within the elite - after {round_label}", loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(plot_dir, "correlations.png"))
    plt.close(fig)


def _pareto_front(x, y):
    """Indices of the points no other point beats in both x and y, sorted by x."""
    order = np.argsort(x)
    front, best_y = [], np.inf
    for i in order:
        if y[i] < best_y:
            front.append(i)
            best_y = y[i]
    return np.array(front, dtype=int)


def plot_tradeoffs(output_root, ranked, n_elite, metrics, score_mode):
    """One panel per pair of objectives: each member's RMSE relative to the
    score's reference (best RMSE reached, or sigma), with the front of the
    best combinations. Members failing a constraint are drawn lighter."""
    objectives = [m for m in metrics if m.role == "objective"]
    if len(objectives) < 2:
        return
    ref_label = {"relative": "best RMSE reached", "sigma": "sigma", "reference": "reference"}[score_mode]
    pairs = [(a, b) for i, a in enumerate(objectives) for b in objectives[i + 1:]]
    fig, axes = plt.subplots(1, len(pairs), figsize=(max(5.5, 4.4 * len(pairs)), 4.8), squeeze=False)
    is_elite = np.zeros(len(ranked), dtype=bool)
    is_elite[:n_elite] = True
    feasible = ranked["feasible"].to_numpy(dtype=bool)
    for ax, (a, b) in zip(axes[0], pairs):
        x = ranked[f"ratio_{a.name}"].to_numpy(dtype=float)
        y = ranked[f"ratio_{b.name}"].to_numpy(dtype=float)
        rest = ~is_elite
        ax.scatter(x[rest & ~feasible], y[rest & ~feasible], s=10, color=GRID, lw=0,
                   label="fails a constraint")
        ax.scatter(x[rest & feasible], y[rest & feasible], s=10, color=GRAY, lw=0, label="passes the constraints")
        ax.scatter(x[is_elite], y[is_elite], s=16, color=BLUE_MID, lw=0, label="elite")
        front = _pareto_front(np.where(feasible, x, np.inf), np.where(feasible, y, np.inf))
        front = front[np.isfinite(x[front])]
        ax.plot(x[front], y[front], "-", color=INK_2, lw=1.5, label="best combinations (passing)")
        ax.plot(x[0], y[0], "D", color=BLUE, ms=8, mec="white", mew=1.5, label="best member")
        if score_mode != "relative":
            ax.axvline(1, color=INK_2, ls="--", lw=1)
            ax.axhline(1, color=INK_2, ls="--", lw=1)
        # Members far off would squash the interesting region
        lo = 0 if score_mode != "relative" else 0.9
        ax.set_xlim(lo, max(2.0, np.nanquantile(x, 0.5)))
        ax.set_ylim(lo, max(2.0, np.nanquantile(y, 0.5)))
        ax.set_xlabel(f"{a.name} RMSE / {ref_label}")
        ax.set_ylabel(f"{b.name} RMSE / {ref_label}")
    handles, labels = axes[0][0].get_legend_handles_labels()
    # One panel (two objectives) is too narrow for the legend in one row
    ncol = 5 if len(pairs) > 1 else 2
    fig.legend(handles, labels, loc="upper center", ncol=ncol)
    fig.tight_layout(rect=(0, 0, 1, 0.9 if len(pairs) > 1 else 0.8))
    fig.savefig(os.path.join(output_root, "tradeoffs.png"))
    plt.close(fig)


def _diurnal(series_wide):
    """Mean over days per time of day (hours, e.g. 13.5 for 13:30) of a DataFrame indexed by date."""
    hours = series_wide.index.hour + series_wide.index.minute / 60.0
    return series_wide.groupby(hours).mean()


def plot_diurnal(output_root, plot_dir, ranked, n_elite, metrics, round_label):
    """Mean 24-hour cycle of every sub-daily metric (observations at least
    hourly on most days), each averaged over the observation times only, so
    model and observations cover the same days and hours. Bands: diurnal
    means of the elite and of 5x the elite."""
    series = _load_series(output_root, ranked.head(5 * n_elite))
    if series is None:
        return
    top10 = list(ranked.head(n_elite)["uid"])
    best_uid = ranked.iloc[0]["uid"]
    panels = []
    for metric in metrics:
        s = series[series["metric"] == metric.name]
        if s.empty:
            continue
        obs = s.drop_duplicates("date").set_index("date")["obs"].sort_index()
        if len(obs) < 48 or obs.index.to_series().diff().median() > pd.Timedelta(hours=1):
            continue
        panels.append((metric, s, obs))
    if not panels:
        return

    fig, axes = plt.subplots(1, len(panels), figsize=(5.5 * len(panels), 4.2), squeeze=False)
    for ax, (metric, s, obs) in zip(axes[0], panels):
        wide = _diurnal(s.pivot_table(index="date", columns="uid", values="model"))
        obs_d = _diurnal(obs.to_frame())["obs"]
        b10 = wide[[u for u in top10 if u in wide.columns]]
        ax.fill_between(wide.index, wide.min(axis=1), wide.max(axis=1), color=BLUE_LIGHT, lw=0,
                        label=f"best {wide.shape[1]} members")
        ax.fill_between(b10.index, b10.min(axis=1), b10.max(axis=1), color=BLUE_MID, lw=0,
                        label=f"best {b10.shape[1]} members (elite)")
        if best_uid in wide.columns:
            ax.plot(wide.index, wide[best_uid], "-", color=BLUE, lw=2, label="best member")
        ax.plot(obs_d.index, obs_d.values, "o", color=INK, ms=4, label="observations")
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 3))
        ax.set_xlabel("hour of day")
        ax.set_ylabel(metric.variable)
        ax.set_title(f"{metric.name}: mean 24-hour cycle", loc="left", color=INK)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4)
    fig.suptitle(f"after {round_label}", x=0.99, ha="right", fontsize=9, color=INK_2)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(os.path.join(plot_dir, "diurnal.png"))
    plt.close(fig)
