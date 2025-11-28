include("../../../../src/postprocessing/julia/core/qcomparer.jl")

using PyPlot
using CSV
using DataFrames


hainich_obs = init_hainich_obs();
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/05_transient_fluxnet_finer"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/06s_transient_fluxnet_finer"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/07s_transient_fluxnet_finer"


calculate_mod_obs_rmse(rt_path_hyd, hainich_obs)

rmse_data_path = joinpath(rt_path_hyd, "post", "params_rmse.csv")

df = CSV.read(rmse_data_path, DataFrame)

#vscodedisplay(df_param)
sort(df, :psi_stem_rmse)[!,[:id,:gpp_rmse,:le_rmse,:psi_stem_rmse, :stem_flow_rmse]]
sort(df, :stem_flow_rmse)[!,[:id,:gpp_rmse,:le_rmse,:psi_stem_rmse, :stem_flow_rmse]]
sort(df, :gpp_rmse)[!,[:id,:gpp_rmse,:le_rmse,:psi_stem_rmse, :stem_flow_rmse]]


vscodedisplay(sort(df, :psi_stem_rmse))
vscodedisplay(sort(df, :gpp_rmse))


dh = filter(row -> (row.psi_stem_rmse < 0.15) & (row.stem_flow_rmse < 0.30) & (row.gpp_rmse < 3.1), df)


vscodedisplay(dh)