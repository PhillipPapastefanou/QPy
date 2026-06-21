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
using LinearAlgebra  # Essential for matrix inversion (inv)

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
ide = "f4_corrt"
colors = [:blue, :brown, :red]
scen_order = [L"\psi_{L}", L"\psi_{s} + \psi_{L}", L"\psi_{s} + \psi_{L} + J"]

# --- INDIVIDUAL PATHS ---
path_blue  = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/72_run_transient_3days_new_mort_new_phen_fix/output"
path_green = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/72_run_transient_3days_new_mort_new_phen_fix/output" 
path_red   = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/72_run_transient_3days_new_mort_new_phen_fix/output" 

# Expanded scenarios mapping to individual paths
scenarios = [
    (file="df_psi_leaf_ind", label=L"\psi_{L}", rt_path=path_blue),
    (file="df_psi_stem_leaf_ind", label=L"\psi_{s} + \psi_{L}", rt_path=path_green),
    (file="df_psi_stem_leaf_stem_flow_ind", label=L"\psi_{s} + \psi_{L} + J", rt_path=path_red)
]

# Set post-processing dir based on the third scenario (red)
post_process_dir = joinpath(scenarios[3].rt_path, "../post", ide)
!isdir(post_process_dir) && mkpath(post_process_dir)

cols_interest = ["k_xylem_sats", "gamma_stem_max", "gamma_leaf", "k_latosa", 
                 "g1", "psi50_close", "root_dist", "root_scale", "g0"]

# --- Column Renaming Dictionary ---
col_names_map = Dict(
    "k_xylem_sats"   => L"K_\mathrm{xylem}",
    "gamma_stem_max" => L"\Gamma_\mathrm{stem,max}",
    "gamma_leaf"     => L"\Gamma_{leaf}",
    "k_latosa"       => L"K_\mathrm{latosa}",
    "g1"             => L"g_1",
    "psi50_close"    => L"\psi_\mathrm{L, close}",
    "root_dist"      => "Root depth",
    "root_scale"     => L"\mathrm{WUE_{root}}",
    "g0"             => L"g_0"
)

# Create the display list for GraphRecipes
display_names = [get(col_names_map, col, col) for col in cols_interest]

# --- 4. Main Processing Loop ---
for (idx, scen) in enumerate(scenarios)
    scen_file = scen.file
    scen_label = scen.label
    current_rt_path = scen.rt_path
    
    # 1. Load the params data explicitly from each scenario's path
    params_path = joinpath(current_rt_path, "../post", "params_rmse_2023.csv")
    if !isfile(params_path)
        @warn "Master parameter file not found for scenario $scen_label at: $params_path"
        continue
    end
    df_params = CSV.read(params_path, DataFrame)

    # 2. Filter using IDs
    ids_path = joinpath(current_rt_path, "../post/ana", "$(scen_file)_all.csv")
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

    # =========================================================================
    # --- PARTIAL CORRELATIONS MATRIX ENGINE ---
    # =========================================================================
    inv_cor = inv(cor_mat)
    part_cor_mat = zeros(n, n)
    var_explained_mat = zeros(n, n)

    for i in 1:n
        for j in 1:n
            if i == j
                part_cor_mat[i, j] = 1.0
                var_explained_mat[i, j] = 1.0
            else
                p_r = -inv_cor[i, j] / sqrt(inv_cor[i, i] * inv_cor[j, j])
                part_cor_mat[i, j] = p_r
                var_explained_mat[i, j] = p_r^2  
            end
        end
    end

    results_list = []
    for i in 1:n
        for j in (i+1):n
            push!(results_list, (
                Parameter_1 = cols_interest[i],
                Parameter_2 = cols_interest[j],
                Standard_Correlation = round(cor_mat[i, j], digits=4),
                Partial_Correlation = round(part_cor_mat[i, j], digits=4),
                Unique_Variance_pct = round(var_explained_mat[i, j] * 100, digits=2)
            ))
        end
    end
    
    df_results = DataFrame(results_list)
    df_results[!, :abs_std_corr] = abs.(df_results.Standard_Correlation)
    sort!(df_results, :abs_std_corr, rev = true)
    select!(df_results, Not(:abs_std_corr))

    clean_label = replace(lowercase(scen_file), " " => "_")
    csv_out_name = "partial_correlations_$(clean_label).csv"
    CSV.write(joinpath(post_process_dir, csv_out_name), df_results)

    # =========================================================================
    # --- NEW FEATURE: DYNAMIC GENERATION OF THE TEXT ANALYSIS REPORT ---
    # =========================================================================
    # 1. Calculation for Method 1 (Network Weight Share of Top 3 Pairs)
    top_3_variance = sum(df_results.Unique_Variance_pct[1:3])
    total_network_variance = sum(df_results.Unique_Variance_pct)
    top_3_share = (top_3_variance / total_network_variance) * 100

    # 2. Calculation for Method 2 (Multiple R² for individual node constraints)
    r2_mult_list = []
    for i in 1:n
        r2_val = 1.0 - (1.0 / inv_cor[i, i]) 
        push!(r2_mult_list, (Parameter = cols_interest[i], R2_pct = r2_val * 100))
    end
    df_r2 = DataFrame(r2_mult_list)
    sort!(df_r2, :R2_pct, rev=true)

    # 3. Construct and write the .txt file report string
    report_path = joinpath(post_process_dir, "variance_analysis_report_$(clean_label).txt")
    open(report_path, "w") do f
        write(f, "================================================================================\n")
        write(f, "HYDRAULIC STRUCTURE NETWORK METRICS REPORT (NON-PCA APPROACH)\n")
        write(f, "================================================================================\n")
        write(f, "Scenario: $scen_label\n")
        write(f, "Generated on: $(Dates.today())\n\n")
        
        write(f, "--------------------------------------------------------------------------------\n")
        write(f, "METHOD 1: THE NETWORK WEIGHT CONTRIBUTION METHOD\n")
        write(f, "--------------------------------------------------------------------------------\n")
        write(f, "This method evaluates the total direct, unique interactions (Partial R²) inside the\n")
        write(f, "system and measures what percentage is locked into the top 3 dominant tradeoffs.\n\n")
        write(f, "  * Absolute unique variance sum of top 3 relationships: $(round(top_3_variance, digits=2))%\n")
        write(f, "  * Cumulative unique variance sum across all 36 links:  $(round(total_network_variance, digits=2))%\n\n")
        write(f, "  >> PREPARED RESULT STATEMENT:\n")
        write(f, "  \"Of all isolated parameter interactions within the functional hydraulic network,\n")
        write(f, "   just three fundamental tradeoffs account for $(round(top_3_share, digits=2))% of the total\n")
        write(f, "   structural network connectivity.\"\n\n")
        
        write(f, "--------------------------------------------------------------------------------\n")
        write(f, "METHOD 2: NODE CONSTRAINT CAPACITY (MULTIPLE R-SQUARED VALUES)\n")
        write(f, "--------------------------------------------------------------------------------\n")
        write(f, "This evaluates how much a single biological parameter's variance is completely determined\n")
        write(f, "and locked in by its connections to the rest of the model matrix.\n\n")
        write(f, "   Parameter       |  Variance Explained by the Rest of the Web (Multiple R²)\n")
        write(f, "   -----------------------------------------------------------------------------\n")
        for row in eachrow(df_r2)
            p_name = rpad(row.Parameter, 18)
            r_val  = lpad(string(round(row.R2_pct, digits=2)) * "%", 8)
            write(f, "   $p_name|  $r_val\n")
        end
        write(f, "\n  >> PREPARED RESULT STATEMENT:\n")
        write(f, "  \"The internal architectural constraints of the model are highly centralized.\n")
        write(f, "   Core hydraulic traits like $(df_r2.Parameter[1]) and $(df_r2.Parameter[2]) are so structurally bound\n")
        write(f, "   that over $(round(df_r2.R2_pct[1], digits=1))% of their model variance is strictly pre-determined\n")
        write(f, "   by the surrounding network matrix parameters.\"\n")
        write(f, "================================================================================\n")
    end
    
    println("Successfully generated network analysis text report: variance_analysis_report_$(clean_label).txt")
    # =========================================================================

    # --- Matrix Logic: Filter and Prep for Dynamic Thickness ---
    threshold = 0.2
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

    p_graph = graphplot(abs_weights_mat,
        x = x_coords,
        y = y_coords,
        names = fill("", n),           
        nodeshape = :rect,             
        markeralpha = 0.0,             
        markerstrokealpha = 0.0,       
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

    box_w = 4.5
    box_h = 1.5

    for i in 1:n
        x_c = x_coords[i]
        y_c = y_coords[i]
        
        rect = Shape(x_c .+ [-box_w/2, box_w/2, box_w/2, -box_w/2], 
                     y_c .+ [-box_h/2, -box_h/2, box_h/2, box_h/2])
        
        plot!(p_graph, rect, fillcolor=:white, linecolor=:black, label="")
        
        annotate!(p_graph, x_c, y_c, 
            text(display_names[i], font(16, "Computer Modern", :black, :center)))
    end

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
    
    out_name = "correlation_network_$(clean_label).png"
    savefig(p_graph, joinpath(post_process_dir, out_name))
    
    println("Successfully saved graph for: $scen_label to $out_name")
end

println("All scenarios processed successfully.")