using Statistics
using DataFrames
using Dates
using Base.Filesystem: basename
using CSV
using Base.Threads
using CategoricalArrays
using LaTeXStrings

# Makie replaces Plots and StatsPlots
using CairoMakie

include("../../../../../../src/postprocessing/julia/core/qcomparer_2023.jl")
include("../../../../../../src/postprocessing/julia/core/qslicer.jl")

obs = init_hainich_obs()

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
    joined_str = join(formatted_parts, " \\cdot ")
    return latexstring("\\mathrm{$(joined_str)}")
end

function to_datetime(y, d, h)
    return DateTime(y) + Day(d - 1) + Millisecond(round(h * 3600000))
end

function ensemble_2100_snapshots(df_vec::Vector{DataFrame}, scen_label, model_name::String, ssp_name::String)
    all_snapshots = DataFrame()
    
    for df in df_vec
        isempty(df) && continue
        
        # Filter specifically for the year 2100
        df_2100 = filter(:DateTime => d -> year(d) == 2100, df)
        isempty(df_2100) && continue
        
        # Extract the VERY LAST row of the year
        df_last_day = df_2100[end:end, :]
        
        # Format it for the DataFrame
        temp_df = DataFrame(
            Year = fill(2100, nrow(df_last_day)),
            Value = df_last_day.median, 
            Scenario = fill(scen_label, nrow(df_last_day)),
            Model = fill(model_name, nrow(df_last_day)),
            SSP = fill(ssp_name, nrow(df_last_day))
        )
        
        append!(all_snapshots, temp_df)
    end
    
    return all_snapshots
end

function read_input_df(root_output_folder)
    df = CSV.read(joinpath(root_output_folder , "climate.dat"), DataFrame, delim=' ', ignorerepeated=true, header=1, skipto=3)
    transform!(df, [:year, :doy, :hour] => ByRow(to_datetime) => :DateTime)
    return df
end

# --- 1. Setup ---
ide = "fig5_future_violin_makie_grouped"
var_avails = ["npp_avg", "total_veg_c"]
var_avails = ["gpp_avg", "qle_avg", "npp_avg", "total_veg_c"]
d1, d2 = DateTime("2020-01-01"), DateTime("2101-01-01")

rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/72_run_transient_3days_new_mort_new_phen_fix/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)

path_blue = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/ismip_selection_72"
path_red  = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/ismip_selection_72" 

# Notice "std" is removed entirely from this list as requested
scenarios = [
    (dir="df_psi_leaf_ind", label=L"\psi_{L}", id_filter=:all, ismip_base=path_blue),
    (dir="df_psi_stem_leaf_ind", label=L"\psi_{L} + \psi_{s}", id_filter=:all, ismip_base=path_blue),
    (dir="df_psi_stem_leaf_stem_flow_ind", label=L"\psi_{L} + \psi_{s} + J", id_filter=:all, ismip_base=path_red)
]

SSPS = ["ssp126", "ssp370", "ssp585"]
# Keep mpi-esm1-2 here so it is extracted and evaluated in the statistical summary CSV
MODELS = ["mri-esm2-0", "mpi-esm1-2", "ipsl-cm6a", "gfdl-esm4" ,"ukesm1-0"]

master_data_path = joinpath(post_process_dir, "master_data_2100.csv")
master_data = DataFrame()

# --- 2. Data Extraction / Caching Loop ---
if isfile(master_data_path)
    println("Found existing data cache! Loading from: $master_data_path")
    master_data = CSV.read(master_data_path, DataFrame)
else
    println("No cache found. Starting Data Extraction Loop...")
    for model in MODELS
        for ssp in SSPS
            for scen in scenarios
                println("Extracting Data for Model: $model | SSP: $ssp | Scenario: $(scen.label)")
                
                folder = "$(scen.ismip_base)_$(scen.dir)/$model/$ssp/output/"

                if !isdir(folder)
                    @warn "Directory not found: $folder"
                    continue
                end

                all_names = readdir(folder)
                indexes = filter(x -> isdir(joinpath(folder, x)), all_names)

                first_index = true
                qoutput = nothing
                cats = nothing
                sim_type_times = nothing
                run_collection = QMultiRunCollections(QOutputCollection[], String[])

                for i in indexes
                    i_str = string(i)
                    foldern = "$folder/$i_str"

                    if first_index 
                        qoutput = read_quincy_site_output(foldern)
                        cats = qoutput.cats
                        sim_type_times = qoutput.sim_type_times
                        first_index = false
                    else
                        qoutput = deepcopy(qoutput)
                        for sim_type_t in sim_type_times
                            for cat in cats
                                filename = joinpath(foldern, cat*"_"*sim_type_t*".nc")
                                qoutput.data[sim_type_t][cat].filename = filename 
                            end
                        end
                    end
                    push!(run_collection.idstr, i_str);
                    push!(run_collection.output, qoutput);
                end

                for var in var_avails
                    df_vec = get_multi_file_slice(run_collection, var, Fluxnetdata, DailySeries, 0.1, 0.9, slice_dates, d1, d2)
                    
                    df_snapshots = ensemble_2100_snapshots(df_vec, scen.label, model, ssp)
                    
                    if !isempty(df_snapshots)
                        df_snapshots.Variable .= var
                        append!(master_data, df_snapshots)
                    end
                end
            end
        end
    end
    
    # Save the extracted data so we don't have to extract it again
    println("Extraction complete. Saving to: $master_data_path")
    CSV.write(master_data_path, master_data)
end

# --- 3. Compute and Save Mean & Std (Grouped by Model as well) ---
println("Calculating mean and standard deviation per Variable, SSP, Model, and Scenario...")
if !isempty(master_data)
    # Ensure Scenario is a standard String for grouping to prevent issues when re-loading from CSV
    master_data.Scenario_String = string.(master_data.Scenario)

    # Model is placed before Scenario_String
    summary_df = combine(groupby(master_data, [:Variable, :SSP, :Model, :Scenario_String]), 
                         :Value => mean => :Mean, 
                         :Value => std => :Std)
    
    # Round Mean and Std columns to 2 significant digits
    transform!(summary_df, 
        :Mean => ByRow(x -> ismissing(x) || isnan(x) ? x : round(x, sigdigits=2)) => :Mean,
        :Std  => ByRow(x -> ismissing(x) || isnan(x) ? x : round(x, sigdigits=2)) => :Std
    )
    
    summary_path = joinpath(post_process_dir, "summary_stats_ssp_scenario_model.csv")
    CSV.write(summary_path, summary_df)
    println("Saved summary statistics (Model column first, 2 sig. digits) to: $summary_path")
else
    @warn "master_data is empty, skipping statistical summary."
end

# --- 4. Makie Plotting Routine ---
println("Starting Makie Plotting...")

# Filter out "mpi-esm1-2" dynamically for the plotting section layout
plot_models = filter(m -> m != "mpi-esm1-2", MODELS)

# Map remaining models and scenarios to integers so Makie can group and dodge them cleanly
model_mapping = Dict(m => i for (i, m) in enumerate(plot_models))
scen_mapping  = Dict(string(s.label) => i for (i, s) in enumerate(scenarios))

# Explicitly set the custom colors as requested
scen_colors   = [:blue, :brown, :red]

# Prepare Legend elements outside the loop so they can be injected into the 3rd plot
labels_display = [s.label for s in scenarios]
elements = [PolyElement(polycolor = scen_colors[i]) for i in 1:length(labels_display)]

for var in var_avails
    df_var = filter(:Variable => v -> v == var, master_data)
    
    # Only keep data belonging to the filtered plot models
    df_var = filter(:Model => m -> m in plot_models, df_var)
    isempty(df_var) && continue
    
    # Calculate global min/max for the current variable to unify ylims across SSPs
    ymin, ymax = minimum(df_var.Value), maximum(df_var.Value)
    yrange = ymax - ymin
    # Add 5% padding to top and bottom so the data doesn't clip boundaries tight
    global_ylims = (ymin - 0.05 * yrange, ymax + 0.05 * yrange)

   # Calculate global min/max for the current variable to unify ylims across SSPs
    ymin, ymax = minimum(df_var.Value), maximum(df_var.Value)
    yrange = ymax - ymin
    
    # SAFETY CHECK: Prevent (0.0, 0.0) limits if all values are zero
    global_ylims = if yrange == 0.0
        if ymin == 0.0
            (-0.1, 0.1)  # If data is completely zeroed out
        else
            (ymin - 0.1 * abs(ymin), ymin + 0.1 * abs(ymin)) # If data is uniform but non-zero
        end
    else
        # Standard 5% padding to top and bottom
        (ymin - 0.05 * yrange, ymax + 0.05 * yrange)
    end 

    # Convert categorical strings to indices for Makie plotting
    df_var.ModelInt = [model_mapping[m] for m in df_var.Model]
    df_var.ScenInt  = [scen_mapping[string(s)] for s in df_var.Scenario]

    # Create the figure container (Rows: Title, Axes)
    fig = Figure(size = (1600, 500), fontsize = 18, font="Computer Modern")
    
    for (col_idx, ssp) in enumerate(SSPS)
        df_ssp = filter(:SSP => s -> s == ssp, df_var)
        
        # Dynamically generate 'a', 'b', 'c' based on the column index
        panel_letter = string(Char(96 + col_idx))

        # Setup the 1x3 Axis layout with unified limits and panel labels
        ax = Axis(fig[1, col_idx], 
            title = "($panel_letter) $(uppercase(ssp))", 
            titlealign = :left,
            xlabel = "Model", 
            ylabel = col_idx == 1 ? L"\mathrm{veg.\ carbon \; [mol \cdot m^{-2}]}" : "",
            xticks = (1:length(plot_models), plot_models),
            xticklabelrotation = pi/6
        )
        ylims!(ax, global_ylims)
        
        isempty(df_ssp) && continue
        
        # Grouped violins
        violin!(ax, df_ssp.ModelInt, df_ssp.Value; 
            dodge = df_ssp.ScenInt,
            n_dodge = length(scenarios),
            color = [scen_colors[i] for i in df_ssp.ScenInt],
            strokecolor = :black,
            strokewidth = 1,
            show_median = true,
            mediancolor = :black,
            width = 0.5,
            scale = :width
        )

        # Inject the legend ONLY into the 3rd plot (SSP585)
        if col_idx == 3
            # :lt places it Top-Left. Use :rt for Top-Right if your data overlaps on the left
            axislegend(ax, elements, labels_display, "Scenarios", position = :rb, framevisible = false)
        end
    end
    
    # Super Title at the top
    Label(fig[0, :], "2100 Spread | Variable: $var", fontsize = 24, font=:bold)
    
    # Save output
    out_path = joinpath(post_process_dir, "makie_2100_grouped_violins_$(var).png")
    save(out_path, fig)
    println("Saved figure: $out_path")
end

println("Processing Complete.")