"""Plain-language summary of a calibration, written at the end of a run.

Whether a fit is good needs a reference outside the model. Per objective, the
best member's RMSE is compared with every reference available for it: the
error you accept (sigma/relative_sigma) and the natural variability of the
observations (obs_spread_columns), plus its NSE (worse than the observed mean
if below 0). Per constraint, how many observations lie within the tolerance.
"""
import os

import numpy as np

from .metrics import typical_sigma, spread_sigma

MARGINAL_RATIO = 1.5


def references(metric):
    """{label: RMSE an objective should stay below} for every reference the metric has."""
    refs = {}
    sigma = typical_sigma(metric)
    if sigma is not None:
        refs["your sigma"] = sigma
    spread = spread_sigma(metric)
    if spread is not None:
        refs["observation spread"] = spread
    return refs


def accepted(ranked, metrics):
    """Members that pass every constraint and, for every objective with a
    sigma (else its observation spread), have an RMSE within it."""
    ok = ranked["feasible"].to_numpy(dtype=bool).copy()
    for m in metrics:
        if m.role != "objective":
            continue
        refs = references(m)
        ref = refs.get("your sigma", refs.get("observation spread"))
        if ref is not None:
            ok &= ranked[f"rmse_{m.name}"].to_numpy(dtype=float) <= ref
    return ok


def assess(config, history, ranked, stop_reason, bound_warnings):
    """Build the verdict text, print it, write it to
    <output_root>/calibration_verdict.txt, and return it."""
    best = ranked.iloc[0]
    lines = ["Calibration verdict", "=" * 19,
             f"Ran {len(history)} round(s); stopped because: {stop_reason}.",
             f"Best member: {best['uid']} (score {best['score']:.4g}, "
             f"{'passes' if best['feasible'] else 'FAILS'} the constraints)", ""]

    poor, unchecked = [], []
    for m in config.metrics:
        if m.role == "constraint":
            n = int(best[f"n_{m.name}"])
            within = best[f"nwithin_{m.name}"]
            within = 0 if np.isnan(within) else int(within)
            needed = int(np.ceil(m.min_within_fraction * n - 1e-9))
            label = "PASS" if within >= needed else "FAIL"
            if label == "FAIL":
                poor.append(m.name)
            lines.append(f"  - {m.name} (constraint, +-{m.tolerance:g}, {needed}/{n} needed): "
                         f"{within}/{n} observations within, "
                         f"mean offset {best[f'bias_{m.name}']:+.3g}, largest {best[f'maxabs_{m.name}']:.3g} "
                         f"-> {label}")
            continue

        rmse = best[f"rmse_{m.name}"]
        achievable = ranked[f"rmse_{m.name}"].min()
        nse = best[f"nse_{m.name}"]
        parts = [f"RMSE {rmse:.4g} ({rmse / achievable:.2f}x the best any member reached, {achievable:.4g})",
                 f"bias {best[f'bias_{m.name}']:+.3g}", f"r {best[f'r_{m.name}']:.2f}", f"NSE {nse:.2f}"]
        refs = references(m)
        worst_ratio = 0.0
        for label_ref, value in refs.items():
            ratio = rmse / value
            worst_ratio = max(worst_ratio, ratio)
            parts.append(f"{label_ref} {value:.4g}: {'within' if ratio <= 1 else f'{ratio:.2f}x'}")
        if not np.isnan(nse) and nse < 0:
            label = "POOR (worse than the observed mean)"
        elif not refs:
            label = "NO REFERENCE (set sigma or obs_spread_columns to judge it)"
            unchecked.append(m.name)
        elif worst_ratio <= 1:
            label = "GOOD"
        elif worst_ratio <= MARGINAL_RATIO:
            label = "MARGINAL"
        else:
            label = "POOR"
        if label.startswith(("POOR", "MARGINAL")):
            poor.append(m.name)
        lines.append(f"  - {m.name} (objective): " + ", ".join(parts) + f" -> {label}")

    if len(history) > 1:
        first, last = history["elite_mean_score"].iloc[0], history["elite_mean_score"].iloc[-1]
        lines.append(f"\nThe elite's mean score went from {first:.4g} (round 0) to {last:.4g}. "
                     "(Scores of different rounds use the reference of their time.)")

    if bound_warnings:
        lines.append("\nThe best members sit at an edge of the allowed range:")
        lines += [f"  - {w}" for w in bound_warnings]

    lines.append("")
    if not poor:
        lines.append("VERDICT: every checked metric is fit within its references"
                     + (f"; not checked: {', '.join(unchecked)}." if unchecked else "."))
    else:
        lines.append(f"VERDICT: the fit is still marginal/poor for: {', '.join(poor)}.")
        if bound_warnings:
            lines.append("Widen the ranges listed above first, then run again.")
        elif stop_reason.startswith("reached"):
            lines.append("The score was still improving: raise ensemble.max_rounds and rerun with "
                         "resume=True (finished rounds are loaded, not rerun).")
        else:
            lines.append("More rounds will not help. Check the metric definitions (variable, scaling), "
                         "or the model cannot match this observation with these parameters "
                         "(see tradeoffs.png for what can be fit together).")

    text = "\n".join(lines)
    print(text)
    with open(os.path.join(config.output_root, "calibration_verdict.txt"), "w") as f:
        f.write(text + "\n")
    return text
