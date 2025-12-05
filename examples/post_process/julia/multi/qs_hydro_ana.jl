

include("../../../../src/postprocessing/julia/core/qcomparer.jl")

using PyPlot
using CSV
using DataFrames

rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/14_transient_slurm_array"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/15_transient_slurm_array"


rmse_data_path = joinpath(rt_path_hyd, "post", "params_rmse.csv")

df = CSV.read(rmse_data_path, DataFrame)
df = df[:, .!map(col -> all(x -> ismissing(x) || (x isa Number && isnan(x)), col),
                 eachcol(df))]


ds = df[[1, 4097],cols_rmse]
vscodedisplay(ds)


# print(names(df))
dh = filter(row -> (row.psi_stem_rmse_23 < 0.1) & (row.stem_flow_rmse_23 < 0.30) & (row.gpp_rmse_23 < 3.2), df)
dh = filter(row -> (row.psi_stem_rmse_23 < 0.1) & (row.stem_flow_rmse_23 < 0.30) & (row.le_rmse_23 < 35), df)

dh = filter(row -> (row.psi_stem_rmse_23 < 0.12) & (row.stem_flow_rmse_23 < 0.30)&(row.le_rmse_23 < 34) , df)
dh = filter(row -> (row.psi_stem_rmse_23 < 0.1) & (row.stem_flow_rmse_23 < 0.28)&(row.le_rmse_full < 35)&(row.gpp_rmse_full < 3.4) , df)
dh = filter(row -> (row.psi_stem_rmse_23 < 0.1) & (row.stem_flow_rmse_23 < 0.28) & (row.le_rmse_18 < 33)&(row.gpp_rmse_18 < 3.2) , df)
dh = filter(row -> (row.psi_stem_rmse_23 < 0.1) & (row.stem_flow_rmse_23 < 0.28) & (row.le_rmse_03 < 40)&(row.gpp_rmse_03 < 4.1) , df)


vscodedisplay(dh)


# 1. Select columns that do NOT contain "RMSE" 
cols = names(dh) .|> String
cols_no_rmse = filter(col -> !occursin("RMSE", uppercase(col)), cols)
cols_rmse = filter(col -> occursin("RMSE", uppercase(col)), cols)



# 2. Grid size (example: 4×4)
nrows, ncols = 5, 4
nplots = length(cols_rmse)

figure(figsize=(12, 10))

for (i, col) in enumerate(cols_rmse)
    ax = subplot(nrows, ncols, i)
    ax[:hist](df[!, Symbol(col)], bins=30)
    ax[:set_title](col)
end

tight_layout()
savefig("a.png")
dh



# d_vng= sort(filter(row -> (row.soil_pyhs_ret == "VanGenuchten"), dh), :gpp_rmse_03)
# d_vng[1:5, :fid]

# d_camp= sort(filter(row -> (row.soil_pyhs_ret == "Campbell"), dh), :gpp_rmse_03)
# d_camp[1:5, :fid]

# vscodedisplay(d_vng) 