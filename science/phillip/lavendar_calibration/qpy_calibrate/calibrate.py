"""Orchestrates the LAVENDAR-style calibration loop:

    1. Draw an ensemble of parameter vectors from the user's ranges
       (Latin hypercube on iteration 0; a linearized-posterior draw on
       later iterations). Parameters marked calibrate=False are held fixed
       at their nominal value and excluded from this step entirely.
    2. Run the whole ensemble in parallel (locally or as a SLURM array).
    3. Extract each metric from each run and merge onto the observations.
    4. Solve the 4D-En-Var cost function in closed form for the posterior
       parameter vector and its ensemble-space covariance.
    5. Check convergence (relative drop in cost function); if not converged
       and iterations remain, draw a new, inflated ensemble around the
       posterior, checkpoint it, and go to 2.
    6. Report a plain-language verdict on whether the fit is actually good,
       and whether a further round (resume=True, higher max_iterations) is
       worth the extra runs.

Every iteration is expensive (n_ensemble full QUINCY runs), by design: this
replaces an open-ended "resample -> rerun -> resample" search with a small,
fixed number of ensemble batches (typically 2-5), each doing one principled
linear-algebra update instead of a heuristic re-sampling rule.
"""
import os

import numpy as np
import pandas as pd

from . import diagnostics, verdict
from .config import CalibrationConfig
from .ensemble import perturbation_matrix, posterior_ensemble, sample_lhs_ensemble
from .fourdenvar import cost_function, gradient_test, solve_envar
from .metrics import extract_ensemble_matrix
from .model_runner import QuincyModelRunner


def _checkpoint_dir(output_root):
    return os.path.join(output_root, "resume_state")


def _save_checkpoint(output_root, next_iteration, next_members, prior_members_iter0, last_ok_members, names):
    ckdir = _checkpoint_dir(output_root)
    os.makedirs(ckdir, exist_ok=True)
    pd.DataFrame(next_members, columns=names).to_csv(os.path.join(ckdir, "next_members.csv"), index=False)
    pd.DataFrame(prior_members_iter0, columns=names).to_csv(os.path.join(ckdir, "prior_members_iter0.csv"), index=False)
    if last_ok_members is not None:
        pd.DataFrame(last_ok_members, columns=names).to_csv(os.path.join(ckdir, "last_ok_members.csv"), index=False)
    with open(os.path.join(ckdir, "next_iteration.txt"), "w") as f:
        f.write(str(next_iteration))


def _load_checkpoint(output_root):
    ckdir = _checkpoint_dir(output_root)
    next_members = pd.read_csv(os.path.join(ckdir, "next_members.csv")).to_numpy()
    prior_members_iter0 = pd.read_csv(os.path.join(ckdir, "prior_members_iter0.csv")).to_numpy()
    last_ok_path = os.path.join(ckdir, "last_ok_members.csv")
    last_ok_members = pd.read_csv(last_ok_path).to_numpy() if os.path.isfile(last_ok_path) else None
    with open(os.path.join(ckdir, "next_iteration.txt")) as f:
        next_iteration = int(f.read().strip())
    history_path = os.path.join(output_root, "calibration_history.csv")
    history = pd.read_csv(history_path).to_dict("records") if os.path.isfile(history_path) else []
    return next_members, next_iteration, history, prior_members_iter0, last_ok_members


def run_calibration(config: CalibrationConfig):
    os.makedirs(config.output_root, exist_ok=True)
    rng = np.random.default_rng(config.ensemble.seed)
    runner = QuincyModelRunner(config)

    calibrated_params = [p for p in config.parameters if p.calibrate]
    fixed_params = [p for p in config.parameters if not p.calibrate]
    calibrated_names = [p.name for p in calibrated_params]
    calibrated_idx = [i for i, p in enumerate(config.parameters) if p.calibrate]
    fixed_idx = [i for i, p in enumerate(config.parameters) if not p.calibrate]
    fixed_values = np.array([p.nominal for p in fixed_params])

    if fixed_params:
        print(f"[LAVENDAR] {len(fixed_params)} parameter(s) fixed at their nominal value "
              f"(calibrate=False): {', '.join(p.name for p in fixed_params)}. "
              f"Calibrating the remaining {len(calibrated_params)}: {', '.join(calibrated_names)}.")

    def expand_to_full(members_calibrated):
        """(Ne, n_calibrated) ensemble, in internal (possibly log10) space
        -> (Ne, n_total) in natural units, with the fixed parameters' columns
        filled in at their nominal value, in the order model_runner expects
        (matching config.parameters)."""
        n = members_calibrated.shape[0]
        full = np.empty((n, len(config.parameters)))
        if calibrated_idx:
            linear = np.empty_like(members_calibrated)
            for j, p in enumerate(calibrated_params):
                linear[:, j] = p.from_internal(members_calibrated[:, j])
            full[:, calibrated_idx] = linear
        if fixed_idx:
            full[:, fixed_idx] = fixed_values[None, :]
        return full

    def to_natural_units(vec):
        """A single (n_calibrated,) vector, internal space -> natural units,
        for reporting (calibration_history.csv, posterior_parameters.py)."""
        return np.array([p.from_internal(v) for p, v in zip(calibrated_params, vec)])

    lo = np.array([p.internal_min for p in calibrated_params])
    hi = np.array([p.internal_max for p in calibrated_params])

    if config.resume and os.path.isdir(_checkpoint_dir(config.output_root)):
        members, start_iteration, history, prior_members_iter0, last_ok_members = \
            _load_checkpoint(config.output_root)
        print(f"[LAVENDAR] resuming from checkpoint: continuing at iteration {start_iteration}")
    else:
        if config.resume:
            print("[LAVENDAR] resume=True but no checkpoint found in this output_root; starting fresh.")
        members = sample_lhs_ensemble(calibrated_params, config.ensemble.size, config.ensemble.seed)
        members[0] = 0.5 * (lo + hi)  # a fixed, reproducible anchor member for diagnostics
        prior_members_iter0 = members.copy()
        history = []
        last_ok_members = None
        start_iteration = 0

    x_analysis = members.mean(axis=0)
    converged = False

    for iteration in range(start_iteration, config.ensemble.max_iterations):
        iter_dir = os.path.join(config.output_root, f"iter_{iteration:02d}")
        print(f"[LAVENDAR] iteration {iteration}: running {members.shape[0]} ensemble members in {iter_dir}")

        run_dirs, success = runner.run_ensemble(expand_to_full(members), iter_dir)
        n_ok = sum(success)
        print(f"[LAVENDAR] {n_ok}/{len(success)} members finished successfully")

        min_required = max(3, int(np.ceil(config.ensemble.min_success_fraction * len(success))))
        if n_ok < min(min_required, len(success)):
            raise RuntimeError(
                f"Only {n_ok}/{len(success)} ensemble members finished successfully. This "
                "usually means some parameter combinations are physically unstable (e.g. "
                "hydraulic failure crashing the run). Narrow the parameter ranges and retry."
            )

        Y, R_diag, H, ok_idx, metric_table = extract_ensemble_matrix(run_dirs, success, config.metrics)
        ok_members = members[ok_idx]
        last_ok_members = ok_members

        mean_params, X_b_prime = perturbation_matrix(ok_members)

        h_mean = H.mean(axis=1)
        HXb = (H - h_mean[:, None]) / np.sqrt(len(ok_idx) - 1)
        innovation = h_mean - Y

        w, P_w, _A = solve_envar(HXb, innovation, R_diag)
        x_analysis = mean_params + X_b_prime @ w
        x_analysis = np.clip(x_analysis, lo, hi)

        cost_prior = float(cost_function(np.zeros_like(w), HXb, innovation, R_diag))
        cost_post = float(cost_function(w, HXb, innovation, R_diag))

        if iteration == 0 and config.ensemble.run_gradient_check:
            eta_to_ferr = gradient_test(HXb, innovation, R_diag)
            diagnostics.plot_gradient_test(
                os.path.join(config.output_root, "gradient_test.png"), eta_to_ferr)

        rmse_by_metric = metric_table.groupby("metric")["rmse"].mean().to_dict()
        rel_change = abs(cost_prior - cost_post) / max(abs(cost_prior), 1e-8)
        converged = rel_change < config.ensemble.convergence_tol

        record = dict(
            iteration=iteration,
            n_members=len(ok_idx),
            cost_prior=cost_prior,
            cost_posterior=cost_post,
            rel_change=rel_change,
        )
        record.update({f"rmse_{k}": v for k, v in rmse_by_metric.items()})
        record.update({f"param_{p.name}": v for p, v in zip(calibrated_params, to_natural_units(x_analysis))})
        record.update({f"param_{p.name}": p.nominal for p in fixed_params})
        history.append(record)

        pd.DataFrame(history).to_csv(os.path.join(config.output_root, "calibration_history.csv"), index=False)
        metric_table.to_csv(os.path.join(iter_dir, "metric_table.csv"), index=False)
        diagnostics.plot_iteration(config, iteration, ok_members, x_analysis, metric_table)

        print(f"[LAVENDAR] iter {iteration}: cost {cost_prior:.4f} -> {cost_post:.4f} "
              f"(rel. change {rel_change:.4f}); mean RMSE by metric: {rmse_by_metric}")

        if not config.keep_run_outputs:
            _prune_raw_outputs(run_dirs)

        if converged:
            print("[LAVENDAR] Converged.")
            break

        # Compute (and checkpoint) the next ensemble whenever we haven't
        # converged -- including on the last allowed iteration. Otherwise a
        # later resume=True run would find only the checkpoint saved after
        # the *previous* iteration (pointing at the iteration that just ran)
        # and re-run it, wasting a full, expensive ensemble batch instead of
        # actually continuing past where this run stopped.
        new_members = posterior_ensemble(
            mean_params=x_analysis,
            X_b_prime=X_b_prime,
            P_w=P_w,
            n_ensemble=config.ensemble.size,
            inflation=config.ensemble.inflation,
            rng=rng,
            param_specs=calibrated_params,
        )
        new_members[0] = x_analysis
        _save_checkpoint(config.output_root, iteration + 1, new_members, prior_members_iter0, ok_members, calibrated_names)

        if iteration == config.ensemble.max_iterations - 1:
            print("[LAVENDAR] Reached max_iterations without formal convergence; using the last estimate.")
            break

        members = new_members

    diagnostics.plot_parameter_distributions(
        os.path.join(config.output_root, "parameter_distributions.png"),
        prior_members_iter0, last_ok_members if last_ok_members is not None else members,
        calibrated_params,
    )
    diagnostics.plot_convergence(config, history)

    final_params = {p.name: float(v) for p, v in zip(calibrated_params, to_natural_units(x_analysis))}
    final_params.update({p.name: p.nominal for p in fixed_params})
    out_path = os.path.join(config.output_root, "posterior_parameters.py")
    _write_posterior_parameters_py(out_path, final_params)
    print(f"[LAVENDAR] done. Posterior parameters written to {out_path}")

    verdict.assess(config, history, converged)

    return final_params, history


def _write_posterior_parameters_py(path, params: dict):
    """Write the calibrated parameters as a plain importable Python dict
    (`from posterior_parameters import posterior_parameters`), instead of
    JSON, so they can be copy-pasted straight into a normal QPy runscript's
    `lctlib[pft].<name> = ...` assignments."""
    with open(path, "w") as f:
        f.write('"""Posterior parameter values from a LAVENDAR calibration run.\n\n')
        f.write("Import directly: `from posterior_parameters import posterior_parameters`,\n")
        f.write("or copy the values into a normal QPy runscript.\n\"\"\"\n\n")
        f.write("posterior_parameters = {\n")
        for name, value in params.items():
            f.write(f"    {name!r}: {value!r},\n")
        f.write("}\n")


def _prune_raw_outputs(run_dirs):
    """Delete each member's whole run directory (raw NetCDF output plus its
    namelist/lctlib/climate.dat symlink) once its metrics have been
    extracted, to keep disk usage bounded across many ensembles x
    iterations. The per-member parameter values and RMSEs already live in
    <iter_dir>/metric_table.csv and <output_root>/calibration_history.csv,
    so nothing under run_dirs is needed afterwards."""
    import shutil
    for rd in run_dirs:
        shutil.rmtree(rd, ignore_errors=True)
