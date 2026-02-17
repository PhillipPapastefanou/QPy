using Pkg
# Pkg.add("NCDatasets")
# Pkg.add("Dates")
# Pkg.add("CFTime")
# Pkg.add("DataFrames")
# Pkg.add("Statistics")
Pkg.add("ColorSchemes")
# Pkg.add("PyCall")
# Pkg.add("PyPlot")

using NCDatasets
using Dates 
using DataFrames
using Statistics 

script_dir = dirname(@__FILE__)

folder_data = "/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/science/phillip/output/03_transient_fluxnet/output/0"
folder_data = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/38_rerun_for_test/output/29"
#folder_data = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/40_run_transient_slurm_array_mort_hyd_fail_mort_g1/output/26"


include("../../../../src/postprocessing/julia/plt/qstd_plt_pyplot.jl")

folder_plt = joinpath(script_dir, "plots")
plt_settings = QPlotSettings()
plt_settings.verbose = true


create_std_plt_single_output(folder_data, folder_plt, plt_settings)

