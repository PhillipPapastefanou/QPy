using Statistics, VectorizedStatistics
using DataFrames
using Dates
using Base.Filesystem: basename
using CSV
using Base.Threads
using Plots
using LaTeXStrings
using StatsPlots

include("../../../../../../src/postprocessing/julia/core/qcomparer_2023.jl")
include("../../../../../../src/postprocessing/julia/core/qslicer.jl")

# --- 1. Helper Functions ---

function format_unit_to_latex(unit_str::String)
    s = replace(unit_str, "micro " => "\\mu{}")
    s = replace(s, "micro" => "\\mu{}")
    
    parts = split(s, " ", keepempty=false)
    formatted_parts = String[]
    
    for part in parts
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

param_info = Dict(
    "k_latosa"     => ("\\mathrm{Leaf area :Sapwood area}", "kg m-2 s-1 MPa-1"),
    "k_xylem_sats" => ("K_{xylem,sat}", "kg m-1 s-1 MPa-1"),
    "psi50_close"  => ("\\psi_\\mathrm{Leaf,close}", "MPa"),
    "root_dist"    => ("z_{root} \\mathrm{(Inv\\ root\\ depth)}", "1/m"),
    "g1"           => ("g_{1}\\mathrm{(water\\ use\\ strategy)}", "kPa0.5"),
    "g0"           => ("g_{0}", "mmol m-2 s-1")
)

# CHANGED: Added X_Pos as an Int to securely map to numeric coordinates
df_plot_all = DataFrame(Parameter=String[], Value=Float64[], Scenario=String[], X_Pos=Int[])
ide = "fig_0"
colors = [:blue, :brown, :red]
scen_order = [L"\psi_{L}", L"\psi_{L} + \psi_{s}", L"\psi_{L} + \psi_{s} + J"]

path_blue  = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/72_run_transient_3days_new_mort_new_phen_fix/output"
path_brown = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/72_run_transient_3days_new_mort_new_phen_fix/output" 
path_red   = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/72_run_transient_3days_new_mort_new_phen_fix/output" 

# Added ID parameter to securely map the scenario string to a numeric coordinate (1, 2, 3)
scenarios = [
    (file="df_psi_leaf_ind", label=L"\psi_{L}", id=1, rt_path=path_blue),
    (file="df_psi_stem_leaf_ind", label=L"\psi_{L} + \psi_{s}", id=2, rt_path=path_brown),
    (file="df_psi_stem_leaf_stem_flow_ind", label=L"\psi_{L} + \psi_{s} + J", id=3, rt_path=path_red)
]

post_process_dir = joinpath(scenarios[3].rt_path, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)

cols_interest = ["k_xylem_sats", "k_latosa", "g0", "g1", "psi50_close", "root_dist"]

# --- 3. Data Processing ---

for scen in scenarios
    params_file = joinpath(scen.rt_path, "../post", "params_rmse_2023.csv")
    df_params = CSV.read(params_file, DataFrame)
    
    ids_file = joinpath(scen.rt_path, "../post/ana", "$(scen.file)_all.csv")
    if isfile(ids_file)
        fids = CSV.read(ids_file, DataFrame)[!, :fid]
        df_scen = filter(row -> row.fid in fids, df_params)
        
        for param in cols_interest
            if hasproperty(df_scen, Symbol(param))
                vals = filter(v -> !ismissing(v) && !isnan(v), df_scen[!, param])
                
                if param == "g0"
                    vals = vals .* 1000.0
                end
                
                append!(df_plot_all, DataFrame(
                    Parameter = fill(param, length(vals)),
                    Value = vals,
                    Scenario = fill(scen.label, length(vals)),
                    X_Pos = fill(scen.id, length(vals)) # <--- Track numeric position
                ))
            end
        end
    end
end

# --- 4. Plotting ---

# --- 4. Plotting ---

plot_list = []
subplot_labels = ["a", "b", "c", "d", "e", "f"]

for (idx, param) in enumerate(cols_interest)
    df_sub = filter(r -> r.Parameter == param, df_plot_all)
    sort!(df_sub, :X_Pos) 

    if haskey(param_info, param)
        math_sym, raw_unit = param_info[param]
        p_title = latexstring(math_sym) 
        p_ylabel = format_unit_to_latex(raw_unit) 
    else
        p_title = param
        p_ylabel = "Value"
    end

    # Generate the plot using native structural title locations
    p = violin(df_sub.X_Pos, df_sub.Value, 
        group = df_sub.X_Pos,         
        xticks = (1:3, scen_order),   
        color = reshape(colors, 1, :), 
        
        title = p_title,
        
        ylabel = p_ylabel,     
        legend = false,
        xrotation = 45,
        tickfontsize = 14,      
        titlefontsize = 16,     
        guidefontsize = 14,
        trim = true,
        frame = :box,
        xlims = (0.5, 3.5),           
        top_margin = 6Plots.mm,
        titlefontfamily = "Computer Modern",
    )


yl = extrema(df_sub.Value)

ylab = yl[2] * 0.95
annotate!(p,
    (0.6, ylab,
     text("($(subplot_labels[idx]))", 14, :black, :bold))
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