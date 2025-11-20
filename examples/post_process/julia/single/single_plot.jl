# using Pkg
# Pkg.add("NCDatasets")
# Pkg.add("Dates")
# Pkg.add("CFTime")
# Pkg.add("DataFrames")
# Pkg.add("Statistics")
# Pkg.add("ColorSchemes")
# Pkg.add("PyCall")
# Pkg.add("PyPlot")

using NCDatasets
using Dates 
using CFTime
using DataFrames
using Statistics 

script_dir = dirname(@__FILE__)

folder_data = "/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/science/phillip/output/03_transient_fluxnet/output/0"


include("../../../../src/postprocessing/julia/plt/qstd_plt_pyplot.jl")

folder_plt = joinpath(script_dir, "plots")
plt_settings = QPlotSettings()
plt_settings.verbose = true


create_std_plt_single_output(folder_data, folder_plt, plt_settings)

