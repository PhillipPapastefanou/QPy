
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


function format_unit_to_latex(unit_str::String)

    # 1. Handle "micro" prefixes
    # We replace it with \mu{} so LaTeX separates the macro from the next letters 
    # (e.g., \mu{}mol prevents it from looking for a non-existent \mumol command)
    s = replace(unit_str, "micro " => "\\mu{}")
    s = replace(s, "micro" => "\\mu{}")
    
    # 2. Split the string into individual units based on spaces
    parts = split(s, " ", keepempty=false)
    
    formatted_parts = String[]
    
    for part in parts
        # Regex explanation:
        # ^([A-Za-z\\]+)  -> Captures the base (letters or slashes for \mu)
        # (-?\d+)$        -> Captures the exponent (optional minus sign, then numbers)
        m = match(r"^([A-Za-z\\]+)(-?\d+)$", part)
        
        if m !== nothing
            # If it has an exponent, format it as base^{exponent}
            base = m.captures[1]
            exponent = m.captures[2]
            push!(formatted_parts, "$(base)^{$(exponent)}")
        else
            # If no exponent is found, leave it as is (e.g., "mol", "MPa")
            push!(formatted_parts, part)
        end
    end
    
    # 3. Join everything together with the center dot
    joined_str = join(formatted_parts, " \\cdot ")
    
    # 4. Wrap the whole thing in \mathrm{} to keep the font upright
    final_latex_string = "\\mathrm{$(joined_str)}"
    
    # Convert and return as a LaTeXString
    return latexstring(final_latex_string)
end

df_plot_all = DataFrame(Parameter=String[], Value=Float64[], Scenario=String[])
ide = "fig_0"
colors = [:blue, :green, :red]
scen_order = [L"\psi_{L}", L"\psi_{s} + \psi_{L}", L"\psi_{s} + \psi_{L} + J"]
scenarios = [
    #"df_ind" => "U",
    "df_psi_leaf_ind" => L"\psi_{L}",
    "df_psi_stem_leaf_ind" => L"\psi_{s} + \psi_{L}",
    "df_psi_stem_leaf_stem_flow_ind" => L"\psi_{s} + \psi_{L} + J"
]
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/70_run_transient_3days_new_mort_new_phen_fix/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)
# Read parameter data
df_params = CSV.read(joinpath(rt_path_hyd, "../post", "params_rmse_2023.csv"), DataFrame)

cols_interest = ["k_xylem_sats", "k_latosa", "g0",
                 "g1", "psi50_close", "root_dist"]

# --- 2. Build Combined Dataframe for Plotting ---
# We want a long-format DF: [ParameterName, Value, ScenarioLabel]
df_plot_all.Scenario = categorical(df_plot_all.Scenario, levels=scen_order)

for (scen_file, scen_label) in scenarios
    ids_file = joinpath(rt_path_hyd, "../post/ana", "$(scen_file)_all.csv")
    fids = CSV.read(ids_file, DataFrame)[!, :fid]
    
    # Filter df_params to only include the FIDs in this scenario
    # We use 'in' to match the IDs
    df_scen = filter(row -> row.fid in fids, df_params)
    
    # Extract only our parameters of interest and reshape to Long format
    for param in cols_interest
        if hasproperty(df_scen, Symbol(param))
            vals = filter(v -> !ismissing(v) && !isnan(v), df_scen[!, param])
            append!(df_plot_all, DataFrame(
                Parameter = fill(param, length(vals)),
                Value = vals,
                Scenario = fill(scen_label, length(vals))
            ))
        end
    end
end

# Ensure Scenario is a Categorical or specific order for the X-axis
scen_order = [s[2] for s in scenarios]

# --- 3. Plotting ---
# We create a list of plots to assemble into a grid
plot_list = []

for param in cols_interest
    df_sub = filter(r -> r.Parameter == param, df_plot_all)
    sort!(df_sub, :Scenario) 

    p = violin(df_sub.Scenario, df_sub.Value, 
        group = df_sub.Scenario,
        # Reshaping colors into a row vector (1, :) maps them to the groups in order
        color = reshape(colors, 1, :), 
        title = param,
        ylabel = "Value",
        legend = false,
        # xticks = :all,  <-- REMOVE THIS LINE
        xrotation = 45,
        trim = true,
        frame = :box
    )
        
    push!(plot_list, p)
end
# Create the final 3x3 grid
final_violin_plot = plot(plot_list..., 
    layout = (2, 3), 
    size = (1200, 600), 
    margin = 5Plots.mm
)

# Save
savefig(final_violin_plot, joinpath(post_process_dir, "parameter_distributions_violin.png"))

cols = names(df_params) .|> String
exclude = ["RMSE", "ID", "FID", "USE_JSB_PHYSICS"]
cols_no_rmse = filter(col -> all(p -> !occursin(p, uppercase(col)), exclude), cols)
cols_rmse = filter(col -> occursin("RMSE", uppercase(col)), cols)

