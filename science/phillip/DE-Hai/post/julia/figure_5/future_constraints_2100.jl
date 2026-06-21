using Statistics
using DataFrames
using Dates
using Base.Filesystem: basename
using CSV
using Base.Threads
using CategoricalArrays

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
MODELS = ["mri-esm2-0", "mpi-esm1-2", "ipsl-cm6a", "gfdl-esm4" ,"ukesm1-0"]

master_data = DataFrame()

# --- 2. Data Extraction Loop ---
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

# --- 3. Makie Plotting Routine ---
println("Starting Makie Plotting...")

# Map models and scenarios to integers so Makie can group and dodge them
model_mapping = Dict(m => i for (i, m) in enumerate(MODELS))
scen_mapping  = Dict(s.label => i for (i, s) in enumerate(scenarios))

# Explicitly set the custom colors as requested
scen_colors   = [:blue, :brown, :red]

for var in var_avails
    df_var = filter(:Variable => v -> v == var, master_data)
    isempty(df_var) && continue
    
    # Convert categorical strings to indices for Makie plotting
    df_var.ModelInt = [model_mapping[m] for m in df_var.Model]
    df_var.ScenInt  = [scen_mapping[s] for s in df_var.Scenario]

    # Create the figure container (Rows: Title, Axes, Legend)
    fig = Figure(size = (1800, 700), fontsize = 18, font="Computer Modern")
    
    for (col_idx, ssp) in enumerate(SSPS)
        df_ssp = filter(:SSP => s -> s == ssp, df_var)
        
        # Setup the 1x3 Axis layout
        ax = Axis(fig[1, col_idx], 
            title = uppercase(ssp), 
            xlabel = "Model", 
            ylabel = col_idx == 1 ? L"\mathrm{veg.\ carbon \; [mol \cdot m^{-2}]}" : "",
            xticks = (1:length(MODELS), MODELS),
            xticklabelrotation = pi/6
        )
        
        isempty(df_ssp) && continue
        
        # Grouped violins! 'x' is the Model, 'dodge' handles side-by-side scenarios
        # n_dodge forces equal width rendering for all scenarios even if missing
        violin!(ax, df_ssp.ModelInt, df_ssp.Value; 
            dodge = df_ssp.ScenInt,
            n_dodge = length(scenarios),
            color = [scen_colors[i] for i in df_ssp.ScenInt],
            strokecolor = :black,
            strokewidth = 1,
            show_median = true,
            mediancolor = :black
        )
    end
    
    # Super Title at the top
    Label(fig[0, :], "2100 Spread | Variable: $var", fontsize = 24, font=:bold)
    
    # Shared Legend at the bottom
    labels = [s.label for s in scenarios]
    elements = [PolyElement(polycolor = scen_colors[i]) for i in 1:length(labels)]
    Legend(fig[2, :], elements, labels, "Scenarios", orientation = :horizontal, framevisible = false)
    
    # Save output
    out_path = joinpath(post_process_dir, "makie_2100_grouped_violins_$(var).png")
    save(out_path, fig)
    println("Saved figure: $out_path")
end

println("Processing Complete.")