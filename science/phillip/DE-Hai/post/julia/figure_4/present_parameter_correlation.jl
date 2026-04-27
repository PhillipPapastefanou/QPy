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
include("../../../../../../src/postprocessing/julia/core/qcomparer_2023.jl")
include("../../../../../../src/postprocessing/julia/core/qslicer.jl")

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
ide = "f4_corr"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/70_run_transient_3days_new_mort_new_phen_fix/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)

!isdir(post_process_dir) && mkpath(post_process_dir)

colors = [:purple, :blue, :green, :red]
scen_order = ["U", L"\psi_{L}", L"\psi_{s} + \psi_{L}", L"\psi_{s} + \psi_{L} + J"]
scenarios = [
    "df_ind" => "U",
    "df_psi_leaf_ind" => L"\psi_{L}",
    "df_psi_stem_leaf_ind" => L"\psi_{s} + \psi_{L}",
    "df_psi_stem_leaf_stem_flow_ind" => L"\psi_{s} + \psi_{L} + J"
]

cols_interest = ["k_xylem_sats", "gamma_stem_max", "gamma_leaf", "k_latosa", 
                 "g1", "psi50_close", "root_dist", "root_scale", "g0"]

# --- Column Renaming Dictionary ---
col_names_map = Dict(
    "k_xylem_sats"   => L"K_{xylem}",
    "gamma_stem_max" => L"\Gamma_{stem,max}",
    "gamma_leaf"     => L"\Gamma_{leaf}",
    "k_latosa"       => L"K_{latosa}",
    "g1"             => L"g_1",
    "psi50_close"    => L"\psi_\mathrm{L, close}",
    "root_dist"      => "Root Dist",
    "root_scale"     => "Root Scale",
    "g0"             => L"g_0"
)

# Create the display list for GraphRecipes
display_names = [get(col_names_map, col, col) for col in cols_interest]

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

    # --- Matrix Logic: Filter and Prep for Dynamic Thickness ---
    threshold = 0.15
    min_thick = 1.5
    max_thick = 12.0

    filtered_mat = zeros(n, n)
    abs_weights_mat = zeros(n, n)
    widths = zeros(n, n) 
    
    # Calculate matrix values (Upper triangle only)
    for i in 1:n
        for j in (i+1):n
            w = cor_mat[i, j]
            if abs(w) >= threshold
                filtered_mat[i, j] = w
                abs_weights_mat[i, j] = abs(w)
                # Dynamic scaling
                widths[i, j] = ((abs(w) - threshold) / (1.0 - threshold)) * (max_thick - min_thick) + min_thick
            end
        end
    end

    if all(filtered_mat .== 0.0)
        @info "No valid correlations >= $threshold found for scenario: $scen_label. Skipping plot."
        continue
    end
    
    current_scen_color = colors[idx]
    
    # --- 5. Generate Graph Plot ---
    radius = 10.0
    theta = range(0, stop=2π, length=n+1)[1:end-1]
    x_coords = radius .* cos.(theta)
    y_coords = radius .* sin.(theta)

    # 1. Create the base plot with EDGES ONLY
    p_graph = graphplot(abs_weights_mat,
        x = x_coords,
        y = y_coords,
        names = fill("", n),           # Hide default text
        nodeshape = :rect,             # Keep as rect but hide it
        markeralpha = 0.0,             # Make node fill invisible
        markerstrokealpha = 0.0,       # Make node border invisible
        edgecolor = current_scen_color,   
        edgewidth = widths,             
        directed = false,               
        arrow = false,
        curves = true,
        curvature_scalar = 0.85,                
        size = (1200, 1000),
        xlims = (-16, 16),
        ylims = (-16, 16),
        framestyle = :none,
        title = "Parameter Correlations: $scen_label"
    )

    # 2. Manually draw BULLETPROOF uniform rectangular boxes
    # Define exact width and height of boxes in graph coordinates
    box_w = 4.5
    box_h = 1.5

    for i in 1:n
        x_c = x_coords[i]
        y_c = y_coords[i]
        
        # Create an exact rectangle shape centered at the node coordinate
        rect = Shape(x_c .+ [-box_w/2, box_w/2, box_w/2, -box_w/2], 
                     y_c .+ [-box_h/2, -box_h/2, box_h/2, box_h/2])
        
        # Plot the white box with black border
        plot!(p_graph, rect, fillcolor=:white, linecolor=:black, label="")
        
        # Overlay the text perfectly centered in the new box
annotate!(p_graph, x_c, y_c, 
    text(display_names[i], font(16, "Computer Modern", :black, :center)))
    end

    # 3. Add Edge Labels (Correlation values)
    for i in 1:n
        for j in (i+1):n
            w = filtered_mat[i, j]
            if w != 0.0
                mx = (x_coords[i] + x_coords[j]) / 2
                my = (y_coords[i] + y_coords[j]) / 2
                annotate!(p_graph, mx, my + 0.6, 
                    text(string(round(w, digits=2)), 10, :black, :center, font("Computer Modern")))
            end
        end
    end
    
    clean_label = replace(lowercase(scen_file), " " => "_")
    out_name = "correlation_network_$(clean_label).png"
    savefig(p_graph, joinpath(post_process_dir, out_name))
    
    println("Successfully saved graph for: $scen_label to $out_name")
end

println("All scenarios processed.")