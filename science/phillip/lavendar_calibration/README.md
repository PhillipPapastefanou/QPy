# LAVENDAR-style plant-hydraulics calibration for QPy/QUINCY

A generic, site-agnostic tool to auto-calibrate QUINCY's plant-hydraulic
parameters against observations. You give it parameter ranges and one or
more evaluation metrics in a plain Python config script (same style as any
other QPy runscript); it runs an ensemble of QUINCY simulations in parallel,
fits the ensemble against your observations using 4D ensemble-variational
data assimilation (4D-En-Var), and iterates a handful of times until it
converges on a posterior parameter set.

This is a from-scratch implementation of the method used in
[Pinnington et al. (2020), "The Land Variational Ensemble Data Assimilation
Framework: LAVENDAR v1.0.0"](https://doi.org/10.5194/gmd-13-55-2020),
adapted from JULES to QUINCY. See "The method" below for how it maps onto
the paper's equations.

## Quick start

```bash
cd science/phillip/lavendar_calibration
cp config_example.py my_site.py   # edit site, ranges, obs paths
python run_calibration.py my_site.py
```

Outputs land in `<output_root>/`:
- `posterior_parameters.py` — the final calibrated parameter values, as a plain
  Python dict (`from posterior_parameters import posterior_parameters`) you can
  paste straight into a normal QPy runscript's `lctlib[pft].<name> = ...` lines
- `calibration_verdict.txt` — a plain-language "did this actually fit, and is a
  second/third round worth it" summary (see "Was the fit any good?" below)
- `calibration_history.csv` — cost function and per-metric RMSE per iteration
- `convergence.png`, `parameter_distributions.png`, `gradient_test.png` — diagnostic plots
- `iter_XX/` — one full ensemble's QUINCY setups/output and `metric_table.csv` (per-member, per-metric RMSE)

## Writing a config

A config is a plain Python script -- no YAML/JSON -- written the same way as
any other QPy runscript: import the spec classes from `qpy_calibrate.config`,
build up `ParameterSpec`/`MetricSpec`/`EnsembleSpec`/`SimulationSpec`
instances, and assign the final `CalibrationConfig` to a module-level
variable named `config`. See `config_example.py` for a complete, working
example (DE-Hai site, ranges taken from an existing hand-tuned sweep, real
observation files). The pieces you edit:

- **`site`** — a FLUXNET3 site ID (must exist in QUINCY's site list, same
  as any other QPy runscript).
- **`parameters`** — one entry per parameter to calibrate: a `name`
  (matching a field on QUINCY's `Lctlib_Item`, e.g. `psi50_xylem`,
  `k_xylem_sat`, `gamma_stem_max`, `g1_medlyn`, ...; see
  `src/quincy/base/Lctlib.py` for the full list) and a `min`/`max` range.
  Unknown names fail immediately at startup rather than silently doing
  nothing. Global (non-PFT) process parameters are also supported via
  `target="paramlist"` + `category="<namelist_category>"`, e.g. for
  `gdd_t_air_threshold` under `lnd_q_pheno_nml`.

  **If you already know some parameters matter less** (e.g. from an earlier
  sensitivity-analysis sweep like the ones under
  `science/phillip/DE-Hai/runscripts/`), fix them instead of calibrating
  them: set `calibrate=False` and `nominal=<value>` instead of `min`/`max`:
  ```python
  ParameterSpec(name="g0", calibrate=False, nominal=0.0025)
  ```
  A fixed parameter is held at `nominal` in every ensemble member and
  excluded from the 4D-En-Var solve entirely -- it's not that it's
  "unimportant weight", it's simply removed from the calibration problem's
  dimensionality. This matters because the whole ensemble (`ensemble.size`
  members) has to jointly resolve every *calibrated* parameter's effect on
  every metric: dropping parameters you already know don't move your
  metrics leaves more of that same ensemble size to pin down the ones that
  do, instead of spending it on directions the data can't actually
  constrain. At least one parameter must remain calibrated.

  **If a parameter's plausible range spans orders of magnitude** (e.g.
  `root_scale`: 0.01 .. 2.0 -- a 200x span), add `scale="log"`:
  ```python
  ParameterSpec(name="root_scale", min=0.01, max=2.0, scale="log")
  ```
  A uniform *linear* draw over such a range would put almost the whole
  ensemble above ~1.0 and barely sample the small end, and the Gaussian
  posterior draw used on later iterations doesn't make sense for a
  multiplicative quantity either. `scale="log"` makes the LHS sampling, the
  ensemble perturbation matrix, and the posterior draw all happen in log10
  space internally (this is exactly what the existing hand-tuned DE-Hai
  sweep scripts already do by hand for `root_scale`); `min`/`max`/`nominal`
  are still given, and the calibrated result is still reported (in
  `posterior_parameters.py`, `calibration_history.csv`), in the parameter's
  normal, natural units -- the log10 transform is invisible outside the
  sampling/solve step. Requires `min` (or `nominal`, for a fixed parameter)
  to be > 0. `parameter_distributions.png` labels a log-scaled parameter's
  panel "(log10)" since its histogram is of the internal, log-space values.
- **`metrics`** — one entry per observation stream to calibrate against:
  the QUINCY output `category`/`variable` (as in
  `<CATEGORY>_<identifier>_<timeres>.nc`, e.g. `PHYD`/`psi_stem_avg`), a
  CSV `obs_file` with a datetime column and the `obs_column` to compare
  against, and either `sigma` (absolute observation-error std) or
  `relative_sigma` (fraction of |obs|). You can list as many metrics as you
  like (LAI, GPP, sap flow, stem water potential, ...); `weight` lets you
  tune how strongly each one pulls the calibration.
  **Time resolution matters**: most flux/pool variables (GPP, LE, LAI) are
  only meaningful as daily means, QUINCY's default
  (`simulation.output_interval == "daily"`). Sap flow and stem water
  potential are inherently sub-daily; for
  those, set `simulation.output_interval = "fluxnet_timestep"` plus
  `fluxnet_forc_start_yr`/`fluxnet_forc_last_yr` (a trailing window of the
  transient run) to get half-hourly output for that window -- QUINCY only
  populates real timestamps for sub-daily output through this mechanism, not
  through a plain global timestep setting. All metrics in one calibration
  run share the same resolution, so don't mix a sub-daily and a daily metric
  in one config.

  **Soft plausibility constraints** (no observations needed): if you only
  have, say, GPP and ET data, GPP/ET alone often can't rule out physically
  odd parameter combinations (equifinality) -- multiple very different
  hydraulic settings can produce a similar GPP/ET trajectory. If you still
  know, from domain knowledge, roughly what range an *unobserved* internal
  variable should stay in (e.g. "midday leaf water potential should be
  between -2.5 and -0.3 MPa"), add a metric with `target_min`/`target_max`
  instead of `obs_file`/`obs_column`:
  ```python
  MetricSpec(
      name="psi_leaf_midday",
      category="PHYD",
      variable="psi_leaf_avg",
      target_min=-2.5,
      target_max=-0.3,
      hour_start=11,   # optional: restrict to local hours 11-13 ("midday");
      hour_end=13,     # needs simulation.output_interval == "fluxnet_timestep"
      weight=0.5,
  )
  ```
  This is folded into the exact same 4D-En-Var cost function as a real
  metric, as a pseudo-observation centred on the range's midpoint (its
  implied uncertainty is derived from the width of the range via
  `range_confidence_sigma`, default treats min/max as a ~95% plausible
  interval, not a hard wall) -- it nudges the fit away from combinations
  that would push the unobserved variable somewhere implausible, without
  claiming to know its true value. Omit `hour_start`/`hour_end` to apply the
  constraint to whatever resolution you're already using (e.g. the daily
  mean) instead of requiring sub-daily output; just note a daily mean runs
  less negative than a true midday value, so you may need to loosen the
  range accordingly in that case.
- **`ensemble`** — `size` (also the batch parallelism), `max_iterations`,
  and `convergence_tol` (relative drop in the cost function below which the
  loop stops early).
- **`simulation.forcing_file_override`** — most FLUXNET3 sites' standard
  forcing stops around 2012; if your observations are more recent, point
  this at a site-specific extended forcing `.dat` file (as several existing
  DE-Hai runscripts already do by hand) instead of the one QPy resolves
  automatically from the site list.
- **`run_mode`** — `"local"` runs the ensemble with a local
  `multiprocessing.Pool` (good for a quick test or a small ensemble on a
  workstation, but only works if the shell QPy itself is running in already
  has the right modules loaded for QUINCY's shared libraries -- see
  "Model crashes" below); `"slurm_array"` submits one SLURM array task per
  ensemble member via `sbatch --wait` and blocks until the whole batch
  finishes (the intended mode for `ensemble.size` above ~100, since each
  array task loads its own module environment via
  `src/quincy/run_scripts/submit.py`, and the only practical mode once
  `ensemble.size` exceeds a single node's core count). `slurm_ram_in_gb`
  (default 4) and `slurm_partition` (default `"small,work"`) set each
  array task's SLURM resource request.
- **`simulation.soil_sand`/`soil_silt`** — override the site's default soil
  texture (clay is derived as `1 - sand - silt`); set both together, e.g. to
  match a value a previous hand-tuned sweep for this site already settled
  on, or leave both unset to keep the site-level default.
- **`clip_negative_obs_to_zero`**: for a physically non-negative observed
  quantity whose sensor readings occasionally dip slightly below 0 from
  noise (e.g. sap-flow flux density near zero at night), set this to clip
  those to 0 before use, instead of letting them pull the fit toward
  matching sensor noise. This matches the convention already used in the
  existing DE-Hai comparison scripts for sap flow (`J0.5`); not meaningful
  for a range constraint (there's no real observation to clip).
- **`model_scale`**: multiply the model's raw value by this factor before
  any comparison -- for a unit conversion and/or an empirically chosen
  correction factor. DE-Hai's sap-flow metric uses this: the existing Julia
  analysis (`src/postprocessing/julia/core/qcomparer_2023.jl`,
  `calculate_mod_obs_rmse_2023`) found that QUINCY's `G_per_sap_area_avg`,
  scaled by `x1000` (unit conversion) `x0.5` (an empirical correction --
  `"G_rmse_05"` there, versus the `1x`/`0.25x`/`2x` alternatives also
  tried), best matches observed sap-flow flux density (`J0.5`) in *absolute*
  units -- a different, more literal comparison than dividing both series
  by their own max (`normalize`). Set `model_scale=500.0` (`1000 * 0.5`) and
  leave `normalize` off to reproduce that.
- **`relative_sigma` and near-zero observations**: `relative_sigma` scales
  the assumed observation error with `|obs|`, floored at a tiny constant so
  it never hits exactly zero. For a variable that legitimately sits near
  zero some of the time (e.g. night-time or winter GPP), that floor can make
  those points count as near-perfectly-known, dominating the cost function
  and pulling the fit toward matching noise in the small values rather than
  the signal in the large ones. If you see the reported cost or RMSE behave
  oddly for such a variable, switch that metric to an absolute `sigma`
  instead (or a `sigma` floor added on top of `relative_sigma` in your own
  obs prep).

## The method, briefly

Classic sensitivity-analysis sweeps (LHS/Sobol over thousands of runs) are
good for asking *which* parameters matter. Calibration — *what values* best
match observations — is a different problem, and a naive "sample a batch,
rank by RMSE, narrow the ranges, resample, repeat" loop needs many outer
iterations (and therefore many thousands of model runs in total) to
converge, with no principled way to decide how much to narrow the ranges
each time.

4D-En-Var instead does the following, once per iteration:

1. Draw an ensemble of `ensemble.size` parameter vectors (Latin hypercube on
   iteration 0; a linearized-posterior draw afterwards — see below).
2. Run the whole ensemble (this is the expensive part, and the only part
   that needs the actual model).
3. For every metric, merge each member's model output onto the
   observations and stack everything into one observation vector `y_hat`,
   one obs-error-variance vector, and one ensemble perturbation matrix in
   observation space (`ĤX_b'`, eq. 26 of the paper) — this plays the role
   the model's tangent-linear/adjoint would in 4D-Var, but is built purely
   from the ensemble's spread, with no derivative of QUINCY needed.
4. Solve the ensemble-space cost function
   `J(w) = 1/2 w^T w + 1/2 (ĤX_b' w + d)^T R^-1 (ĤX_b' w + d)`
   for the posterior weight vector `w`. Because this is *quadratic* in `w`,
   the minimum is a single `(Ne x Ne)` linear solve
   (`qpy_calibrate/fourdenvar.py::solve_envar`) — no gradient-descent
   tuning needed, unlike the general 4D-Var case in the paper.
5. Reconstruct the posterior parameter vector `x_a = x_b + X_b' w` and its
   covariance in ensemble-weight space, `P_w`.
6. If the relative drop in cost is below `convergence_tol`, stop. Otherwise
   draw a new ensemble around `x_a` using `P_w` (inflated by
   `ensemble.inflation` to guard against the ensemble collapsing too
   tightly before the estimate has actually converged — see Sect. 4.1 of
   the paper), clip to the user's hard bounds, and go to step 2.

So the total cost is `ensemble.size x max_iterations` model runs — typically
a few hundred to ~1000 — rather than an open-ended resampling search, and
each iteration's update is a closed-form fit rather than a heuristic
"shrink the box" rule. `qpy_calibrate/fourdenvar.py::gradient_test`
reproduces the paper's own correctness check (eq. 28 / Fig. 1): it's run
automatically on iteration 0 and plotted to `gradient_test.png`.

## Was the fit any good?

Convergence (`rel. change < convergence_tol`) only tells you the ensemble
has *stopped moving* -- it says nothing about whether it stopped somewhere
that actually matches your observations. At the end of every run,
`qpy_calibrate/verdict.py` adds that separate check and writes it to
`calibration_verdict.txt` (also printed to the console): for each metric, it
compares the final RMSE against the observation-error `sigma`/`relative_sigma`
you specified for it (i.e. "how far off is the model, relative to how
precisely you said you trust this data") and labels it GOOD/MARGINAL/POOR.
It then combines that with the convergence status into one recommendation:

- **Converged + good fit everywhere** — done, nothing more to run.
- **Converged, but a metric is still marginal/poor** — more iterations of
  the *same* config won't help (it already stopped moving); instead widen
  that parameter's range, re-check the metric's `category`/`variable`/
  `obs_file`, or accept the model can't fully explain that observation here.
- **Not converged, but the cost was still dropping meaningfully** — a
  second or third round is likely worth it. Raise `ensemble.max_iterations`
  and set `resume=True` in the config, then rerun with the *same*
  `output_root`: it picks up the next ensemble from a checkpoint written
  after every non-final iteration (`<output_root>/resume_state/`), so you
  only pay for the *new* iterations, not the ones you already ran.
- **Not converged, and the cost was barely moving anyway** — more rounds
  probably won't help either; reconsider the parameter ranges or metrics
  instead of just adding iterations.

## Practical notes

- **"0/N members finished successfully" from the very first iteration**,
  with every member's `quincy_stderr.log`/`slurm.err` showing an
  `error while loading shared libraries` message, means QUINCY's shared
  libraries aren't resolvable in whatever environment actually ran the
  binary -- not a parameter-range problem. For `run_mode="local"`, the
  *calling shell* needs `ml gnu12/12.2.0 mpich/3.4.3-ofi netcdf/4.9.0
  hwloc/2.7.0` loaded before `python run_calibration.py ...`, since local
  mode just inherits whatever's already loaded. For `run_mode="slurm_array"`
  this is normally handled automatically (each array task's `submit.sh`,
  generated by `src/quincy/run_scripts/submit.py`, loads that same module
  set itself) -- if it still fails there, that shared template is missing a
  module QUINCY now needs (this happened once already: `hwloc/2.7.0` wasn't
  in it) and should be fixed there, since every other DE-Hai runscript
  submits through the same file.
- **Model crashes.** Extreme plant-hydraulic parameter combinations
  (implausible vulnerability curves, near-zero conductances, ...) can make
  QUINCY fail outright, or make it fail *after* producing partial output. Any
  member whose run doesn't finish cleanly is dropped before the 4D-En-Var
  solve; if fewer than `ensemble.min_success_fraction` of members survive,
  the run aborts with a message to narrow the ranges rather than silently
  fitting to a biased sub-ensemble.
- **Disk usage.** With `keep_run_outputs: false` (the default), each
  member's raw NetCDF output is deleted right after its metrics are
  extracted; only the per-iteration `metric_table.csv` and the top-level
  summaries are kept. Set it to `true` while debugging a new site/config.
- **Adding a new site** needs nothing beyond a config file, as long as the
  site is in QUINCY's standard FLUXNET3 site list — no code changes.
- **This calibrates against a fixed simulation window and PFT.** If your
  site or window is unusual (e.g., partial hydraulics support, different
  spin-up needs), copy `config_example.py`'s `simulation = SimulationSpec(...)`
  block and adjust it the same way you would in a normal QPy runscript.
