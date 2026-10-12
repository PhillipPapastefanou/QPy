# LAVENDAR calibration config for DE-Hai, evaluated against 2023 psi_stem,
# sap flow, and psi_leaf (midday) observations. Sub-daily model output
# covers 2023-2024 (2024 included for plotting, even though the metrics
# below are the 2023 obs files).
#
# Parameter space and forcing file reproduced from the most recent hand-tuned
# sensitivity sweep for this site:
# science/phillip/DE-Hai/runscripts/2023_HAI_runscripts/72_run_transient_3days_new_mort_new_phen_fix.py
# Every parameter that sweep varied (min != max) is calibrated here with the
# same range; every one it held constant (min == max, or hardcoded outside
# the sampled set) is fixed here via calibrate=False instead, so the
# ensemble spends its effort only on the parameters that actually move.
#
# Run with:  python run_calibration.py config_DE-Hai_psi_2023.py
#
# IMPORTANT: run_mode="slurm_array" is required at this ensemble size (512).
# It dispatches through GenerateSlurmScriptArrayBased, which loads the
# gnu12/mpich/netcdf module stack QUINCY's binary needs on every array task
# -- the same mechanism 72_run_transient_3days_new_mort_new_phen_fix.py's own
# sbatch submission relies on. Local multiprocessing has no such guarantee
# (it just inherits whatever modules happen to already be loaded in the
# calling shell) and also isn't practical at 512-way parallelism on a single
# 64-core node.

from qpy_calibrate.config import (
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
    spinup_years=30,
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
    # Fixed soil texture from the 72_... sweep (sand=0.25, silt=0.38 ->
    # clay=0.37), rather than whatever EnvironmentalInputSite resolves by
    # default for the site.
    soil_sand=0.25,
    soil_silt=0.38,
)

ensemble = EnsembleSpec(
    size=512,
    max_iterations=4,
    convergence_tol=0.02,
    seed=42,
    inflation=1.15,
    run_gradient_check=True,
    min_success_fraction=0.3,
)

# --- Calibrated parameters (72_...'s ranges where min != max) ---
parameters = [
    ParameterSpec(name="k_xylem_sat", min=0.7, max=2.5),
    ParameterSpec(name="gamma_stem_max", min=70, max=200),
    ParameterSpec(name="psi50_stem_tlp", min=-2.5, max=-2.3),
    ParameterSpec(name="gamma_leaf", min=0.03, max=0.04),
    ParameterSpec(name="k_latosa", min=3000, max=8000),
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
metrics = [
    MetricSpec(
        name="psi_stem",
        category="PHYD",
        variable="psi_stem_avg",
        obs_file="/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed/PsiStem2023.csv",
        obs_column="FAG",
        sigma=0.3,
        weight=1.0,
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
        relative_sigma=0.25,
        weight=0.5,
        clip_negative_obs_to_zero=True,
    ),
    MetricSpec(
        name="psi_leaf",
        category="PHYD",
        variable="psi_leaf_avg",
        obs_file="/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed/psi_leaf_midday_2023_2024_avg.csv",
        obs_column="psi_leaf_midday_avg",
        sigma=0.3,
        weight=1.0,
    ),
]

config = CalibrationConfig(
    site="DE-Hai",
    output_root="/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/lavendar_calibration/DE-Hai_psi_2023",
    run_mode="slurm_array",
    n_parallel=512,
    simulation=simulation,
    ensemble=ensemble,
    parameters=parameters,
    metrics=metrics,
    keep_run_outputs=False,
    resume=True,
)
