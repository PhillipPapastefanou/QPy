# Example LAVENDAR-style calibration config for the DE-Hai FLUXNET3 site,
# written the same way as any other QPy runscript: build up the objects in
# plain Python and assign the result to `config`. Parameter ranges below are
# taken from the existing hand-tuned sweep in
# science/phillip/DE-Hai/runscripts/2024_HAI_runscripts/
# 61_run_transient_slurm_array_mort_hyd_fail_mort_g1.py, and the observation
# files are the ones already used in science/phillip/DE-Hai/bench/
# post_process_complete_single.py. Copy this file per site/user and edit the
# site name, ranges, and obs file paths.
#
# Run with:  python run_calibration.py my_config.py

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
    # All metrics below (psi_stem, sap flow, GPP, psi_leaf_midday) are
    # sub-daily or need an hour-of-day filter, so we switch the trailing
    # fluxnet_forc_start_yr..fluxnet_forc_last_yr window (2000-2024, matching
    # the observation files) to half-hourly output; output_start/end_
    # first_day_year above are ignored by QUINCY once this mode is on. This
    # leaves a 99-year (1901-1999) ordinary daily-output lead-in, which
    # QUINCY's timestep-output switch requires to be non-empty.
    output_interval="fluxnet_timestep",
    fluxnet_forc_start_yr=2000,
    fluxnet_forc_last_yr=2024,
    # DE-Hai's standard FLUXNET3 forcing only covers 1901-2012; the psi_stem/
    # sap-flow/2023-2024 GPP observations below need forcing through 2024, so
    # (as in the existing DE-Hai runscripts) we point at the site's extended
    # forcing file instead of the one auto-resolved from the site list.
    forcing_file_override="/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/QUINCY_DE-Hai_1901_2024.dat",
    use_plant_hydraulics=True,
    use_hydraulic_failure_mort=False,
)

ensemble = EnsembleSpec(
    size=150,
    max_iterations=4,
    convergence_tol=0.02,
    seed=42,
    inflation=1.15,
    run_gradient_check=True,
    min_success_fraction=0.3,
)

# Plant-hydraulic parameters to calibrate (target="lctlib" -> per-PFT field on
# the QUINCY Lctlib_Item; see src/quincy/base/Lctlib.py for the full list of
# valid names).
parameters = [
    ParameterSpec(name="k_xylem_sat", min=0.25, max=5.0),
    ParameterSpec(name="gamma_stem_max", min=100, max=210),
    ParameterSpec(name="gamma_stem_res", min=15, max=40),
    ParameterSpec(name="psi50_stem_tlp", min=-2.3, max=-1.8),
    ParameterSpec(name="psi50_leaf_close", min=-1.8, max=-0.6),
    ParameterSpec(name="k_latosa", min=2000, max=6000),
    ParameterSpec(name="g1_medlyn", min=3.5, max=4.5),
    # g0's range in the earlier sensitivity sweep was already tiny
    # (0.0024-0.0026) -- known to barely move GPP/ET at this site, so it's
    # fixed at its midpoint here instead of spending ensemble spread on it.
    # Flip to ParameterSpec(name="g0", min=..., max=...) to calibrate it too.
    ParameterSpec(name="g0", calibrate=False, nominal=0.0025),
    # root_scale spans two orders of magnitude (0.01 .. 2.0); the earlier
    # hand-tuned sweep script already samples it as log10(root_scale) for
    # exactly this reason (a linear draw would barely explore the small
    # end). scale="log" does that automatically -- min/max/the reported
    # result all stay in natural units, only the internal sampling is log10.
    ParameterSpec(name="root_scale", min=0.01, max=2.0, scale="log"),
    ParameterSpec(name="k_root_dist", min=2.5, max=5.5),
]

# Evaluation metrics: any number of them, each compared against its own
# observation CSV. RMSE per metric is what feeds the 4D-En-Var cost
# function; 'sigma'/'relative_sigma' encode how much you trust each
# observation stream, and 'weight' lets you tune the balance between them.
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
        # correction), matching "G_rmse_05" in the existing DE-Hai Julia
        # analysis (src/postprocessing/julia/core/qcomparer_2023.jl,
        # calculate_mod_obs_rmse_2023) -- see "model_scale" in README.md.
        variable="G_per_sap_area_avg",
        model_scale=500.0,  # 1000 * 0.5
        obs_file="/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed/Sapflow2023.csv",
        obs_column="J0.5",
        relative_sigma=0.25,
        weight=0.5,
        clip_negative_obs_to_zero=True,
    ),
    MetricSpec(
        name="gpp",
        category="Q_ASSIMI",
        variable="gpp_avg",
        obs_file="/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed/Fluxnet2023_2024_eval.csv",
        obs_column="GPP",
        relative_sigma=0.2,
        weight=1.0,
    ),
    # Soft plausibility constraint instead of real data: no obs_file here.
    # Useful if you only have e.g. GPP/ET but still know, physiologically,
    # that midday leaf water potential shouldn't leave some range -- this
    # keeps the calibration from drifting into implausible parameter
    # combinations that GPP/ET alone can't rule out (equifinality). See
    # "Soft plausibility constraints" in README.md.
    MetricSpec(
        name="psi_leaf_midday",
        category="PHYD",
        variable="psi_leaf_avg",
        target_min=-2.5,
        target_max=-0.3,
        hour_start=11,  # needs simulation.output_interval == "fluxnet_timestep" above
        hour_end=13,
        weight=0.5,
    ),
]

config = CalibrationConfig(
    site="DE-Hai",
    output_root="/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/lavendar_calibration/DE-Hai_example",
    # quincy_root="/path/to/quincy",   # optional; auto-detected if omitted
    run_mode="local",  # "local" (multiprocessing here) or "slurm_array" (sbatch --wait, one task/member)
    n_parallel=150,    # local: pool size. slurm_array: max concurrently running array tasks.
    # resume=True,     # set this (same output_root) for a second/third round after
                        # raising ensemble.max_iterations -- see "Second and third
                        # rounds" in README.md. Leave False for a fresh run.
    simulation=simulation,
    ensemble=ensemble,
    parameters=parameters,
    metrics=metrics,
)
