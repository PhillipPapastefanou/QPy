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

# Extractor function handles extracting yearly means cleanly
function extract_yearly_time_series(df_vec::Vector{DataFrame}, scen_label, model_name::String, ssp_name::String)
    all_ts = DataFrame()
    
    for (run_idx, df) in enumerate(df_vec)
        isempty(df) && continue
        
        df.Year = year.(df.DateTime)
        df_yearly = combine(groupby(df, :Year), :median => mean => :Value)
        
        temp_df = DataFrame(
            Year = df_yearly.Year,
            Value = df_yearly.Value, 
            Scenario = fill(scen_label, nrow(df_yearly)),
            Model = fill(model_name, nrow(df_yearly)),
            SSP = fill(ssp_name, nrow(df_yearly)),
            RunID = fill("$(model_name)_run$(run_idx)", nrow(df_yearly))
        )
        
        append!(all_ts, temp_df)
    end
    
    return all_ts
end

function read_input_df(root_output_folder)
    df = CSV.read(joinpath(root_output_folder , "climate.dat"), DataFrame, delim=' ', ignorerepeated=true, header=1, skipto=3)
    transform!(df, [:year, :doy, :hour] => ByRow(to_datetime) => :DateTime)
    return df
end

# --- 1. Setup ---
ide = "fig5_future_timeseries_yearly_makie"
var_avails = ["npp_avg", "total_veg_c"]
d1, d2 = DateTime("2020-01-01"), DateTime("2101-01-01")

rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/72_run_transient_3days_new_mort_new_phen_fix/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)

path_blue = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/ismip_selection_72"
path_red  = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/ismip_selection_72" 

scenarios = [
    (dir="df_psi_leaf_ind", label=L"\psi_{L}", id_filter=:all, ismip_base=path_blue),
    (dir="df_psi_stem_leaf_ind", label=L"\psi_{L} + \psi_{s}", id_filter=:all, ismip_base=path_blue),
    (dir="df_psi_stem_leaf_stem_flow_ind", label=L"\psi_{L} + \psi_{s} + J", id_filter=:all, ismip_base=path_red)
]

SSPS = ["ssp126"]
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
                df_ts = extract_yearly_time_series(df_vec, scen.label, model, ssp)
                
                if !isempty(df_ts)
                    df_ts.Variable .= var
                    append!(master_data, df_ts)
                end
            end
        end
    end
end

# --- 3. Save Raw Data as CSV ---
println("Saving Master Data to CSV...")
csv_path = joinpath(post_process_dir, "master_data_timeseries_yearly.csv")
CSV.write(csv_path, master_data)
println("Saved CSV to: $csv_path")

# --- 4. Makie Plotting Routine ---
println("Starting Makie Plotting...")

scen_colors  = [:blue, :brown, :red]
panel_labels = ["a)", "b)", "c)"]

for var in var_avails
    df_var = filter(:Variable => v -> v == var, master_data)
    isempty(df_var) && continue
    
    # --- Safe Imperative Anomaly Transformation ---
    # We build a fresh clean table for plotting to completely bypass broadcasting type issues
    df_plot = DataFrame()
    
    for run_group in groupby(df_var, [:Scenario, :RunID])
        run_df = copy(run_group)
        sort!(run_df, :Year)
        
        if var == "total_veg_c"
            # Explicitly pinpoint the starting year
            idx_2020 = findfirst(==(2020), run_df.Year)
            
            if idx_2020 !== nothing
                base_val = run_df.Value[idx_2020]
                run_df.Value = run_df.Value .- base_val
            else
                @warn "Run $(run_df.RunID[1]) is missing 2020. Shifting by first recorded value."
                run_df.Value = run_df.Value .- run_df.Value[1]
            end
        end
        append!(df_plot, run_df)
    end
    
    fig = Figure(size = (1800, 600), fontsize = 18, font="Computer Modern")
    
    for (col_idx, scen) in enumerate(scenarios)
        df_scen = filter(:Scenario => s -> s == scen.label, df_plot)
        
        if var == "total_veg_c"
            ylabel_str = col_idx == 1 ? L"\Delta \mathrm{veg.\ carbon \; [mol \cdot m^{-2}]}" : ""
        else
            ylabel_str = col_idx == 1 ? L"\mathrm{Value}" : "" 
        end

        ax = Axis(fig[1, col_idx], 
            title = "$(panel_labels[col_idx]) $(scen.label)", 
            xlabel = "Year", 
            ylabel = ylabel_str
        )
        
        isempty(df_scen) && continue
        
        # Plot every individual line cleanly. Each is now fully grounded at 0.0 in 2020.
        for run_df in groupby(df_scen, :RunID)
            lines!(ax, run_df.Year, run_df.Value; 
                #color = (scen_colors[col_idx], 0.25), 
                color = (:black, 0.25), 
                linewidth = 0.3
            )
        end
        
        # Calculate statistics directly from our fresh zeroed out lines
        df_stats = combine(groupby(df_scen, :Year), 
            :Value => median => :MedianValue,
            :Value => (x -> quantile(x, 0.2)) => :Q20,
            :Value => (x -> quantile(x, 0.9)) => :Q80
        )
        sort!(df_stats, :Year)
        
        band!(ax, df_stats.Year, df_stats.Q20, df_stats.Q80;
            color = (scen_colors[col_idx], 0.15)
        )
        
        lines!(ax, df_stats.Year, df_stats.Q20; 
            color = scen_colors[col_idx], 
            linewidth = 1.2,
            linestyle = :dash
        )
        lines!(ax, df_stats.Year, df_stats.Q80; 
            color = scen_colors[col_idx], 
            linewidth = 1.2,
            linestyle = :dash
        )

        lines!(ax, df_stats.Year, df_stats.MedianValue; 
            color = scen_colors[col_idx], 
            linewidth = 3.2
        )
    end
    
    title_prefix = var == "total_veg_c" ? "Anomaly (Relative to 2020)" : "Yearly Time Series"
    Label(fig[0, :], "SSP370 $title_prefix (2020-2100) | Variable: $var", fontsize = 24, font=:bold)
    
    elements = [LineElement(color = scen_colors[i], linewidth = 3.0) for i in 1:length(scen_colors)]
    Legend(fig[2, :], elements, ["Median " * s.label for s in scenarios], "Scenarios", orientation = :horizontal, framevisible = false)
    
    out_path = joinpath(post_process_dir, "makie_yearly_timeseries_$(var).png")
    save(out_path, fig)
    println("Saved figure: $out_path")
end

println("Processing Complete.")