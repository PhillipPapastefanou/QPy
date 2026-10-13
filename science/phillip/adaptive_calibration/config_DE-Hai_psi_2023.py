# Calibration config for DE-Hai, evaluated against 2023 psi_stem,
# sap flow, and psi_leaf (midday) observations. Sub-daily model output
# covers 2023-2024 (2024 included for plotting, even though the metrics
# below are the 2023 obs files).
#
# Parameter space, forcing file and model setup (C only, fixed roots) taken from
# the most recent hand-tuned sensitivity sweep for this site:
# science/phillip/DE-Hai/runscripts/2023_HAI_runscripts/72_run_transient_3days_new_mort_new_phen_fix.py
# Every parameter that sweep varied (min != max) is calibrated here, with the
# k_latosa range deliberately widened; every one it held constant is
# fixed here via calibrate=False instead.
#
# Run with:  python run_calibration.py config_DE-Hai_psi_2023.py
#
# run_mode="slurm_array" is required at this ensemble size (512): every
# member is one SLURM array task that loads the module stack QUINCY needs,
# runs the model and computes its own metrics.

from src.calibration.config import (
    CalibrationConfig,
    EnsembleSpec,
    MetricSpec,
    ParameterSpec,
    SimulationSpec,
)

simulation = SimulationSpec(
    forcing_dataset="FLUXNET3",
    spinup_start_year=1901,
    spinup_end_year=1930,
    spinup_years=300,  # as in the 72_... sweep
    transient_start_year=1901,
    simulation_length_years=124,  # 1901 .. 2024
    output_start_first_day_year=1,
    output_end_last_day_year=124,
    # psi_stem/sap_flow/psi_leaf are all sub-daily: switch 2023-2024 to
    # half-hourly output (2024 included too, on top of what the metrics
    # below need, so the resulting NetCDFs can be plotted/inspected over
    # both years -- psi_leaf_midday_2023_2024_avg.csv's 2024 rows will
    # now also merge in automatically).
    output_interval="fluxnet_timestep",
    fluxnet_forc_start_yr=2023,
    fluxnet_forc_last_yr=2024,
    # Standard FLUXNET3 forcing for DE-Hai only covers 1901-2012; point at
    # the site's extended forcing file (as the 72_... script also does) so
    # the transient run actually reaches 2023.
    forcing_file_override="/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/QUINCY_DE-Hai_1901_2024.dat",
    use_plant_hydraulics=True,
    use_hydraulic_failure_mort=True,
    # C-only setup and fixed roots, as in the 72_... sweep
    c_only=True,
    dynamic_roots=False,
    # Fixed soil texture from the 72_... sweep (sand=0.25, silt=0.38 ->
    # clay=0.37), rather than whatever EnvironmentalInputSite resolves by
    # default for the site.
    soil_sand=0.25,
    soil_silt=0.38,
)

# Up to 5 rounds of 512, from scratch (round 0 samples the full ranges); it
# stops earlier once the elite improves by less than 1% per round. A round
# takes ~1 h whatever its size, as all members run at once; the elite (best
# 52 members of all runs so far) is large enough to fit the 12-parameter
# distribution.
ensemble = EnsembleSpec(
    size=512,
    max_rounds=5,
    elite_fraction=0.1,
    seed=42,
    min_success_fraction=0.3,
)

# --- Calibrated parameters (72_...'s ranges where min != max) ---
parameters = [
    ParameterSpec(name="k_xylem_sat", min=0.7, max=2.5),
    ParameterSpec(name="gamma_stem_max", min=70, max=200),
    ParameterSpec(name="psi50_stem_tlp", min=-2.5, max=-2.3),
    ParameterSpec(name="gamma_leaf", min=0.03, max=0.04),
    ParameterSpec(name="k_latosa", min=2000, max=8000),
    ParameterSpec(name="g1_medlyn", min=3.5, max=4.2),
    ParameterSpec(name="g0", min=0.002, max=0.003),
    ParameterSpec(name="g_res", min=0.0003, max=0.0006),
    ParameterSpec(name="psi_leaf_threshold", min=-4.5, max=-3.5),
    ParameterSpec(name="psi50_leaf_close", min=-1.5, max=-1.0),
    ParameterSpec(name="k_root_dist", min=4.0, max=6.0),
    # root_scale spans 20 .. 120 (6x): log-scaled, as requested and as the
    # 72_... sweep itself already samples it (root_scale_log).
    ParameterSpec(name="root_scale", min=20.0, max=120.0, scale="log"),

    # --- Fixed parameters: min == max in 72_..., or hardcoded there outside
    # the sampled set entirely. Held at that same constant value here.
    ParameterSpec(name="gamma_stem_res", calibrate=False, nominal=30.0),
    ParameterSpec(name="slope_leaf_close", calibrate=False, nominal=2.5),
    ParameterSpec(name="slope_stem_tlp", calibrate=False, nominal=10.0),
    ParameterSpec(name="gmin", calibrate=False, nominal=0.00001),
    ParameterSpec(name="psi50_xylem", calibrate=False, nominal=-3.8),
    ParameterSpec(name="vmax_uptake_p", calibrate=False, nominal=0.012),
    ParameterSpec(name="gdd_req_max", calibrate=False, nominal=425.0),
    ParameterSpec(name="k_gdd_dormance", calibrate=False, nominal=0.016),
    ParameterSpec(name="k_rtos", calibrate=False, nominal=4.0),
    ParameterSpec(
        name="gdd_t_air_threshold", target="paramlist", category="lnd_q_pheno_nml",
        calibrate=False, nominal=8.0,
    ),
]

# --- Metrics: 2023 psi_stem, sap flow, and psi_leaf (midday) ---
# psi_stem and sap flow are objectives: the search scores a member by the
# worse of their RMSEs relative to the spread between trees (score="reference"),
# so no weighting between them is needed and neither is pushed below the
# precision of the data.
# psi_leaf (6 dates) is a ballpark constraint: 5 of 6 dates within +-0.5 MPa.
# The quantile columns give the spread between trees (used by the search and
# the verdict); sigma = the acceptance thresholds of the 72_... analysis
# (DE-Hai/post/julia/multi/qs_hydro_selector_23_indexes.jl), only used to
# judge the fit (verdict, accepted_parameters.csv).
metrics = [
    MetricSpec(
        name="psi_stem",
        category="PHYD",
        variable="psi_stem_avg",
        obs_file="/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed/PsiStem2023.csv",
        obs_column="FAG",
        sigma=0.115,
        obs_spread_columns=("FAG_025", "FAG_075"),
        obs_spread_quantiles=(0.25, 0.75),
    ),
    MetricSpec(
        name="sapflow",
        category="PHYD",
        # G_per_sap_area_avg x1000 (unit conversion) x0.5 (empirical
        # correction), matching "G_rmse_05" in the existing Julia analysis
        # (src/postprocessing/julia/core/qcomparer_2023.jl,
        # calculate_mod_obs_rmse_2023) -- found to be the better-matching of
        # the two candidate model variables (vs. stem_flow_per_sap_area_avg)
        # and the 0.5x scaling (vs. 1x/0.25x/2x) tried there against J0.5.
        variable="G_per_sap_area_avg",
        model_scale=500.0,  # 1000 * 0.5
        obs_file="/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed/Sapflow2023.csv",
        obs_column="J0.5",
        sigma=6.85,
        obs_spread_columns=("J0.25", "J0.75"),
        obs_spread_quantiles=(0.25, 0.75),
        clip_negative_obs_to_zero=True,
        # The logger time is 2 h behind model time; same correction as
        # Sapflow2023-2024_offset.csv used by the Julia analysis
        # (DE-Hai/input/sapflow/sapflow_2024-2025_timefix.ipynb)
        obs_time_shift_hours=2.0,
    ),
    MetricSpec(
        name="psi_leaf",
        category="PHYD",
        variable="psi_leaf_avg",
        obs_file="/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed/psi_leaf_midday_2023_2024_avg.csv",
        obs_column="psi_leaf_midday_avg",
        role="constraint",
        tolerance=0.5,
        # One outlier date allowed: on 2023-09-18 every run of the earlier
        # calibration was 0.7-1.4 MPa too wet (a model issue, not a parameter one)
        min_within_fraction=5 / 6,
    ),
]

config = CalibrationConfig(
    site="DE-Hai",
    output_root="/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/adaptive_calibration/DE-Hai_psi_2023_rounds_v3",
    run_mode="slurm_array",
    n_parallel=512,
    simulation=simulation,
    ensemble=ensemble,
    parameters=parameters,
    metrics=metrics,
    keep_run_outputs=False,
    # Complete output of the best 20% of every round, for later analysis
    # (round_XX/output/<member>, listed in round_XX/kept_outputs.csv)
    keep_best_outputs_fraction=0.2,
    resume=True,
    # Objectives scored by RMSE / spread between trees (obs_spread_columns
    # above): the search improves psi_stem as far as possible while keeping
    # sap flow within the variability of the observations
    score="reference",
    # No previous_results: the earlier calibrations scored sap flow without
    # the +2 h time correction, so their RMSEs don't apply.
)
