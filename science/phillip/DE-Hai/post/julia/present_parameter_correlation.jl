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
include("../../../../../src/postprocessing/julia/core/qcomparer_2023.jl")
include("../../../../../src/postprocessing/julia/core/qslicer.jl")

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
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/70_run_transient_3days_new_mort_new_phen_fix/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)

!isdir(post_process_dir) && mkpath(post_process_dir)

colors = [:purple, :blue, :green, :red]
scen_order = ["U", L"\psi_{s}", L"\psi_{s} + \psi_{L}", L"\psi_{s} + \psi_{L} + J"]
scenarios = [
    "df_ind" => "U",
    "df_psi_stem_ind" => L"\psi_{s}",
    "df_psi_stem_leaf_ind" => L"\psi_{s} + \psi_{L}",
    "df_psi_stem_leaf_stem_flow_ind" => L"\psi_{s} + \psi_{L} + J"
]

cols_interest = ["k_xylem_sats", "gamma_stem_max", "gamma_leaf", "k_latosa", 
                 "g1", "psi50_close", "root_dist", "root_scale", "g0"]

params_path = joinpath(rt_path_hyd, "../post", "params_rmse_2023.csv")
if !isfile(params_path)
    error("Master parameter file not found at: $params_path")
end
df_params = CSV.read(params_path, DataFrame)

# --- 4. Main Processing Loop ---
for (idx, (scen_file, scen_label)) in enumerate(scenarios)
    ids_path = joinpath(rt_path_hyd, "../post/ana", "$(scen_file)_all.csv")
    n = length(cols_interest)
    
    if !isfile(ids_path)
        @warn "ID file not found for scenario $scen_label: $ids_path"
        continue
    end

    fids_df = CSV.read(ids_path, DataFrame)
    if isempty(fids_df) || !("fid" in names(fids_df))
        @warn "Scenario $scen_label has no valid 'fid' column or is empty."
        continue
    end
    fids = fids_df[!, :fid]
    
    df_scen = filter(row -> row.fid in fids, df_params)
    
    if isempty(df_scen)
        @warn "No matching parameters found for scenario: $scen_label"
        continue
    end

    clean_data = dropmissing(df_scen[!, cols_interest])
    
    if size(clean_data, 1) < 2
        @warn "Not enough valid data rows for scenario: $scen_label"
        continue
    end

    data_matrix = Matrix(clean_data)
    cor_mat = cor(data_matrix)

    # --- Matrix Splitting Logic ---
    # Create separate matrices for thin and thick lines
    mat_thin = zeros(n, n)
    mat_thick = zeros(n, n)
    
    for i in 1:n, j in 1:n
        if i == j
            continue # Skip self-correlation
        end
        
        w = cor_mat[i, j]
        abs_w = abs(w)
        
        # Apply your exact threshold rules
        if abs_w >= 0.15 && abs_w < 0.25
            mat_thin[i, j] = w
        elseif abs_w >= 0.25
            mat_thick[i, j] = w
        end
        # If < 0.15, it remains 0.0 in both matrices (invisible)
    end

    # Combine them for the annotation loop later
    filtered_mat = mat_thin .+ mat_thick

    if all(filtered_mat .== 0.0)
        @info "No valid correlations >= 0.15 found for scenario: $scen_label. Skipping plot."
        continue
    end
    
    current_scen_color = colors[idx]
    
    # --- 5. Generate Graph Plot ---
    radius = 10.0
    theta = range(0, stop=2π, length=n+1)[1:end-1]
    x_coords = radius .* cos.(theta)
    y_coords = radius .* sin.(theta)

    # Plot 1: Base graph with the THIN lines (half thickness = 4.0)
    p_graph = graphplot(mat_thin,
        x = x_coords,
        y = y_coords,
        names = cols_interest,
        nodeshape = :rect,
        nodecolor = :white,
        markerstrokecolor = :black,
        nodesize = 3,
        fontsize = 12,
        edgecolor = current_scen_color,   
        linewidth = 4.0,           # Set static half thickness here
        arrow = arrow(:closed, :head, 0.4, 0.4),
        curves = true,
        curvature_scalar = 0.85,                
        size = (1200, 1000),
        xlims = (-15, 15),
        ylims = (-15, 15),
        framestyle = :none,
        title = "Parameter Correlations: $scen_label"
    )

    # Plot 2: Overlay the THICK lines (full thickness = 8.0) if any exist
    if any(mat_thick .!= 0.0)
        graphplot!(p_graph, mat_thick,
            x = x_coords,
            y = y_coords,
            names = fill("", n),        # Empty strings so text isn't drawn twice
            nodeshape = :rect,
            markeralpha = 0.0,          # Hide the nodes on the overlay
            markerstrokealpha = 0.0,    
            nodesize = 3,               # Keep size identical so arrows terminate correctly
            edgecolor = current_scen_color,   
            linewidth = 8.0,            # Set static full thickness here
            arrow = arrow(:closed, :head, 0.4, 0.4),
            curves = true,
            curvature_scalar = 0.85
        )
    end

    # --- Pinpoint Label Placement ---
    for i in 1:n, j in 1:n
        w = filtered_mat[i, j]
        if w != 0.0
            mx = (x_coords[i] + x_coords[j]) / 2
            my = (y_coords[i] + y_coords[j]) / 2
            
            annotate!(p_graph, mx - 0.1, my + 0.6, 
                text(string(round(w, digits=2)), 11, :black, :center, font("Computer Modern")))
        end
    end
    
    clean_label = replace(lowercase(scen_file), " " => "_")
    out_name = "correlation_network_$(clean_label).png"
    savefig(p_graph, joinpath(post_process_dir, out_name))
    
    println("Successfully saved graph for: $scen_label to $out_name")
end

println("All scenarios processed.")