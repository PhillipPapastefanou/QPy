using Statistics, VectorizedStatistics
using DataFrames
using Dates
using Base.Filesystem: basename
using CSV
using Base.Threads
using LaTeXStrings
using CairoMakie

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
    "k_xylem_sats" => ("K_{xylem,sat}", "kg m-1 s-1 MPa-1"),
    "k_latosa"     => ("\\mathrm{Leaf area :Sapwood area}", "kg m-2 s-1 MPa-1"),
    "psi50_close"  => ("\\psi_\\mathrm{Leaf,close}", "MPa"),
    "root_dist"    => ("z_{root} \\mathrm{(Inv\\ root\\ depth)}", "1/m"),
    "g1"           => ("g_{1}\\mathrm{(water\\ use\\ strategy)}", "kPa0.5"),
    "g0"           => ("g_{0}", "mmol m-2 s-1")
)

df_plot_all = DataFrame(Parameter=String[], Value=Float64[], Scenario=String[], X_Pos=Int[])
ide = "fig_0_alt"
colors = [:blue, :brown, :red]
colors = [:green, :orange, :red]
#scen_order = [L"\psi_{L}", L"\psi_{L} + \psi_{s}", L"\psi_{L} + \psi_{s} + J"]
scen_order = [L"J", L"J+ \psi_{s}", L"\psi_{L} + \psi_{s} + J"]

path_blue  = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/72_run_transient_3days_new_mort_new_phen_fix/output"
path_brown = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/72_run_transient_3days_new_mort_new_phen_fix/output" 
path_red   = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/72_run_transient_3days_new_mort_new_phen_fix/output" 

# scenarios = [
#     (file="df_psi_leaf_ind", label=L"\psi_{L}", id=1, rt_path=path_blue),
#     (file="df_psi_stem_leaf_ind", label=L"\psi_{L} + \psi_{s}", id=2, rt_path=path_brown),
#     (file="df_psi_stem_leaf_stem_flow_ind", label=L"\psi_{L} + \psi_{s} + J", id=3, rt_path=path_red)
# ]

scenarios = [
    (file="df_stem_flow_ind", label=L"J", id=1, rt_path=path_blue),
    (file="df_stem_flow_psi_stem_ind", label=L"J+ \psi_{s}", id=2, rt_path=path_brown),
    (file="df_psi_stem_leaf_stem_flow_ind", label=L"\psi_{L} + \psi_{s} + J", id=3, rt_path=path_red)
]

post_process_dir = joinpath(scenarios[3].rt_path, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)

cols_interest = ["k_xylem_sats", "k_latosa", "psi50_close", "root_dist","g1", "g0"] 

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
                    X_Pos = fill(scen.id, length(vals))
                ))
            end
        end
    end
end

# --- 4. NEW: Statistical Aggregation & CSV Export ---

# Generate grouping summaries securely via combination pipeline
df_summary = combine(
    groupby(df_plot_all, [:Parameter, :Scenario, :X_Pos]), 
    :Value => mean => :Mean, 
    :Value => std => :Std_Dev
)

# Arrange rows clearly corresponding to initial parameter layout mapping
sort!(df_summary, [:Parameter, :X_Pos])

# Strip out layout coordinates column used internally for sorting prior to output
df_output = select(df_summary, Not(:X_Pos))
df_output[!, :Mean] = round.(df_output[!, :Mean], sigdigits=3)
df_output[!, :Std_Dev] = round.(df_output[!, :Std_Dev], sigdigits=3)

# Save the structured stats matrix straight to the post directory
CSV.write(joinpath(post_process_dir, "parameter_summary_statistics.csv"), df_output)


# --- 5. Plotting (Makie Backend) ---

fig = Figure(size = (1300, 900))
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

    row = (idx - 1) ÷ 3 + 1
    col = (idx - 1) % 3 + 1

    ax = Axis(fig[row, col], 
        title = p_title,
        ylabel = p_ylabel,
        xticks = (1:3, scen_order),
        xticklabelrotation = pi/4, 
        titlesize = 21,          
        ylabelsize = 18,         
        xticklabelsize = 22,     
        yticklabelsize = 18      
    )

    xlims!(ax, 0.5, 3.5)
    mapped_colors = [colors[x] for x in df_sub.X_Pos]

    # Native Violin call utilizing equal width configurations
    violin!(ax, df_sub.X_Pos, df_sub.Value; 
        color = mapped_colors,
        strokewidth = 1.5,
        strokecolor = :black,
        width = 0.55,       
        scale = :width      
    )

    # Clean boxplot core insertion mirroring traditional StatsPlots layout aesthetics
    boxplot!(ax, df_sub.X_Pos, df_sub.Value;
        width = 0.08,             
        color = :white,           
        strokewidth = 1.5,
        strokecolor = :black,
        whiskerwidth = 0.04,
        markersize = 3.0          
    )

    text!(ax, 0.05, 0.95, 
        text = "($(subplot_labels[idx]))", 
        space = :relative, 
        align = (:left, :top), 
        fontsize = 22, 
        color = :black
    )
end

rowgap!(fig.layout, 40)
colgap!(fig.layout, 25)

save(joinpath(post_process_dir, "parameter_distributions_violin.png"), fig)