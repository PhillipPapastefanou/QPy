"""Ensemble sampling for 4D-En-Var (Pinnington et al. 2020, Sect. 2.3.2).

The prior ensemble is a Latin-hypercube draw across the user-specified
parameter ranges. Each later iteration's ensemble is drawn from the
(inflated) linearized posterior computed by qpy_calibrate.fourdenvar,
projected back into parameter space through the *previous* iteration's
perturbation matrix X_b' (eq. 23 of the paper), then clipped back to the
user's hard bounds.
"""
import numpy as np
from scipy.stats import qmc


def sample_lhs_ensemble(param_specs, n_ensemble, seed):
    """Latin-hypercube draw of n_ensemble parameter vectors within [min, max]
    for each parameter (log10-transformed first for a scale=='log'
    parameter, so the draw is uniform in log space rather than linear space
    -- see ParameterSpec.scale). Returns an (n_ensemble, n_params) array, in
    this internal (possibly log10) space; callers convert back to natural
    units via ParameterSpec.from_internal before using the values outside
    the 4D-En-Var machinery."""
    d = len(param_specs)
    sampler = qmc.LatinHypercube(d=d, seed=seed)
    unit = sampler.random(n=n_ensemble)
    lo = np.array([p.internal_min for p in param_specs])
    hi = np.array([p.internal_max for p in param_specs])
    return lo[None, :] + unit * (hi - lo)[None, :]


def perturbation_matrix(members: np.ndarray):
    """Given an (Ne, d) ensemble, return (mean (d,), X_b' (d, Ne)) following
    eq. 21 of Pinnington et al. (2020): each column of X_b' is one member's
    deviation from the ensemble mean, scaled by 1/sqrt(Ne-1)."""
    mean = members.mean(axis=0)
    Ne = members.shape[0]
    X_b_prime = (members - mean[None, :]).T / np.sqrt(Ne - 1)
    return mean, X_b_prime


def posterior_ensemble(mean_params, X_b_prime, P_w, n_ensemble, inflation, rng, param_specs):
    """Draw a new ensemble consistent with the linear posterior covariance
    P_w (in ensemble-weight space), projected into parameter space via
    X_b' (x0 = x_b + X_b' w, eq. 23), inflated by `inflation` to counter
    ensemble collapse (Sect. 4.1), and clipped to the user's hard bounds."""
    Ne_w = P_w.shape[0]
    P_w_inflated = P_w * (inflation ** 2)
    eigval, eigvec = np.linalg.eigh(P_w_inflated)
    eigval = np.clip(eigval, 0.0, None)
    sqrt_Pw = eigvec @ np.diag(np.sqrt(eigval)) @ eigvec.T

    z = rng.standard_normal(size=(n_ensemble, Ne_w))
    w_samples = z @ sqrt_Pw.T                      # (n_ensemble, Ne_w)
    members = mean_params[None, :] + w_samples @ X_b_prime.T   # (n_ensemble, d)

    lo = np.array([p.internal_min for p in param_specs])
    hi = np.array([p.internal_max for p in param_specs])
    return np.clip(members, lo[None, :], hi[None, :])
