"""The 4D-En-Var core: builds and solves the ensemble-variational cost
function of Pinnington et al. (2020, "LAVENDAR"), eqs. 24-27.

Unlike the paper (which minimises J(w) with a gradient-descent routine, eq.
25), we exploit the fact that J is exactly quadratic in the ensemble weight
vector w under the tangent-linear approximation (eq. 18): this makes the
minimiser available in closed form as a single (Ne x Ne) linear solve, with
no optimiser, learning rate, or convergence tuning required. This is the
same maths, just solved directly instead of iteratively.

    J(w) = 1/2 w^T w + 1/2 (H X_b' w + d)^T R^-1 (H X_b' w + d)

    d = h(x_b) - y_hat                      (innovation at the ensemble mean)
    grad J(w) = w + (H X_b')^T R^-1 (H X_b' w + d) = 0
    =>  (I + (H X_b')^T R^-1 (H X_b')) w = -(H X_b')^T R^-1 d
"""
import numpy as np


def solve_envar(H_Xb_prime: np.ndarray, innovation: np.ndarray, R_diag: np.ndarray):
    """Solve for the posterior ensemble weights w.

    H_Xb_prime : (n_obs, Ne) ensemble perturbation matrix in observation
                 space (eq. 26): column i is (h(x_b,i) - h_bar) / sqrt(Ne-1).
    innovation : (n_obs,) = h_bar - y_hat, the misfit of the ensemble-mean
                 model trajectory against the stacked observation vector.
    R_diag     : (n_obs,) observation-error variances (diagonal R).

    Returns (w, P_w, A) where P_w = A^-1 is the posterior covariance in
    ensemble-weight space.
    """
    Ne = H_Xb_prime.shape[1]
    Rinv = 1.0 / R_diag
    HX = H_Xb_prime
    A = np.eye(Ne) + (HX.T * Rinv) @ HX
    b = -(HX.T * Rinv) @ innovation
    w = np.linalg.solve(A, b)
    P_w = np.linalg.inv(A)
    return w, P_w, A


def cost_function(w, H_Xb_prime, innovation, R_diag):
    Rinv = 1.0 / R_diag
    resid = H_Xb_prime @ w + innovation
    return 0.5 * np.dot(w, w) + 0.5 * np.dot(resid, resid * Rinv)


def cost_gradient(w, H_Xb_prime, innovation, R_diag):
    Rinv = 1.0 / R_diag
    resid = H_Xb_prime @ w + innovation
    return w + H_Xb_prime.T @ (resid * Rinv)


def gradient_test(H_Xb_prime, innovation, R_diag, w0=None, etas=None, seed=0):
    """Gradient-correctness check, following eq. 28 / Fig. 1 of Pinnington
    et al. (2020):

        f(eta) = | J(w + eta*b) - J(w) | / (eta * b^T grad J(w))

    should tend to 1 as eta -> 0 (until eta gets so small that floating-point
    noise dominates). Returns {eta: |f(eta) - 1|} for plotting; a
    monotonically decreasing curve down to ~1e-6..1e-8 before it turns back
    up is the same signature the paper reports and confirms the cost
    function and its gradient are mutually consistent.
    """
    Ne = H_Xb_prime.shape[1]
    rng = np.random.default_rng(seed)
    if w0 is None:
        w0 = np.zeros(Ne)
    b = rng.standard_normal(Ne)
    b = b / np.linalg.norm(b)

    J0 = cost_function(w0, H_Xb_prime, innovation, R_diag)
    grad0 = cost_gradient(w0, H_Xb_prime, innovation, R_diag)
    denom_ref = np.dot(b, grad0)

    if etas is None:
        etas = np.logspace(-9, -1, 9)

    out = {}
    for eta in etas:
        J1 = cost_function(w0 + eta * b, H_Xb_prime, innovation, R_diag)
        denom = eta * denom_ref
        out[float(eta)] = float(np.abs((J1 - J0) / denom - 1.0)) if denom != 0 else float("nan")
    return out
