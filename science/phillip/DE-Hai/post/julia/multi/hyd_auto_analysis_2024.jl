include("../../../../../../src/postprocessing/julia/core/qcomparer_2024.jl")
#include("../../../../src/postprocessing/julia/core/qcomparer_2023.jl")

using CSV
using DataFrames
using Distributed

hainich_obs = init_hainich_obs();

rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/05_transient_fluxnet_finer"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/06s_transient_fluxnet_finer"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/07s_transient_fluxnet_finer"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/11_transient_slurm_array"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/12_std_transient_slurm_array"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/14_transient_slurm_array"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/15_transient_slurm_array"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/18_transient_slurm_array_vj"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/19_transient_slurm_array_vj"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/20_transient_slurm_array_krtos"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/21_transient_slurm_array_krtos"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/26_transient_slurm_array_dyn_roots_off"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/26_transient_slurm_array_dyn_roots_off"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/27_transient_slurm_array_dyn_roots_off"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/27b_transient_slurm_array_dyn_roots_off"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/28_run_transient_slurn_array_constrained"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/29_transient_slurm_array_dyn_roots_off"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/30_run_transient_slurm_array_mort_hyd_fail_mort"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/2026_31_run_transient_slurm_array_mort_hyd_fail_mort"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/2026_32_run_transient_slurm_array_mort_hyd_fail_mort"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/2026_33_run_transient_slurm_array_mort_hyd_fail_mort"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/2026_35b_run_transient_slurm_array_mort_hyd_fail_mort_g1"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/37_rerun_for_test"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/38_rerun_for_test"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/42_run_transient_slurm_array_mort_hyd_fail_mort_g1"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/60_run_transient_slurm_array_mort_hyd_fail_mort_g1"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/53_run_transient_g1_low_gamma_leaf"
#rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/255_run_transient_no_texture"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/55_run_transient_g1_low_gamma_leaf"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/56_refix_run_transient_g1_low_gamma_leaf"


#calculate_mod_obs_rmse_2024(rt_path_hyd, hainich_obs)                                     
#calculate_mod_obs_rmse_2023(rt_path_hyd, hainich_obs)                                     
#calculate_mod_obs_rmse_parallel(rt_path_hyd, hainich_obs)


if abspath(PROGRAM_FILE) == @__FILE__
    
    # Load observation data

    
    println("Starting RMSE calculations...")
    calculate_mod_obs_rmse_2024(rt_path_hyd, hainich_obs)
end

