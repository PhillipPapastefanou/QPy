"""Sampling between rounds (cross-entropy method).

Round 0 is a Latin hypercube over the original ranges. Every later round
samples a multivariate normal fitted to the elite (best members so far):
its mean moves to where the good members are, and its covariance shrinks for
parameters the data constrain while staying wide for those it doesn't, and
follows correlated parameter combinations that fit equally well. A part of
every round still samples the original ranges as a check.

All functions work in the internal parameter space (log10 for scale=="log",
see ParameterSpec); ranges are arrays lo, hi of shape (n_params,).
"""
import numpy as np
from scipy.stats import qmc

# Spread of a uniform distribution, in units of its width
UNIFORM_STD = 1.0 / np.sqrt(12.0)


def original_ranges(param_specs):
    lo = np.array([p.internal_min for p in param_specs])
    hi = np.array([p.internal_max for p in param_specs])
    return lo, hi


def sample_lhs(lo, hi, n, seed):
    """Latin-hypercube draw of n parameter vectors within [lo, hi]."""
    if n <= 0:
        return np.empty((0, len(lo)))
    unit = qmc.LatinHypercube(d=len(lo), seed=seed).random(n=n)
    return lo[None, :] + unit * (hi - lo)[None, :]


def uniform_distribution(lo, hi):
    """Mean and covariance of the uniform distribution over [lo, hi] (round 0)."""
    return 0.5 * (lo + hi), np.diag((UNIFORM_STD * (hi - lo)) ** 2)


def fit_distribution(elite, prev_cov, inflation, min_spread_fraction):
    """Mean and covariance of the elite (n_elite, n_params) for the next round.

    The covariance is inflated by `inflation` (in standard deviations), and no
    parameter's spread may drop below `min_spread_fraction` of its previous
    spread in one round, so the search can't collapse onto a few lucky members.
    """
    mean = elite.mean(axis=0)
    cov = np.atleast_2d(np.cov(elite, rowvar=False)) * inflation ** 2

    std = np.sqrt(np.diag(cov))
    min_std = min_spread_fraction * np.sqrt(np.diag(prev_cov))
    scale = np.maximum(1.0, min_std / np.maximum(std, 1e-300))
    cov = cov * np.outer(scale, scale)
    return mean, cov


def sample_distribution(mean, cov, lo0, hi0, n, seed, max_tries=50):
    """n draws of the multivariate normal, redrawing those outside the original ranges."""
    rng = np.random.default_rng(seed)
    out = np.empty((0, len(mean)))
    for _ in range(max_tries):
        draws = rng.multivariate_normal(mean, cov, size=2 * n, method="eigh")
        inside = np.all((draws >= lo0) & (draws <= hi0), axis=1)
        out = np.vstack([out, draws[inside]])
        if len(out) >= n:
            return out[:n]
    # Mostly outside the ranges (optimum at a bound): clip the rest
    rest = np.clip(rng.multivariate_normal(mean, cov, size=n - len(out), method="eigh"), lo0, hi0)
    return np.vstack([out, rest])


def sample_round(mean, cov, lo0, hi0, n, explore_fraction, seed):
    """n members: most from the fitted distribution, a fraction explore_fraction
    over the original ranges. Returns (members, explore flag)."""
    n_explore = int(round(n * explore_fraction))
    focus = sample_distribution(mean, cov, lo0, hi0, n - n_explore, seed)
    explore = sample_lhs(lo0, hi0, n_explore, seed + 1)
    flags = np.r_[np.zeros(len(focus), dtype=bool), np.ones(len(explore), dtype=bool)]
    return np.vstack([focus, explore]), flags


def sampled_range(mean, cov, lo0, hi0):
    """Range holding ~95% of a round's samples per parameter (mean +- 2 std), for plots and reports."""
    std = np.sqrt(np.diag(cov))
    return np.clip(mean - 2 * std, lo0, hi0), np.clip(mean + 2 * std, lo0, hi0)


def elite_at_bound(elite, lo0, hi0, tol=0.02):
    """Per parameter: does the elite reach the original lower/upper bound
    (within tol of the full width)? Then the optimum may lie outside the
    range and the range should be widened."""
    width = hi0 - lo0
    return elite.min(axis=0) <= lo0 + tol * width, elite.max(axis=0) >= hi0 - tol * width
