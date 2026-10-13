"""Round-based calibration of QUINCY parameters against observations.

Round 0 samples the full parameter ranges (Latin hypercube). After every
round, the best members of all rounds so far ("elite", ensemble.elite_fraction
of a round's size) define the next round's sampling distribution, a
multivariate normal fitted to them (see sampling.py), so the sampled
parameter space shrinks where the observations constrain it. A small part of
every round keeps sampling the full ranges as a check. Members compute their
own RMSE inside their SLURM task (see member_task.py), so a round ends as
soon as the last QUINCY run is done.

Metrics have a role (MetricSpec.role): objectives are fit as well as
possible, constraints are a ballpark check that members must pass to be
ranked ahead (see metrics.score_members). All members are rescored together
after every round, because the "relative" score compares each objective's
RMSE with the best one reached so far.

With config.previous_results, the successful members of earlier calibrations
(inside the current ranges, rescored with the current metrics) join the
elite from the start, and round 0 already samples around them.

Output in config.output_root:
  round_XX/            setups, members.csv, results.csv, distribution.npz, plots/,
                       kept_outputs.csv (with keep_best_outputs_fraction)
  results.csv          every member of every round (parameters, statistics, scores)
  history.csv          best and elite scores and RMSE per round
  best_parameters.py   the best member's parameters (natural units)
  top_parameters.csv   the elite's parameters
  elite_correlations.csv  rank correlations between the elite's parameters
  accepted_parameters.csv members that pass every constraint and every
                       objective's sigma/observation spread, where given
  progress.png, ranges.png, tradeoffs.png, calibration_verdict.txt
"""
import glob
import math
import os

import numpy as np
import pandas as pd

from .config import CalibrationConfig
from .metrics import add_stats, score_members
from .plots import (plot_fits, plot_parameters, plot_progress, plot_ranges, plot_correlations,
                    plot_tradeoffs, plot_diurnal)
from .runner import QuincyModelRunner
from .sampling import (original_ranges, sample_lhs, uniform_distribution, fit_distribution,
                       sample_round, sampled_range, elite_at_bound)
from .verdict import assess, accepted


def run_calibration(config: CalibrationConfig):
    ens = config.ensemble
    os.makedirs(config.output_root, exist_ok=True)

    specs = [p for p in config.parameters if p.calibrate]
    fixed = [p for p in config.parameters if not p.calibrate]
    names = [p.name for p in specs]
    if fixed:
        print(f"[calibration] {len(fixed)} parameter(s) fixed at their nominal value: "
              f"{', '.join(p.name for p in fixed)}")
    print(f"[calibration] calibrating {len(specs)} parameter(s): {', '.join(names)}")
    for m in config.metrics:
        extra = f" (tolerance {m.tolerance:g})" if m.role == "constraint" else ""
        print(f"[calibration] metric {m.name}: {m.role}{extra}")

    runner = QuincyModelRunner(config)
    lo0, hi0 = original_ranges(specs)
    mean, cov = uniform_distribution(lo0, hi0)
    n_elite = max(2, math.ceil(ens.elite_fraction * ens.size))

    all_results, history, ranges = [], [], []
    previous = _load_previous_results(config, specs)
    if previous is not None:
        all_results.append(previous)
        print(f"[calibration] {len(previous)} member(s) of earlier calibrations inside the current ranges")
        if len(previous) >= n_elite:
            prev_elite = score_members(previous, config.metrics, config.score).head(n_elite)
            mean, cov = fit_distribution(_internal(prev_elite, specs), cov, ens.inflation,
                                         ens.min_spread_fraction)
        else:
            previous = None
    stop_reason = f"reached ensemble.max_rounds ({ens.max_rounds})"
    prev_elite_uids = None

    for r in range(ens.max_rounds):
        round_name = f"round_{r:02d}"
        round_dir = os.path.join(config.output_root, round_name)
        results_file = os.path.join(round_dir, "results.csv")
        dist_file = os.path.join(round_dir, "distribution.npz")

        if config.resume and os.path.isfile(results_file):
            print(f"[calibration] {round_name}: loading finished round")
            res = pd.read_csv(results_file)
            dist = np.load(dist_file)
            mean, cov = dist["mean"], dist["cov"]
        else:
            seed = ens.seed + 100 * r
            if r == 0 and previous is None:
                internal = sample_lhs(lo0, hi0, ens.size, seed)
                explore = np.zeros(ens.size, dtype=bool)
            else:
                internal, explore = sample_round(mean, cov, lo0, hi0, ens.size, ens.explore_fraction, seed)
            natural = np.column_stack([[s.from_internal(v) for v in internal[:, k]] for k, s in enumerate(specs)])

            full = np.column_stack(
                [natural[:, names.index(p.name)] if p.calibrate else np.full(ens.size, p.nominal)
                 for p in config.parameters])
            print(f"[calibration] {round_name}: running {ens.size} members in {round_dir}")
            res = runner.run_round(full, round_dir)
            # Only now: writing the setups replaces the whole round_dir
            pd.DataFrame(natural, columns=names).to_csv(os.path.join(round_dir, "members.csv"),
                                                        index_label="member")
            np.savez(dist_file, mean=mean, cov=cov)
            for k, name in enumerate(names):
                res[name] = natural[:, k]
            res["explore"] = explore
            res["round"] = r
            res["round_dir"] = round_name
            res["uid"] = [f"r{r}_m{m}" for m in res["member"]]

        res["ok"] = res["ok"].astype(bool)
        res = add_stats(res, config.metrics, config.output_root)
        res.drop(columns=["score", "feasible"], errors="ignore").to_csv(results_file, index=False)

        lo, hi = (lo0, hi0) if r == 0 and previous is None else sampled_range(mean, cov, lo0, hi0)
        ranges.append((lo, hi))
        n_ok = int(res["ok"].sum())
        print(f"[calibration] {round_name}: {n_ok}/{len(res)} members ok")
        for reason, count in res.loc[~res["ok"], "reason"].value_counts().items():
            print(f"    {count} failed: {reason}")
        if n_ok < ens.min_success_fraction * len(res):
            raise RuntimeError(
                f"Only {n_ok}/{len(res)} members of {round_name} succeeded (< min_success_fraction "
                f"{ens.min_success_fraction}). Check the failure reasons above; narrow the parameter "
                "ranges if the model crashes or dies for large parts of them.")

        all_results.append(res)
        ranked = score_members(pd.concat(all_results, ignore_index=True), config.metrics, config.score)
        results = pd.concat([ranked, pd.concat(all_results, ignore_index=True).query("not ok")],
                            ignore_index=True)
        elite = ranked.head(n_elite)
        best = ranked.iloc[0]
        this_round = ranked[ranked["round"] == r]

        elite_internal = _internal(elite, specs)
        next_mean, next_cov = fit_distribution(elite_internal, cov, ens.inflation, ens.min_spread_fraction)
        next_lo, next_hi = sampled_range(next_mean, next_cov, lo0, hi0)
        at_lo, at_hi = elite_at_bound(elite_internal, lo0, hi0)
        bound_warnings = [f"{s.name}: best members reach the original {'min' if a else 'max'} "
                          f"({s.min if a else s.max}) -- consider widening the range"
                          for s, a, b in zip(specs, at_lo, at_hi) if a or b]

        record = {"round": r, "n_ok": n_ok, "n_feasible_round": int(this_round["feasible"].sum()),
                  "best_score": best["score"], "elite_mean_score": elite["score"].mean(),
                  "median_score_round": this_round["score"].median(), "best_member": best["uid"]}
        record.update({f"best_rmse_{m.name}": best[f"rmse_{m.name}"] for m in config.metrics})
        history.append(record)
        history_df = pd.DataFrame(history)

        print(f"[calibration] {round_name}: best score {best['score']:.4g} ({best['uid']}, "
              f"{'passes' if best['feasible'] else 'fails'} the constraints), "
              f"elite mean {record['elite_mean_score']:.4g}, "
              f"{record['n_feasible_round']}/{n_ok} members of this round pass the constraints; "
              + ", ".join(f"{m.name} RMSE {best[f'rmse_{m.name}']:.3g}" for m in config.metrics))
        for w in bound_warnings:
            print(f"[calibration] warning: {w}")

        # Outputs after every round, so they can be inspected while the next one runs
        rmse_cols = [f"rmse_{m.name}" for m in config.metrics]
        results.to_csv(os.path.join(config.output_root, "results.csv"), index=False)
        history_df.to_csv(os.path.join(config.output_root, "history.csv"), index=False)
        elite[["uid", "score", "feasible"] + rmse_cols + names].to_csv(
            os.path.join(config.output_root, "top_parameters.csv"), index=False)
        correlations = pd.DataFrame(elite_internal, columns=names).corr(method="spearman")
        correlations.to_csv(os.path.join(config.output_root, "elite_correlations.csv"))
        ranked[accepted(ranked, config.metrics)][["uid", "score"] + rmse_cols + names].to_csv(
            os.path.join(config.output_root, "accepted_parameters.csv"), index=False)
        _write_best_parameters(os.path.join(config.output_root, "best_parameters.py"), config, best)

        if config.keep_best_outputs_fraction > 0 and not config.keep_run_outputs:
            _keep_best_outputs(round_dir, this_round, len(res), config.keep_best_outputs_fraction)

        is_last = r == ens.max_rounds - 1
        if prev_elite_uids is not None:
            # Both elites scored against the same (current) reference
            prev = ranked.set_index("uid").loc[prev_elite_uids, "score"].mean()
            improvement = (prev - record["elite_mean_score"]) / prev
            if improvement < ens.min_improvement:
                stop_reason = (f"the elite's mean score improved by only {100 * improvement:.2g}% in "
                               f"{round_name} (< ensemble.min_improvement {100 * ens.min_improvement:.2g}%)")
                is_last = True
        prev_elite_uids = list(elite["uid"])

        plot_dir = os.path.join(round_dir, "plots")
        os.makedirs(plot_dir, exist_ok=True)
        plot_fits(config.output_root, plot_dir, ranked, n_elite, config.metrics, f"round {r}")
        plot_diurnal(config.output_root, plot_dir, ranked, n_elite, config.metrics, f"round {r}")
        plot_parameters(plot_dir, this_round, elite, specs, lo, hi,
                        None if is_last else next_lo, None if is_last else next_hi, f"round {r}")
        plot_progress(config.output_root, ranked, history_df, config.metrics)
        plot_ranges(config.output_root, ranges, specs)
        plot_correlations(plot_dir, correlations, f"round {r}")
        plot_tradeoffs(config.output_root, ranked, n_elite, config.metrics, config.score)

        if is_last:
            break
        mean, cov = next_mean, next_cov

    print(f"[calibration] stopped: {stop_reason}")
    return assess(config, history_df, ranked, stop_reason, bound_warnings)


def _keep_best_outputs(round_dir, round_ranked, n_members, fraction):
    """Delete the NetCDF output of all members of a round except its best
    `fraction` (ranked as in the elite), and list the kept ones."""
    keep = round_ranked.head(math.ceil(fraction * n_members))
    keep[["uid", "member", "score", "feasible"]].to_csv(os.path.join(round_dir, "kept_outputs.csv"), index=False)
    kept = set(int(m) for m in keep["member"])
    for member in range(n_members):
        if member not in kept:
            for path in glob.glob(os.path.join(round_dir, "output", str(member), "*.nc")):
                os.remove(path)


def _internal(members, specs):
    """(n_members, n_params) array of the members' parameters in internal units."""
    return np.column_stack([[s.to_internal(v) for v in members[s.name]] for s in specs])


def _load_previous_results(config, specs):
    """Successful members of config.previous_results inside the current
    ranges, with the statistics of the current metrics (recomputed from their
    series files where missing). None if there are none."""
    if not config.previous_results:
        return None
    needed = [s.name for s in specs] + [f"rmse_{m.name}" for m in config.metrics]
    parts = []
    for k, path in enumerate(config.previous_results):
        df = pd.read_csv(path)
        missing = [c for c in needed if c not in df.columns]
        if missing:
            raise ValueError(f"previous_results {path} lacks the columns {missing}: it is not from a "
                             "calibration with the same parameters and metrics.")
        df = df[df["ok"].astype(bool)].copy()
        for s in specs:
            df = df[(df[s.name] >= s.min) & (df[s.name] <= s.max)]
        # Series files for the plots and statistics stay where the earlier calibration wrote them
        df["round_dir"] = [os.path.join(os.path.dirname(path), d) for d in df["round_dir"]]
        df["uid"] = [f"p{k}_{u}" for u in df["uid"]]
        parts.append(df.drop(columns=["score", "feasible"], errors="ignore"))
    previous = pd.concat(parts, ignore_index=True)
    if previous.empty:
        return None
    previous["ok"] = True
    previous["round"] = -1
    previous["explore"] = False
    return add_stats(previous, config.metrics, config.output_root)


def _write_best_parameters(path, config, best):
    lines = [
        "# Best member of the calibration, in natural units.",
        "# Paste into a QPy runscript, e.g.: lctlib[pft].<name> = best_parameters['<name>']",
        f"# member {best['uid']}, score {best['score']:.6g}",
        "best_parameters = {",
    ]
    for p in config.parameters:
        value = best[p.name] if p.calibrate else p.nominal
        lines.append(f"    {p.name!r}: {float(value)!r},")
    lines.append("}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
