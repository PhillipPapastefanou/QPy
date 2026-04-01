using Statistics, VectorizedStatistics
using DataFrames
using Dates
using Base.Filesystem: basename
using CSV
using Base.Threads
using Plots
using LaTeXStrings
using Graphs
using GraphRecipes

# --- 1. Load Custom Core Functions ---
# Note: Ensure these paths are correct relative to your script location
include("../../../src/postprocessing/julia/core/qcomparer_2023.jl")
include("../../../src/postprocessing/julia/core/qslicer.jl")

# --- 2. Helper Functions ---
function format_unit_to_latex(unit_str::String)
    s = replace(unit_str, "micro " => "\\mu{}")
    s = replace(s, "micro" => "\\mu{}")
    parts = split(s, " ", keepempty=false)
    formatted_parts = String[]
    for part in parts
        m = match(r"^([A-Za-z\\]+)(-?\d+)$", part)
        if m !== nothing
            push!(formatted_parts, "$(m.captures[1])^{$(m.captures[2])}")
        else
            push!(formatted_parts, part)
        end
    end
    return latexstring("\\mathrm{$(join(formatted_parts, " \\cdot "))}")
end

# --- 3. Setup Parameters & Paths ---
ide = "corr"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/63_run_transient_3days/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)

# Create directory if it doesn't exist
!isdir(post_process_dir) && mkpath(post_process_dir)

colors = [:purple, :blue, :green, :red]
scen_order = ["Ind", "Psi Stem", "Psi Leaf", "Flow"]
# Define the scenarios
scenarios = [
    "df_ind" => "Ind",
    "df_psi_stem_ind" => "Psi Stem",
    "df_psi_stem_leaf_ind" => "Psi Leaf",
    "df_psi_stem_leaf_stem_flow_ind" => "Flow"
]

cols_interest = ["k_xylem_sats", "gamma_stem_max", "gamma_leaf", "k_latosa", 
                 "g1", "psi50_close", "root_dist", "root_scale", "g0"]

# Read the master parameter file
params_path = joinpath(rt_path_hyd, "../post", "params_rmse_2023.csv")
if !isfile(params_path)
    error("Master parameter file not found at: $params_path")
end
df_params = CSV.read(params_path, DataFrame)

# --- 4. Main Processing Loop ---
for (idx, (scen_file, scen_label)) in enumerate(scenarios)
    ids_path = joinpath(rt_path_hyd, "../post/ana", "$(scen_file)_all.csv")
        n = length(cols_interest)
    # Check if the scenario ID file exists
    if !isfile(ids_path)
        @warn "ID file not found for scenario $scen_label: $ids_path"
        continue
    end

    # Read the best-fit IDs for this scenario
    fids_df = CSV.read(ids_path, DataFrame)
    if isempty(fids_df) || !("fid" in names(fids_df))
        @warn "Scenario $scen_label has no valid 'fid' column or is empty."
        continue
    end
    fids = fids_df[!, :fid]
    
    # Filter master parameter list for these specific IDs
    df_scen = filter(row -> row.fid in fids, df_params)
    
    # Check if we actually have data after filtering
    if isempty(df_scen)
        @warn "No matching parameters found for scenario: $scen_label"
        continue
    end

    # Prepare Data Matrix: drop rows containing any missing/NaN values across our columns of interest
    clean_data = dropmissing(df_scen[!, cols_interest])
    
    # CRITICAL SAFETY CHECK: correlation requires at least 2 rows
    if size(clean_data, 1) < 2
        @warn "Not enough valid data rows (found $(size(clean_data, 1))) for correlations in scenario: $scen_label"
        continue
    end

    # Convert to Matrix for Statistics.cor
    data_matrix = Matrix(clean_data)

    # Calculate Correlation Matrix
    cor_mat = cor(data_matrix)

    # Apply Threshold Filter (|r| > 0.25)
    filtered_mat = copy(cor_mat)
    for i in 1:size(filtered_mat, 1), j in 1:size(filtered_mat, 2)
        # Remove correlations below threshold and diagonal (self-correlation)
        if abs(filtered_mat[i,j]) < 0.25 || i == j
            filtered_mat[i,j] = 0.0
        end
    end

    # Check if there are any edges to plot at all
    if all(filtered_mat .== 0.0)
        @info "No correlations > 0.25 found for scenario: $scen_label. Skipping plot."
        continue
    end
current_scen_color = colors[idx]
    # --- 5. Generate Graph Plot ---
radius = 10.0
    theta = range(0, stop=2π, length=n+1)[1:end-1]
    x_coords = radius .* cos.(theta)
    y_coords = radius .* sin.(theta)

    # --- 4. Plotting ---
    p_graph = graphplot(filtered_mat,
        # Force the exact coordinates
        x = x_coords,
        y = y_coords,
        names = cols_interest,
        
        # Box styling
        nodeshape = :rect,
        nodecolor = :white,
        markerstrokecolor = :black,
        nodesize = 3,                  # Controls box size
        fontsize = 12,
        
        # Arrow styling - Use EDGECOLOR to force it
        edgecolor = current_scen_color,   
        edgewidth = (s, d, w) -> 8 * abs(w),
        arrow = arrow(:closed, :head, 0.4, 0.4),
        curves = true,
        curvature_scalar = 0.85,                
        
        # Canvas styling
        size = (1200, 1000),
        xlims = (-15, 15),                # Radius is 10, limits are 15 -> lots of safe padding
        ylims = (-15, 15),
        framestyle = :none,               # Hides axis grids completely
        title = "Parameter Correlations: $scen_label"
    )

    # --- 5. Pinpoint Label Placement ---
    for i in 1:n, j in 1:n
        w = filtered_mat[i, j]
        if w != 0.0
            # Calculate exact midpoint of the straight line
            mx = (x_coords[i] + x_coords[j]) / 2
            my = (y_coords[i] + y_coords[j]) / 2
            
            # Shift the text slightly UP (+0.6) so it floats above the thick line
            annotate!(p_graph, mx - 0.1, my + 0.6, 
                text(string(round(w, digits=2)), 11, :black, :center, font("Computer Modern")))
        end
    end
    # Save with dynamic filename
    clean_label = replace(lowercase(scen_label), " " => "_")
    out_name = "correlation_network_$(clean_label).png"
    savefig(p_graph, joinpath(post_process_dir, out_name))
    
    println("Successfully saved graph for: $scen_label to $out_name")
end

println("All scenarios processed.")