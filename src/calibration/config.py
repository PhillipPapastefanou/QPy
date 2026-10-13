"""User-facing configuration for the QUINCY calibration tool.

A user writes a plain Python config script (same style as the existing QPy
runscripts) that builds a CalibrationConfig describing:
  - which FLUXNET site to run at,
  - which plant-hydraulic parameters to calibrate and their physically
    plausible ranges,
  - which observations to evaluate the model against (one or more metrics),
  - how many members to run per round and how many rounds to allow.

Everything else (namelist/lctlib plumbing, sampling, shrinking the parameter
ranges between rounds, parallel dispatch, plots) is handled by the rest of
this package. See science/phillip/adaptive_calibration/config_example.py for
a fully worked example.
"""
import importlib.util
import math
import os
from dataclasses import dataclass, field
from typing import Optional, List, Tuple


@dataclass
class ParameterSpec:
    # Attribute name as it appears on a QUINCY Lctlib_Item (e.g. "psi50_xylem",
    # "k_xylem_sat", "gamma_stem_max", ...) or, for target=="paramlist", the
    # field name inside the given namelist category (e.g. "gdd_t_air_threshold").
    name: str
    min: Optional[float] = None
    max: Optional[float] = None
    target: str = "lctlib"          # "lctlib" (per-PFT plant param) or "paramlist" (global process param)
    category: Optional[str] = None  # required for target == "paramlist", e.g. "lnd_q_pheno_nml"
    # Set calibrate=False for a parameter you already know -- e.g. from an
    # earlier sensitivity-analysis sweep, like the ones under
    # science/phillip/DE-Hai/runscripts/ -- has little effect on the metrics
    # you're calibrating against. It's then held fixed at `nominal` in every
    # ensemble member instead of being sampled. This shrinks the calibration
    # problem's dimensionality: for the same ensemble.size, the parameters
    # that actually move your metrics get pinned down more tightly instead
    # of ensemble spread being spent on ones that don't matter.
    calibrate: bool = True
    nominal: Optional[float] = None  # required when calibrate=False; ignored (must be unset) otherwise
    # "linear" (default) or "log": for a parameter that naturally spans
    # orders of magnitude (e.g. root_scale: 0.01 .. 2.0, as in the existing
    # hand-tuned DE-Hai sweep scripts, which sample it as
    # log10(root_scale) themselves for exactly this reason), a uniform
    # linear sample over [min, max] wastes almost all of the ensemble on the
    # large end of the range and barely explores the small end. scale="log"
    # makes the sampling and the shrinking of the range between rounds happen
    # in log10 space internally; min/max/nominal are still given (and reported
    # back, e.g. in best_parameters.py) in the parameter's normal,
    # natural units -- the log/linear(10**x) conversion is invisible outside
    # this class. Requires min (or nominal, if calibrate=False) to be > 0.
    scale: str = "linear"

    def __post_init__(self):
        if self.target not in ("lctlib", "paramlist"):
            raise ValueError(f"Parameter '{self.name}': target must be 'lctlib' or 'paramlist', got {self.target!r}")
        if self.target == "paramlist" and not self.category:
            raise ValueError(f"Parameter '{self.name}': target=='paramlist' requires 'category' (e.g. 'lnd_q_pheno_nml')")
        if self.scale not in ("linear", "log"):
            raise ValueError(f"Parameter '{self.name}': scale must be 'linear' or 'log', got {self.scale!r}")

        if self.calibrate:
            if self.min is None or self.max is None:
                raise ValueError(f"Parameter '{self.name}': calibrate=True (the default) requires 'min' and 'max'")
            if self.max <= self.min:
                raise ValueError(f"Parameter '{self.name}': max ({self.max}) must be > min ({self.min})")
            if self.scale == "log" and self.min <= 0:
                raise ValueError(f"Parameter '{self.name}': scale='log' requires min > 0 (got {self.min})")
            if self.nominal is not None:
                raise ValueError(
                    f"Parameter '{self.name}': 'nominal' is only used when calibrate=False -- drop it, "
                    "or set calibrate=False to fix this parameter instead of calibrating it."
                )
        else:
            if self.nominal is None:
                raise ValueError(f"Parameter '{self.name}': calibrate=False requires 'nominal' (the fixed value to use)")
            if self.min is not None or self.max is not None:
                raise ValueError(
                    f"Parameter '{self.name}': calibrate=False fixes the parameter at 'nominal' and ignores "
                    "min/max -- drop them, or set calibrate=True to calibrate this parameter instead."
                )

    def to_internal(self, value: float) -> float:
        """Natural units -> the space the parameter is sampled in
        (log10 for scale=='log', unchanged otherwise)."""
        return math.log10(value) if self.scale == "log" else value

    def from_internal(self, value: float) -> float:
        """Inverse of to_internal -- back to natural units, e.g. before
        writing into lctlib/paramlist or reporting a result to the user."""
        return 10.0 ** value if self.scale == "log" else value

    @property
    def internal_min(self) -> Optional[float]:
        return self.to_internal(self.min) if self.min is not None else None

    @property
    def internal_max(self) -> Optional[float]:
        return self.to_internal(self.max) if self.max is not None else None


_RANGE_TARGET_COLUMN = "_target_"


@dataclass
class MetricSpec:
    # Free-form label used in diagnostics/output tables.
    name: str
    # QUINCY output category (as in the *_<identifier>_<timeres>.nc filenames), e.g. "PHYD", "Q_ASSIMI", "SPQ".
    category: str
    # Model output variable within that category, e.g. "psi_stem_avg", "gpp_avg", "G_avg".
    variable: str
    # --- Mode 1: a real observation stream (set obs_file) ---
    # CSV file with a datetime index column plus the observation column.
    obs_file: Optional[str] = None
    obs_column: Optional[str] = None
    obs_index_col: str = "date"
    # What the metric does in the calibration:
    # "objective": the search tries to fit it as well as possible (its RMSE
    #   enters the score). For densely observed variables (psi_stem, sap flow).
    # "constraint": a ballpark check. Every observation must lie within
    #   +-tolerance of the model; members that pass all constraints are ranked
    #   ahead of all others, but the metric does not pull the fit any further.
    #   For sparse observations (a few psi_leaf dates) or plausibility ranges.
    # Default: "constraint" for target_min/target_max, "objective" otherwise.
    role: Optional[str] = None
    # constraint only: allowed |model - obs| per observation, in the variable's
    # units (for target_min/target_max: half the range, set automatically).
    tolerance: Optional[float] = None
    # constraint only: fraction of the observations that must be within the
    # tolerance, e.g. 5/6 to allow one outlier date.
    min_within_fraction: float = 1.0
    # Optional error you would accept (absolute, or relative to the mean |obs|),
    # for objectives. Used by the search if there is no obs_spread_columns
    # (score="reference") or always (score="sigma"); if given,
    # the verdict and accepted_parameters.csv check the RMSE against it.
    sigma: Optional[float] = None
    relative_sigma: Optional[float] = None
    # Optional: two columns of obs_file holding quantiles of the observations
    # across replicates (e.g. trees), and which quantiles they are. Their
    # spread gives the natural variability of the observations, which the
    # verdict compares the RMSE with, e.g. ("FAG_025", "FAG_075") and (0.25, 0.75).
    obs_spread_columns: Optional[Tuple[str, str]] = None
    obs_spread_quantiles: Tuple[float, float] = (0.25, 0.75)
    # If true, negative observation values are clipped to 0 before use --
    # matching the convention the existing DE-Hai analysis scripts
    # (post_process_complete_single.py, EGU_plot_base.py, T24_plot_output.py)
    # already apply to sap-flow J0.5 (a physically non-negative quantity
    # whose sensor readings dip slightly below 0 from noise, e.g. at night).
    clip_negative_obs_to_zero: bool = False
    # Hours added to the observation timestamps, to correct a time offset
    # between logger and model time. E.g. DE-Hai sap flow needs +2 (see
    # science/phillip/DE-Hai/input/sapflow/sapflow_2024-2025_timefix.ipynb,
    # which made Sapflow2023-2024_offset.csv for the Julia analysis).
    obs_time_shift_hours: float = 0.0
    # Multiply the model's raw value by this factor before any comparison
    # -- for a unit conversion and/or an empirically chosen correction factor.
    # E.g. DE-Hai's sap-flow analysis
    # (src/postprocessing/julia/core/qcomparer_2023.jl,
    # calculate_mod_obs_rmse_2023) compares QUINCY's *_per_sap_area_avg
    # outputs against observed sap-flow flux density at x1000 (unit
    # conversion) times a candidate correction factor (1, 0.5, 0.25, or 2 --
    # 'stem_flow_rmse_05' is the model_scale=1000*0.5=500 case).
    model_scale: float = 1.0
    # --- Mode 2: a soft plausibility range instead of real data (set target_min/target_max) ---
    # Use this when you don't have observations for a variable but still know,
    # from domain knowledge, roughly what range it should stay in -- e.g. "midday
    # leaf water potential should be between -2.5 and -0.3 MPa". This is scored
    # like a real metric against a pseudo-observation centred on the range's
    # midpoint, so it nudges the fit away from physically
    # implausible parameter combinations even when GPP/ET alone can't rule
    # them out (equifinality). Requires both target_min and target_max.
    target_min: Optional[float] = None
    target_max: Optional[float] = None
    # How "hard" the range's edges are, in standard deviations from the
    # midpoint: sigma = (target_max - target_min) / (2 * range_confidence_sigma).
    # Larger values = a stricter constraint (values near the edge are
    # considered less plausible) for the same min/max. Default 2.0 treats
    # min/max as roughly a 95% plausible interval, not a hard wall -- the
    # calibration can still push slightly outside it if GPP/ET strongly
    # demand it.
    range_confidence_sigma: float = 2.0
    # Only meaningful for sub-daily output (simulation.output_interval ==
    # "fluxnet_timestep"): restrict the constraint to local hours in
    # [hour_start, hour_end] inclusive, e.g. [11, 13] for "midday". If
    # omitted, the constraint applies to every available timestep/day, which
    # for daily output effectively compares against the *daily mean* rather
    # than a true midday value -- usually fine as a coarse plausibility
    # check, but be aware daily means run less negative than true midday
    # values, so you may want to loosen target_min/target_max accordingly.
    hour_start: Optional[int] = None
    hour_end: Optional[int] = None
    # Range metrics only: restrict to these months (1-12), e.g. [8] for
    # August, and/or to the years year_start..year_end (inclusive).
    months: Optional[List[int]] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    # Range metrics only: instead of every model value, check one aggregate
    # ("mean", "min" or "max") per aggregate_period ("year": one value per
    # year of the selected months/hours; "all": one value over the whole
    # selection). E.g. months=[8], aggregate="mean": every year's August mean
    # must lie in [target_min, target_max] (min_within_fraction of the years).
    aggregate: Optional[str] = None
    aggregate_period: str = "year"
    # objective only: the metric's ratio is multiplied by this in the score,
    # weight 2 = the metric has to be twice as close to its reference.
    weight: float = 1.0

    def __post_init__(self):
        is_obs = self.obs_file is not None
        is_range = self.target_min is not None or self.target_max is not None

        if is_obs and is_range:
            raise ValueError(
                f"Metric '{self.name}': set either obs_file (real observations) or "
                "target_min/target_max (a soft plausibility range), not both."
            )
        if not is_obs and not is_range:
            raise ValueError(
                f"Metric '{self.name}': must set either obs_file (real observations) or "
                "target_min/target_max (a soft plausibility range)."
            )

        if is_obs:
            if self.obs_column is None:
                raise ValueError(f"Metric '{self.name}': obs_file requires obs_column")
            if (self.months, self.year_start, self.year_end, self.aggregate) != (None,) * 4:
                raise ValueError(f"Metric '{self.name}': months/year_start/year_end/aggregate are only "
                                 "for target_min/target_max metrics")
            if self.sigma is not None and self.relative_sigma is not None:
                raise ValueError(f"Metric '{self.name}': set 'sigma' or 'relative_sigma', not both")
        else:
            if self.target_min is None or self.target_max is None:
                raise ValueError(f"Metric '{self.name}': range constraint requires both target_min and target_max")
            if self.target_max <= self.target_min:
                raise ValueError(
                    f"Metric '{self.name}': target_max ({self.target_max}) must be > "
                    f"target_min ({self.target_min})")
            if self.range_confidence_sigma <= 0:
                raise ValueError(f"Metric '{self.name}': range_confidence_sigma must be > 0")
            if (self.hour_start is None) != (self.hour_end is None):
                raise ValueError(f"Metric '{self.name}': set both hour_start and hour_end, or neither")
            if self.months is not None and not all(1 <= mo <= 12 for mo in self.months):
                raise ValueError(f"Metric '{self.name}': months must be between 1 and 12")
            if self.aggregate not in (None, "mean", "min", "max"):
                raise ValueError(f"Metric '{self.name}': aggregate must be 'mean', 'min' or 'max'")
            if self.aggregate_period not in ("year", "all"):
                raise ValueError(f"Metric '{self.name}': aggregate_period must be 'year' or 'all'")
            if self.clip_negative_obs_to_zero:
                raise ValueError(
                    f"Metric '{self.name}': clip_negative_obs_to_zero applies to real observations, "
                    "not a range constraint's synthesized pseudo-observation")
            if self.sigma is not None or self.relative_sigma is not None:
                raise ValueError(
                    f"Metric '{self.name}': sigma/relative_sigma are derived automatically from "
                    "target_min/target_max/range_confidence_sigma for a range constraint; don't set them directly."
                )
            # Synthesize the pseudo-observation the rest of the pipeline reads
            # through exactly the same obs_column/sigma fields as a real metric.
            self.obs_column = _RANGE_TARGET_COLUMN
            self.sigma = (self.target_max - self.target_min) / (2.0 * self.range_confidence_sigma)
            if self.tolerance is None:
                self.tolerance = 0.5 * (self.target_max - self.target_min)

        if self.role is None:
            self.role = "objective" if is_obs else "constraint"
        if self.role not in ("objective", "constraint"):
            raise ValueError(f"Metric '{self.name}': role must be 'objective' or 'constraint'")
        if self.role == "constraint" and (self.tolerance is None or self.tolerance <= 0):
            raise ValueError(f"Metric '{self.name}': a constraint needs a tolerance > 0 "
                             "(allowed |model - obs| per observation)")
        if not 0 < self.min_within_fraction <= 1:
            raise ValueError(f"Metric '{self.name}': min_within_fraction must be in (0, 1]")
        if self.obs_spread_columns is not None:
            if not is_obs:
                raise ValueError(f"Metric '{self.name}': obs_spread_columns needs an obs_file")
            q_lo, q_hi = self.obs_spread_quantiles
            if not 0 < q_lo < q_hi < 1:
                raise ValueError(f"Metric '{self.name}': obs_spread_quantiles must satisfy 0 < low < high < 1")

        if self.weight <= 0:
            raise ValueError(f"Metric '{self.name}': weight must be > 0")
        if self.model_scale <= 0:
            raise ValueError(f"Metric '{self.name}': model_scale must be > 0")

    @property
    def is_range_constraint(self) -> bool:
        return self.obs_file is None


@dataclass
class EnsembleSpec:
    # Members run per round (also the SLURM array size).
    size: int = 150
    # Round 0 samples the full parameter ranges; every later round samples
    # around the best members found so far.
    max_rounds: int = 3
    # The best fraction of a round's size, out of all members run so far
    # ("elite"), defines the next round's sampling distribution and the
    # elite band in the plots.
    elite_fraction: float = 0.1
    # The next round samples a multivariate normal fitted to the elite (mean
    # and covariance, in log space for scale="log"). Its spread is inflated by
    # this factor, so the region around the elite is still explored.
    inflation: float = 1.2
    # A parameter's spread shrinks at most to this fraction of its previous
    # spread per round, so the search can't collapse onto a few lucky members.
    min_spread_fraction: float = 0.25
    # Fraction of every later round still sampled over the full original
    # ranges, as a check that the search didn't miss a better region.
    explore_fraction: float = 0.1
    # Stop early when the mean score of the elite improved by less than this
    # (relative) in the last round.
    min_improvement: float = 0.01
    seed: int = 42
    # Minimum fraction of a round's members that must finish successfully;
    # below this the run aborts with guidance to narrow parameter ranges.
    min_success_fraction: float = 0.3

    def __post_init__(self):
        if not 0 < self.elite_fraction < 1:
            raise ValueError("EnsembleSpec: elite_fraction must be between 0 and 1")
        if not 0 < self.min_spread_fraction <= 1:
            raise ValueError("EnsembleSpec: min_spread_fraction must be in (0, 1]")
        if self.inflation < 1:
            raise ValueError("EnsembleSpec: inflation must be >= 1")
        if not 0 <= self.explore_fraction < 1:
            raise ValueError("EnsembleSpec: explore_fraction must be in [0, 1)")
        if self.max_rounds < 1:
            raise ValueError("EnsembleSpec: max_rounds must be >= 1")


@dataclass
class SimulationSpec:
    forcing_dataset: str = "FLUXNET3"
    # spinup_start_year MUST equal the first calendar year present in the
    # forcing file (QUINCY hard-errors otherwise: "First year read from the
    # forcing file (...) not equal to start year of transient spinup
    # simulation"), and transient_start_year MUST equal spinup_start_year --
    # violating the latter doesn't error, it silently corrupts the *output*
    # netCDF time coordinate (left at the fill value) while everything else
    # keeps running, which is much harder to notice. Both are 1901 for
    # QUINCY's standard FLUXNET3 forcing and the DE-Hai extended forcing
    # file alike; don't try to "fast-forward" a calibration run by starting
    # the transient run partway through -- shorten simulation_length_years
    # (and/or spinup_years) instead.
    spinup_start_year: int = 1901
    spinup_end_year: int = 1930
    spinup_years: int = 30
    transient_start_year: int = 1901
    simulation_length_years: int = 20
    output_start_first_day_year: int = 1
    output_end_last_day_year: int = 20
    # "daily" (matches daily-mean obs like most GPP/LE/LAI products; this is
    # the well-tested path -- see README) or "fluxnet_timestep", an
    # EXPERIMENTAL attempt at QUINCY's native ~half-hourly output for a
    # trailing sub-window of the transient run (needed for sub-daily
    # observations like stem water potential or sap flow, via
    # fluxnet_forc_start_yr/fluxnet_forc_last_yr below). Plain global
    # timestep output was tried first and rejected: in the QUINCY build this
    # was developed against, the ordinary "transient_*_timestep.nc" writer
    # leaves its time coordinate completely unpopulated. The dedicated
    # fluxnet-timestep writer is the mechanism the existing DE-Hai scripts
    # rely on for exactly this, but during development it did not reliably
    # populate real timestamps either in the configurations tried here --
    # inspect the resulting *_timestep.nc / *_daily.nc files' `time`
    # coordinate for all-fill-value before trusting a calibration run that
    # uses it.
    output_interval: str = "daily"
    # Only used when output_interval == "fluxnet_timestep": the trailing
    # calendar-year window (within transient_start_year ..
    # transient_start_year+simulation_length_years-1) that gets switched to
    # half-hourly output.
    fluxnet_forc_start_yr: Optional[int] = None
    fluxnet_forc_last_yr: Optional[int] = None
    use_plant_hydraulics: bool = True
    use_hydraulic_failure_mort: bool = False
    # Carbon-only setup as in the hand-tuned DE-Hai sweeps: unlimited N fixation
    # (vegetation and soil), fixed leaf stoichiometry and prescribed soil PO4
    c_only: bool = False
    # Roots across soil layers: dynamic over time (True) or fixed after init (False)
    dynamic_roots: bool = True
    # QUINCY's standard FLUXNET3 site-list forcing files stop around 2012 for
    # most sites. If your observations are more recent (e.g. 2020s sap-flow
    # or psi_stem campaigns), point this at a site-specific extended forcing
    # file (.dat, same format QPy already uses) to override the one
    # EnvironmentalInputSite resolves automatically -- exactly what several
    # of the existing DE-Hai runscripts do by hand.
    forcing_file_override: Optional[str] = None
    # Override the site's default soil texture (jsb_sse_nml.qs_soil_sand/
    # qs_soil_silt; clay is derived as 1 - sand - silt), e.g. to match a
    # value a previous hand-tuned sweep for this site already settled on.
    # Set both together, or neither (leave the site-level default as-is).
    soil_sand: Optional[float] = None
    soil_silt: Optional[float] = None

    def __post_init__(self):
        if (self.soil_sand is None) != (self.soil_silt is None):
            raise ValueError("SimulationSpec: set both soil_sand and soil_silt, or neither")
        if self.soil_sand is not None and self.soil_sand + self.soil_silt >= 1.0:
            raise ValueError(
                f"SimulationSpec: soil_sand + soil_silt ({self.soil_sand + self.soil_silt}) must be < 1 "
                "(the remainder becomes clay)")
        if self.transient_start_year != self.spinup_start_year:
            raise ValueError(
                f"transient_start_year ({self.transient_start_year}) must equal "
                f"spinup_start_year ({self.spinup_start_year}). QUINCY does not error on a "
                "mismatch here -- it silently leaves the output netCDF time coordinate "
                "unpopulated instead, which then fails much later, confusingly, when merging "
                "against observations. Don't try to shorten a run by starting the transient "
                "phase partway through the forcing record; shorten simulation_length_years "
                "and/or spinup_years instead."
            )
        if self.output_interval not in ("daily", "fluxnet_timestep"):
            raise ValueError(
                f"output_interval must be 'daily' or 'fluxnet_timestep', got {self.output_interval!r}")
        if self.output_interval == "fluxnet_timestep":
            if self.fluxnet_forc_start_yr is None or self.fluxnet_forc_last_yr is None:
                raise ValueError(
                    "output_interval == 'fluxnet_timestep' requires both fluxnet_forc_start_yr "
                    "and fluxnet_forc_last_yr (the trailing sub-window to switch to half-hourly output)."
                )
            if self.fluxnet_forc_last_yr < self.fluxnet_forc_start_yr:
                raise ValueError("fluxnet_forc_last_yr must be >= fluxnet_forc_start_yr")


@dataclass
class CalibrationConfig:
    site: str
    output_root: str
    parameters: List[ParameterSpec]
    metrics: List[MetricSpec]
    ensemble: EnsembleSpec = field(default_factory=EnsembleSpec)
    simulation: SimulationSpec = field(default_factory=SimulationSpec)
    # "local" (multiprocessing on this machine) or "slurm_array" (one SLURM
    # array task per ensemble member, blocking via `sbatch --wait`).
    run_mode: str = "local"
    # local: size of the multiprocessing pool. slurm_array: max concurrently
    # running array tasks (SLURM '%' throttle).
    n_parallel: int = 150
    # slurm_array only: per-task SLURM resource request. A single QUINCY
    # run needs only a few GB, so these default well below
    # GenerateSlurmScriptArrayBased's own 300GB/'work' default -- matching
    # what the existing hand-written DE-Hai sweep scripts request per task.
    slurm_ram_in_gb: int = 4
    slurm_partition: str = "small,work"
    # Optional explicit path to a QUINCY checkout; if omitted, QuincyPathFinder
    # is used (QUINCY env var, cached local/paths.json, or auto-discovery).
    quincy_root: Optional[str] = None
    # If false (default), each member deletes its NetCDF output right after
    # its metrics have been computed (inside the SLURM task). The model
    # values at the observation timestamps are always kept for the plots.
    keep_run_outputs: bool = False
    # Keep the complete NetCDF output of the best this fraction of every
    # round (e.g. 0.2), for later analysis; the rest is deleted when the round
    # has been scored. Listed in round_XX/kept_outputs.csv.
    keep_best_outputs_fraction: float = 0.0
    # If True, rounds that already finished in output_root are loaded instead
    # of run again, e.g. to add a round after raising ensemble.max_rounds.
    resume: bool = False
    # How the objectives of a member combine into one score (lower is better).
    # Each objective's RMSE is divided by a reference:
    # "reference": the spread of the observations (obs_spread_columns) if
    #   given, else its sigma, else the best RMSE any member reached.
    # "sigma": the metric's sigma.
    # For these two, a ratio below 1 is as good as the data can tell and counts
    # as 1; the score is the mean of weight * ratio over the objectives, so 1
    # means every objective is within its reference.
    # "relative": the best RMSE any member reached for that metric so far; the
    #   score is the largest weight * ratio, so 1.2 means every objective is
    #   within 20% of its best achievable fit.
    # Members that fail a constraint are always ranked behind those that pass.
    score: str = "reference"
    # results.csv files of earlier calibrations with the same setup (site,
    # forcing, fixed parameters, metrics). Their successful members inside the
    # current ranges are rescored and count for the elite, so round 0 samples
    # around them instead of the full ranges.
    previous_results: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.output_root = os.path.abspath(self.output_root)
        if self.run_mode not in ("local", "slurm_array"):
            raise ValueError(f"run_mode must be 'local' or 'slurm_array', got {self.run_mode!r}")
        if not 0 <= self.keep_best_outputs_fraction <= 1:
            raise ValueError("keep_best_outputs_fraction must be between 0 and 1")
        if self.score not in ("reference", "sigma", "relative"):
            raise ValueError(f"score must be 'reference', 'sigma' or 'relative', got {self.score!r}")
        objectives = [m for m in self.metrics if m.role == "objective"]
        if not objectives:
            raise ValueError("At least one metric must have role='objective'.")
        if self.score == "sigma":
            missing = [m.name for m in objectives if m.sigma is None and m.relative_sigma is None]
            if missing:
                raise ValueError(f"score='sigma' needs sigma or relative_sigma for: {', '.join(missing)}")
        self.previous_results = [os.path.abspath(p) for p in self.previous_results]
        if not any(p.calibrate for p in self.parameters):
            raise ValueError("At least one parameter must have calibrate=True (all of them are fixed).")
        for m in self.metrics:
            if m.hour_start is not None and self.simulation.output_interval != "fluxnet_timestep":
                raise ValueError(
                    f"Metric '{m.name}' sets hour_start/hour_end (e.g. for a midday constraint), "
                    "which needs sub-daily output. Set simulation.output_interval: 'fluxnet_timestep' "
                    "(with fluxnet_forc_start_yr/fluxnet_forc_last_yr), or drop hour_start/hour_end to "
                    "apply the constraint to whatever resolution you're already using."
                )

    @staticmethod
    def from_pyfile(path: str) -> "CalibrationConfig":
        """Load a config from a plain Python script (see config_example.py):
        the script builds a CalibrationConfig and assigns it to a
        module-level variable named `config`, exactly like any other QPy
        runscript builds up a Quincy_Setup."""
        path = os.path.abspath(path)
        spec = importlib.util.spec_from_file_location("calibration_user_config", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not hasattr(module, "config"):
            raise ValueError(f"{path} must define a module-level variable named 'config' (a CalibrationConfig instance)")
        config = module.config
        if not isinstance(config, CalibrationConfig):
            raise TypeError(f"{path}: 'config' must be a CalibrationConfig instance, got {type(config)}")
        return config
