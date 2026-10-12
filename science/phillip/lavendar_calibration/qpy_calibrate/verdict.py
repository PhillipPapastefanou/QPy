"""Plain-language "did this work, and should I run more?" summary, written
at the end of a calibration run.

4D-En-Var's own convergence check (relative drop in the cost function) only
says the *ensemble* has stopped moving -- it says nothing about whether it
moved to somewhere that actually fits the data well. This module adds that
second, separate judgement: for each metric, how does the achieved RMSE
compare to how precisely you said you trust that observation
(sigma/relative_sigma)? And, combined with whether the loop formally
converged, should you bump ensemble.max_iterations and run a second or third
round (set resume=True, same output_root) instead of stopping here?
"""
import os

from .metrics import typical_sigma

GOOD_RATIO = 1.2
MARGINAL_RATIO = 2.5
STILL_IMPROVING_REL_CHANGE = 0.05


def assess(config, history, converged):
    """Build the verdict text, print it, write it to
    <output_root>/calibration_verdict.txt, and return it."""
    last = history[-1]
    lines = []
    lines.append("LAVENDAR calibration verdict")
    lines.append("=" * 29)
    lines.append(
        f"Ran {len(history)} iteration(s); "
        f"{'formally converged' if converged else 'stopped at max_iterations without formally converging'}."
    )

    per_metric = []
    for metric in config.metrics:
        rmse_key = f"rmse_{metric.name}"
        if rmse_key not in last:
            continue
        rmse_final = last[rmse_key]
        sigma = typical_sigma(metric)
        ratio = rmse_final / sigma if sigma > 0 else float("inf")
        if ratio <= GOOD_RATIO:
            tag = "GOOD"
        elif ratio <= MARGINAL_RATIO:
            tag = "MARGINAL"
        else:
            tag = "POOR"
        per_metric.append((metric.name, tag))
        kind = "range constraint" if metric.is_range_constraint else "observation"
        lines.append(
            f"  - {metric.name} ({kind}): final RMSE {rmse_final:.4g} vs. assumed obs-error "
            f"sigma {sigma:.4g} (ratio {ratio:.2f}) -> {tag}"
        )

    not_good = [name for name, tag in per_metric if tag != "GOOD"]
    rel_change_last = last.get("rel_change")
    still_improving = rel_change_last is not None and rel_change_last > STILL_IMPROVING_REL_CHANGE

    lines.append("")
    if converged and not not_good:
        lines.append("VERDICT: converged with a good fit on every metric. No further rounds needed.")
    elif converged:
        lines.append(
            f"VERDICT: converged, but the fit is still marginal/poor for: {', '.join(not_good)}. "
            "Running more iterations of *this* config won't help -- it has already stopped moving. "
            "Instead: widen the parameter range(s) most related to that metric, double-check the "
            "metric's category/variable/obs_file, or accept that plant hydraulics at this site/PFT "
            "can't fully explain that observation with the current parameter set."
        )
    elif still_improving:
        lines.append(
            f"VERDICT: did not fully converge yet (cost still dropped {rel_change_last:.1%} on the "
            "last iteration) -- worth a second or third round. Raise ensemble.max_iterations and set "
            "resume=True in the config, then rerun with the same output_root to continue from here "
            "instead of re-running the iterations you already paid for."
        )
    else:
        lines.append(
            "VERDICT: stopped at max_iterations without formally converging, but the cost was barely "
            "moving on the last iteration either -- more rounds of this same setup are unlikely to "
            "help much. Consider whether the parameter ranges bracket a plausible optimum, or whether "
            "the metrics/weights need adjusting, rather than just adding iterations."
        )

    text = "\n".join(lines)
    print("\n" + text + "\n")
    with open(os.path.join(config.output_root, "calibration_verdict.txt"), "w") as f:
        f.write(text + "\n")
    return text
