include("../../../../src/postprocessing/julia/core/qcomparer.jl")

using PyPlot
using CSV
using DataFrames


hainich_obs = init_hainich_obs();
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/05_transient_fluxnet_finer"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/06s_transient_fluxnet_finer"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/07s_transient_fluxnet_finer"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/11_transient_slurm_array"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/12_std_transient_slurm_array"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/13_transient_slurm_array"


calculate_mod_obs_rmse(rt_path_hyd, hainich_obs)
#calculate_mod_obs_rmse_parallel(rt_path_hyd, hainich_obs)

rmse_data_path = joinpath(rt_path_hyd, "post", "params_rmse.csv")

#df = CSV.read(rmse_data_path, DataFrame)
#vscodedisplay(df)

# sort(df, :psi_stem_rmse)[!,[:id,:gpp_rmse,:le_rmse,:psi_stem_rmse, :stem_flow_rmse]]
# sort(df, :stem_flow_rmse)[!,[:id,:gpp_rmse,:le_rmse,:psi_stem_rmse, :stem_flow_rmse]]
# sort(df, :gpp_rmse)[!,[:id,:gpp_rmse,:le_rmse,:psi_stem_rmse, :stem_flow_rmse]]

# print(names(df))
# dh = filter(row -> (row.psi_stem_rmse_23 < 0.1) & (row.stem_flow_rmse_23 < 0.30) & (row.gpp_rmse_23 < 3.2), df)


# vscodedisplay(df)


# dh = filter(row -> (row.psi_stem_rmse_23 < 0.12) & (row.stem_flow_rmse_23 < 0.30) , df)


# # 1. Select columns that do NOT contain "RMSE"
# cols = names(dh) .|> String
# cols_no_rmse = filter(col -> !occursin("RMSE", uppercase(col)), cols)


# # 2. Grid size (example: 4×4)
# nrows, ncols = 5, 4
# nplots = length(cols_no_rmse)

# figure(figsize=(12, 10))  # big figure

# for (i, col) in enumerate(cols_no_rmse)
#     ax = subplot(nrows, ncols, i)
#     ax[:hist](dh[!, Symbol(col)], bins=30)
#     ax[:set_title](col)
# end

# tight_layout()
# savefig("a.png")
# dh



# d_vng= sort(filter(row -> (row.soil_pyhs_ret == "VanGenuchten"), dh), :gpp_rmse_03)
# d_vng[1:5, :fid]

# d_camp= sort(filter(row -> (row.soil_pyhs_ret == "Campbell"), dh), :gpp_rmse_03)
# d_camp[1:5, :fid]

# vscodedisplay(d_vng)