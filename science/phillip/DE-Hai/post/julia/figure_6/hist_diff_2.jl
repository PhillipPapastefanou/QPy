using Statistics
using DataFrames
using Dates
using Base.Filesystem: basename
using CSV
using Base.Threads
using CategoricalArrays

# Makie replaces Plots and StatsPlots
using CairoMakie
using LaTeXStrings

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
ide = "fig6_future_timeseries_yearly_indiv_diff"
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

# Updated to run all three scenarios
SSPS = ["ssp126", "ssp370", "ssp585"]
#MODELS = ["mri-esm2-0", "mpi-esm1-2", "ipsl-cm6a", "gfdl-esm4" ,"ukesm1-0"]
MODELS = ["mri-esm2-0","ipsl-cm6a", "gfdl-esm4" ,"ukesm1-0"]
MODELS = ["mri-esm2-0", "gfdl-esm4" ,"ukesm1-0"]

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

# 5 distinctive colors for the 5 models
model_colors = [:dodgerblue, :firebrick, :forestgreen, :darkorange, :mediumpurple]
panel_labels = ["a)", "b)", "c)"]

for var in var_avails
    df_var = filter(:Variable => v -> v == var, master_data)
    isempty(df_var) && continue
    
    # --- Safe Year-to-Year Change Transformation ---
    df_plot = DataFrame()
    # It is critical to group by SSP here as well, so years don't overlap across scenarios during diff
    for run_group in groupby(df_var, [:SSP, :Scenario, :RunID])
        run_df = copy(run_group)
        sort!(run_df, :Year)
        
        if var == "total_veg_c"
            run_df.Value = vcat(0.0, diff(run_df.Value))
        end
        append!(df_plot, run_df)
    end
    
    # --- Loop over each SSP to generate dedicated figures ---
    for ssp in SSPS
        df_ssp = filter(:SSP => s -> s == ssp, df_plot)
        isempty(df_ssp) && continue

        # Global fontsize makes text highly readable
        fig = Figure(size = (1800, 600), fontsize = 20, font="Computer Modern")
        axes_list = Axis[]
        
        if var == "total_veg_c"
            xlabel_str = L"\Delta \mathrm{veg.\ carbon \; [mol \cdot m^{-2} \cdot yr^{-1}]}"
        else
            xlabel_str = L"\mathrm{Value}"
        end
        
        for (col_idx, scen) in enumerate(scenarios)
            df_scen = filter(:Scenario => s -> s == scen.label, df_ssp)
            title_str = L"\text{%$(panel_labels[col_idx]) }\ %$(scen.label)"

            if col_idx == 1
                ax = Axis(fig[1, col_idx], 
                    title = title_str, 
                    xlabel = xlabel_str, 
                    ylabel = "Density", # Changed to Density to reflect normalization
                    titlesize = 24, xlabelsize = 22, ylabelsize = 22
                )
            else
                ax = Axis(fig[1, col_idx], 
                    title = title_str, 
                    xlabel = xlabel_str,
                    titlesize = 24, xlabelsize = 22
                )
            end
            
            push!(axes_list, ax)
            isempty(df_scen) && continue
            
            for (m_idx, model) in enumerate(MODELS)
                df_model = filter(:Model => m -> m == model, df_scen)
                isempty(df_model) && continue
                
                # Filled Histograms with transparency and a solid stroke
                hist!(ax, df_model.Value; 
                    color = (model_colors[m_idx], 0.35), # 35% opacity fill
                    strokecolor = model_colors[m_idx],   # Solid border
                    strokewidth = 1.5,
                    bins = 40,
                    normalization = :pdf # Normalizes area so distributions overlap fairly
                )
            end
        end
        
        if length(axes_list) == 3
            linkxaxes!(axes_list[1], axes_list[2], axes_list[3])
            linkyaxes!(axes_list[1], axes_list[2], axes_list[3])
        end
        
        title_prefix = var == "total_veg_c" ? "Annual Interannual Change Distribution" : "Value Distribution"
        Label(fig[0, :], "$(uppercase(ssp)) $title_prefix (2020-2100) | Variable: $var", fontsize = 28, font=:bold)
        
        # Switched Legend to PolyElement to match the filled histograms
        elements = [PolyElement(polycolor = (model_colors[i], 0.35), strokecolor = model_colors[i], strokewidth = 1.5) for i in 1:length(MODELS)]
        Legend(fig[2, :], elements, MODELS, "Models", orientation = :horizontal, framevisible = false, labelsize = 20)
        
        # Save output with SSP explicitly in the filename
        out_path = joinpath(post_process_dir, "makie_histogram_per_model_$(var)_$(ssp).png")
        save(out_path, fig)
        println("Saved figure: $out_path")
    end
end

println("Processing Complete.")