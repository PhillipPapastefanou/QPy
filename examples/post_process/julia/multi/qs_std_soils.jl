using PyPlot
using CSV
using DataFrames



rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/12_std_transient_slurm_array"


rmse_data_path = joinpath(rt_path_hyd, "post", "params_rmse.csv")

df = CSV.read(rmse_data_path, DataFrame)
#vscodedisplay(df)

soil_water_types = unique(df.soil_pyhs_ret)

fid =[]
for swr in soil_water_types 
    best_row = sort(filter(row -> (row.soil_pyhs_ret == swr), df), :gpp_rmse_full)[1,:]
    push!(fid,best_row.fid)
end

for swr in soil_water_types 
    best_row = sort(filter(row -> (row.soil_pyhs_ret == swr), df), :le_rmse_full)[1,:]
    println(best_row.le_rmse_full)
end

df[fid,:gpp_rmse_full]

df[fid,:le_rmse_full]


df[fid,:gpp_rmse_03]


df[fid,:le_rmse_03]


df[fid,:le_rmse_18]



df[fid,:gpp_rmse_18]

df[fid,:gpp_rmse_23]

df[fid,:le_rmse_23]