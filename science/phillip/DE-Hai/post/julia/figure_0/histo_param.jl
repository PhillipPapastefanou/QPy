using Statistics, VectorizedStatistics
using DataFrames
using Dates
using Base.Filesystem: basename
using CSV
using Base.Threads
using Plots
using LaTeXStrings
using StatsPlots
using CategoricalArrays 

include("../../../../../../src/postprocessing/julia/core/qcomparer_2023.jl")
include("../../../../../../src/postprocessing/julia/core/qslicer.jl")

# --- 1. Helper Functions ---

function format_unit_to_latex(unit_str::String)
    s = replace(unit_str, "micro " => "\\mu{}")
    s = replace(s, "micro" => "\\mu{}")
    
    parts = split(s, " ", keepempty=false)
    formatted_parts = String[]
    
    for part in parts
        # Updated regex to handle decimals (e.g., 0.5)
        m = match(r"^([A-Za-z\\]+)(-?\d*\.?\d+)$", part)
        
        if m !== nothing
            base = m.captures[1]
            exponent = m.captures[2]
            push!(formatted_parts, "$(base)^{$(exponent)}")
        else
            push!(formatted_parts, part)
        end
    end
    
    joined_str = join(formatted_parts, " \\cdot ")
    final_latex_string = "\\mathrm{$(joined_str)}"
    return latexstring(final_latex_string)
end

# --- 2. Configuration & Labels ---

# Dictionary mapping raw columns to (Math Name, Units)
param_info = Dict(
    "k_xylem_sats" => ("K_{xylem,sat}", "kg m-1 s-1 MPa-1"),
    "k_latosa"     => ("\\mathrm{Leaf area :Sapwood area}", "kg m-2 s-1 MPa-1"),
    "g0"           => ("g_{0}", "mol m-2 s-1"),
    "g1"           => ("g_{1}\\mathrm{(water\\ use\\ strategy)}", "kPa0.5"),
    "psi50_close"  => ("\\psi_{Leaf,close}", "MPa"),
    "root_dist"    => ("z_{root} \\mathrm{(Inv\\ root\\ depth)}", "1/m")
)

# Pre-render the labels for the plot titles
param_labels = Dict(
    key => latexstring("$(val[1])\\ [$(format_unit_to_latex(val[2]))]") 
    for (key, val) in param_info
)

df_plot_all = DataFrame(Parameter=String[], Value=Float64[], Scenario=String[])
ide = "fig_0"
colors = [:blue, :brown, :red]
scen_order = [L"\psi_{L}", L"\psi_{L} + \psi_{s}", L"\psi_{L} + \psi_{s} + J"]

# --- INDIVIDUAL PATHS ---
path_blue  = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/67_run_transient_3days_new_mort_new_phen_fix/output"
path_brown = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/67_run_transient_3days_new_mort_new_phen_fix/output" # UPDATE ME
path_red   = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/70_run_transient_3days_new_mort_new_phen_fix/output" # UPDATE ME

# Expanded scenarios with individual paths
scenarios = [
    (file="df_psi_leaf_ind", label=L"\psi_{L}", rt_path=path_blue),
    (file="df_psi_stem_leaf_ind", label=L"\psi_{L} + \psi_{s}", rt_path=path_brown),
    (file="df_psi_stem_leaf_stem_flow_ind", label=L"\psi_{L} + \psi_{s} + J", rt_path=path_red)
]

# Set post-processing dir based on the first scenario
post_process_dir = joinpath(scenarios[3].rt_path, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)

cols_interest = ["k_xylem_sats", "k_latosa", "g0", "g1", "psi50_close", "root_dist"]

# --- 3. Data Processing ---

df_plot_all.Scenario = categorical(df_plot_all.Scenario, levels=scen_order)

for scen in scenarios
    # Load the params data explicitly from each scenario's path
    params_file = joinpath(scen.rt_path, "../post", "params_rmse_2023.csv")
    df_params = CSV.read(params_file, DataFrame)
    
    ids_file = joinpath(scen.rt_path, "../post/ana", "$(scen.file)_all.csv")
    if isfile(ids_file)
        fids = CSV.read(ids_file, DataFrame)[!, :fid]
        df_scen = filter(row -> row.fid in fids, df_params)
        
        for param in cols_interest
            if hasproperty(df_scen, Symbol(param))
                vals = filter(v -> !ismissing(v) && !isnan(v), df_scen[!, param])
                append!(df_plot_all, DataFrame(
                    Parameter = fill(param, length(vals)),
                    Value = vals,
                    Scenario = fill(scen.label, length(vals))
                ))
            end
        end
    end
end

# --- 4. Plotting ---

plot_list = []

for param in cols_interest
    df_sub = filter(r -> r.Parameter == param, df_plot_all)
    sort!(df_sub, :Scenario) 

    # 1. Extract the math symbol and unit safely
    if haskey(param_info, param)
        math_sym, raw_unit = param_info[param]
        
        # Title gets the math symbol (e.g., \psi_{50,close})
        p_title = latexstring(math_sym) 
        
        # Y-axis gets the LaTeX formatted unitz
        p_ylabel = format_unit_to_latex(raw_unit) 
    else
        # Fallback if a parameter is missing from the dictionary
        p_title = param
        p_ylabel = "Value"
    end

    # 2. Generate the plot
    p = violin(df_sub.Scenario, df_sub.Value, 
        group = df_sub.Scenario,
        color = reshape(colors, 1, :), 
        title = p_title,
        ylabel = p_ylabel,     # <--- Y-axis now uses the LaTeX unit
        legend = false,
        xrotation = 45,
        tickfontsize = 14,      # <--- Increases size of both X and Y tick labels
        titlefontsize = 18,     # <--- Optional: keeps title legible relative to ticks
        guidefontsize = 14,
        trim = true,
        frame = :box,

        # --- POSITIONING FIXES ---
    top_margin = 2Plots.mm,       # Pulls the plot area UP (reducing gap)
    titlefontfamily = "Computer Modern",
    )
    
    push!(plot_list, p)
end

# Create the final grid
final_violin_plot = plot(plot_list..., 
    layout = (2, 3), 
    size = (1200, 800), 
    margin = 10Plots.mm
)

# Save output
savefig(final_violin_plot, joinpath(post_process_dir, "parameter_distributions_violin.png"))

# Cleanup / Metadata (using names from the first scenario's params file to keep variable active)
df_params_meta = CSV.read(joinpath(scenarios[3].rt_path, "../post", "params_rmse_2023.csv"), DataFrame)
cols = names(df_params_meta) .|> String
exclude = ["RMSE", "ID", "FID", "USE_JSB_PHYSICS"]
cols_no_rmse = filter(col -> all(p -> !occursin(p, uppercase(col)), exclude), cols)
cols_rmse = filter(col -> occursin("RMSE", uppercase(col)), cols)