# Calibrating QUINCY's plant hydraulics in rounds

A site-agnostic tool to calibrate QUINCY parameters (written for the
plant-hydraulic ones) against observations. You give it parameter ranges and
one or more metrics in a plain Python config script (same style as any other
QPy runscript). It runs an ensemble of QUINCY simulations as a SLURM array,
keeps the best members, and runs further rounds that sample more and more
tightly around them.

The code lives in `src/calibration/`; this folder only holds the configs and
the scripts that start a calibration.

## Quick start

```bash
cd science/phillip/adaptive_calibration
cp config_example.py my_site.py   # edit site, ranges, obs paths
python run_calibration.py my_site.py
python run_DE-Hai_psi_2023_minitest.py   # 2 rounds x 8 members, to test a setup first
```

Output in `<output_root>/`, updated after every round:
- `round_XX/plots/fit_<metric>.png` — observations vs. the best member and the
  bands spanned by the elite (best 10% of a round's size) and by 5x as many
  members
- `round_XX/plots/diurnal.png` — mean 24-hour cycle of the sub-daily metrics
  (observations vs. the best member and the elite, averaged over the
  observation times only)
- `round_XX/plots/parameters.png` — each parameter's distribution in the
  round vs. the elite, with the sampled range of this and the next round
- `progress.png` — score of all members per round, best score, and the best
  member's RMSE per metric
- `ranges.png` — how each parameter's sampled range shrank over the rounds
- `round_XX/plots/correlations.png`, `elite_correlations.csv` — rank
  correlations between the elite's parameters (parameters that compensate
  each other)
- `tradeoffs.png` — RMSE relative to the score's reference for every pair of
  objectives, for all members, with the
  front of the best combinations: how well the observations can be
  reproduced together
- `accepted_parameters.csv` — all members that pass every constraint and
  every objective's `sigma` (else its observation spread). They are not an
  unbiased sample of the acceptable region: later rounds sample densely
  around the best members.
- `best_parameters.py` — the best member's parameters as a Python dict, to
  paste into a QPy runscript (`lctlib[pft].<name> = ...`)
- `top_parameters.csv` — the elite's parameters (their spread shows how well
  each parameter is constrained)
- `results.csv` / `history.csv` — every member's parameters and scores / per-round summary
- `calibration_verdict.txt` — did it fit, and is another round worth it
- `round_XX/results.csv`, `round_XX/series/<member>.csv.gz` — per-member scores and
  model values at the observation timestamps

## Writing a config

A config is a plain Python script -- no YAML/JSON -- written the same way as
any other QPy runscript: import the spec classes from `src.calibration.config`,
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
  excluded from the search entirely -- it's not that it's
  "unimportant weight", it's simply removed from the calibration problem's
  dimensionality. Every calibrated parameter adds a dimension the search has to cover, so
  fixing the ones you know don't move your metrics lets the same number of
  runs pin down the others more tightly. At least one parameter must remain calibrated.

  **If a parameter's plausible range spans orders of magnitude** (e.g.
  `root_scale`: 0.01 .. 2.0 -- a 200x span), add `scale="log"`:
  ```python
  ParameterSpec(name="root_scale", min=0.01, max=2.0, scale="log")
  ```
  A uniform *linear* draw over such a range would put almost the whole
  ensemble above ~1.0 and barely sample the small end. `scale="log"` makes
  the sampling in every round happen in log10
  space internally (this is exactly what the existing hand-tuned DE-Hai
  sweep scripts already do by hand for `root_scale`); `min`/`max`/`nominal`
  are still given, and the calibrated result is still reported (in
  `best_parameters.py`, `results.csv`), in the parameter's
  normal, natural units -- the log10 transform is invisible outside the
  sampling/solve step. Requires `min` (or `nominal`, for a fixed parameter)
  to be > 0. The plots show a log-scaled parameter on a log axis.
- **`metrics`** — one entry per observation stream to calibrate against:
  the QUINCY output `category`/`variable` (as in
  `<CATEGORY>_<identifier>_<timeres>.nc`, e.g. `PHYD`/`psi_stem_avg`), a
  CSV `obs_file` with a datetime column and the `obs_column` to compare
  against. You can list as many metrics as you like (LAI, GPP, sap flow,
  stem water potential, ...). Each metric has a `role`:
  - `"objective"` (default for observations): fit as well as possible. Use
    it for densely observed variables. No error estimate is needed for the
    search; optionally give `sigma`/`relative_sigma` (the error you would
    accept) and/or `obs_spread_columns` (two quantile columns of the
    observations across replicates, e.g. trees, with `obs_spread_quantiles`)
    so the verdict can say whether the fit is good enough.
  - `"constraint"`: a ballpark check. `min_within_fraction` (default all)
    of the observations must lie within `tolerance` (in the variable's units)
    of the model. Members that pass are ranked ahead of the others, but how
    close they get does not matter, so a constraint never pulls the fit.
    Use it for sparse observations (a few leaf water potential dates) and
    plausibility ranges.
  `obs_time_shift_hours` corrects a time offset between the observation
  logger and the model (DE-Hai sap flow: +2).
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
  )
  ```
  Such a metric is a constraint by default: every model value must lie
  within the range (`tolerance` is set to half its width). To check a
  seasonal value instead of every time step, select months and aggregate,
  e.g. for a Mediterranean site "the August mean leaf water potential must
  be between -4.0 and -2.8 MPa in every year":
  ```python
  MetricSpec(name="psi_leaf_august", category="PHYD", variable="psi_leaf_avg",
             target_min=-4.0, target_max=-2.8,
             months=[8], aggregate="mean")   # one August mean per year
  ```
  `aggregate` is `"mean"`, `"min"` or `"max"`; `aggregate_period="year"`
  (default) checks one value per year, `"all"` one value over the whole
  selection. `year_start`/`year_end` restrict the years, `hour_start`/`hour_end`
  the time of day, and `min_within_fraction` lets some years fail (e.g. 0.9).
  The values come from the sub-daily output window if
  `output_interval="fluxnet_timestep"` (only those years), else from the daily
  transient output. It rules out
  combinations that push the unobserved variable somewhere implausible,
  without claiming to know its true value. Omit `hour_start`/`hour_end` to apply the
  constraint to whatever resolution you're already using (e.g. the daily
  mean) instead of requiring sub-daily output; just note a daily mean runs
  less negative than a true midday value, so you may need to loosen the
  range accordingly in that case.
- **`ensemble`** — `size` (members per round), `max_rounds` (default 3) and
  `elite_fraction` (default 0.1). Rarely needed: `inflation`,
  `min_spread_fraction`, `explore_fraction`, `min_improvement` (see "The method").
- **`simulation.c_only`** / **`simulation.dynamic_roots`** — the carbon-only
  setup (unlimited N fixation, fixed leaf stoichiometry, prescribed PO4) and
  fixed roots, as in the hand-tuned DE-Hai sweeps (e.g. `72_...`).
- **`simulation.forcing_file_override`** — most FLUXNET3 sites' standard
  forcing stops around 2012; if your observations are more recent, point
  this at a site-specific extended forcing `.dat` file (as several existing
  DE-Hai runscripts already do by hand) instead of the one QPy resolves
  automatically from the site list.
- **`run_mode`** — `"local"` runs the members with a local
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
  by their own max. Set `model_scale=500.0` (`1000 * 0.5`) to reproduce that.
## The method

1. **Round 0** samples `ensemble.size` members over the full ranges (Latin
   hypercube) and runs them as one SLURM array. With `previous_results`
   (results.csv files of earlier calibrations with the same setup), their
   members inside the current ranges are rescored with the current metrics,
   join the elite, and round 0 already samples around them.
2. **Every member evaluates itself.** Right after QUINCY finishes, its SLURM
   task (`src/calibration/member_task.py`) reads the output, computes per
   metric the RMSE, saves the model values at the observation timestamps,
   and deletes the NetCDF output. The reading happens in parallel, so a
   round ends as soon as the last run is done. A member whose output is
   completely flat (a dead plant, e.g. after hydraulic failure) counts as failed.
3. **Score**, over the objectives. Each RMSE is divided by a reference; with
   `score="reference"` (default) that is the spread of the observations
   (`obs_spread_columns`, e.g. between trees) if given, else the metric's
   `sigma`, else the best RMSE any member reached. A ratio below 1 is as good
   as the data can tell and counts as 1; the score is the mean of
   `weight * ratio`, so 1 means every objective is within its reference. The
   search thus improves the metric that is still off without pushing one
   that is already within the observations' precision any further.
   `score="sigma"` always uses sigma; `score="relative"` uses the best RMSE
   reached and takes the largest ratio (1.2 = every objective within 20% of
   its best achievable fit), for when no reference is known.
   Every metric counts on its own, independent of how many observations it
   has. All members are rescored together after every round.
4. **Elite** = the best `elite_fraction x size` members of all rounds so far:
   members passing every constraint first, each group by score.
5. **Next round** samples a multivariate normal fitted to the elite (mean and
   covariance, in log space for log parameters), with its spread inflated by
   `inflation` (1.2) and shrinking at most to `min_spread_fraction` (25%) per
   round. Parameters the data constrain get narrower; ones they don't stay
   wide; and correlated combinations that fit equally well (equifinality) are
   followed instead of cut off. `explore_fraction` (10%) of every round still
   samples the full ranges, as a check that nothing better was missed.
6. Stop after `max_rounds`, or earlier when the elite's mean score improved by
   less than `min_improvement` (1%).

Why rounds instead of one big sample: with 12 parameters, a uniform sample
covers the space very thinly. Halving every range by sampling more would need
2^12 = 4096 times as many runs; concentrating later rounds where the good
members are gets there with a few rounds. A box around the elite does not
work well in 12 dimensions, because the elite's members still spread over
most of every single parameter's range; sampling the fitted distribution
concentrates the members near the good region instead. (The previous
LAVENDAR-style 4D-En-Var method assumed the model responds linearly to the
parameters, which plant hydraulics, with its thresholds and mortality, does
not.)

## Was the fit any good?

Whether a fit is good needs a reference outside the model.
`calibration_verdict.txt` reports for the best member:
- per objective: RMSE (and how far from the best any member reached), bias,
  correlation and NSE (below 0: worse than the observed mean, always POOR),
  and the RMSE against every reference given: your `sigma` and the
  observation spread from `obs_spread_columns` (GOOD within all of them,
  MARGINAL up to 1.5x, POOR above; NO REFERENCE if neither is given);
- per constraint: how many observations are within the tolerance, the mean
  offset and the largest miss (PASS/FAIL);
- parameters whose best members sit at an edge of the allowed range (the
  optimum may lie outside it: widen that range). If it
stopped at `max_rounds` while still improving, raise `max_rounds` and rerun
with `resume=True` and the same `output_root`: finished rounds are loaded,
not rerun.

## Practical notes

- **"error while loading shared libraries"** in a member's `slurm.err`: the
  module stack in `src/quincy/run_scripts/submit.py` is missing something
  QUINCY needs. For `run_mode="local"`, load the modules in the calling shell.
- **Failed members** are listed with their reason after every round (QUINCY
  crashed, no output, flat output, ...). If fewer than
  `min_success_fraction` of a round succeed, the run stops: narrow the ranges.
- **Disk usage.** With `keep_run_outputs=False` (the default) every member
  deletes its NetCDF output (and any `fort.*` Fortran debug files) right after
  scoring; only ~100 kB of series per member are kept for the plots. With
  `keep_best_outputs_fraction=0.2` the complete output of the best 20% of
  every round is kept (listed in `round_XX/kept_outputs.csv`), e.g. to
  analyse how parameters relate to other model variables. Set
  `keep_run_outputs=True` while debugging a new config.
- **Adding a new site** needs nothing beyond a config file, as long as the
  site is in QUINCY's standard FLUXNET3 site list.
