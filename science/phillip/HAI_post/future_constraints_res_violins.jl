using Statistics, VectorizedStatistics
using DataFrames
using Dates
using Base.Filesystem: basename
using CSV
using Base.Threads
using Plots
using LaTeXStrings
using StatsPlots
using CategoricalArrays # Needed to lock in X-axis and Scenario order

include("../../../src/postprocessing/julia/core/qcomparer_2023.jl")
include("../../../src/postprocessing/julia/core/qslicer.jl")

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

# --- NEW FUNCTION: Bin data into 15-year intervals ---
function ensemble_last_day_snapshots(df_vec::Vector{DataFrame}, scen_label::AbstractString)
    target_years = [2025, 2040, 2055, 2070, 2085, 2100]
    all_snapshots = DataFrame()
    
    for df in df_vec
        isempty(df) && continue
        
        # 1. Filter to only the years we care about
        df_years = filter(:DateTime => d -> year(d) in target_years, df)
        isempty(df_years) && continue
        
        # 2. Add a Year column for grouping
        df_years.Year = year.(df_years.DateTime)
        
        # 3. Group by Year, and extract the VERY LAST row of each year
        df_last_days = combine(groupby(df_years, :Year)) do sub_df
            return sub_df[end:end, :] # [end:end, :] returns the last row as a DataFrame
        end
        
        # 4. Format it for our Violin Plotting routine
        temp_df = DataFrame(
            Bin = string.(df_last_days.Year),
            BinStart = df_last_days.Year,
            # Note: Assuming your value column is still named 'median' from qslicer
            Value = df_last_days.median, 
            Scenario = fill(scen_label, nrow(df_last_days))
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

function calculate_vpd(t_k, q_gkg, p_hpa)
    t_c = t_k - 273.15
    es = 0.61078 * exp((17.27 * t_c) / (t_c + 237.3))
    q_kgkg = q_gkg / 1000.0
    p_kpa = p_hpa / 10.0
    ea = (q_kgkg * p_kpa) / (0.622 + 0.378 * q_kgkg)
    return max(0.0, es - ea)
end

# --- 1. Setup ---
ide = "future_violin_std"
colors = [:blue, :purple, :red]
#var_avails = ["total_veg_c","psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
var_avails = ["total_veg_c"]
d1, d2 = DateTime("2020-01-01"), DateTime("2101-01-01")

rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/63_run_transient_3days/output"
rt_path_std = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/63_run_transient_3days/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)

ismip_path = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/ismip_selection_63"
ismip_path_std = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/ismip_selection_58"

scenarios = [
    (dir="df_std_ind", label="std", id_filter=[0]),
    (dir="df_ind", label=L"U", id_filter=:all),
    (dir="df_psi_stem_leaf_stem_flow_ind", label=L"\psi_{s} + \psi_{L} + J", id_filter=:all)
]


series = DailySeries
SSPS = ["ssp126", "ssp370", "ssp585"]
MODELS = ["mri-esm2-0", "mpi-esm1-2", "ipsl-cm6a", "gfdl-esm4" ,"ukesm1-0"]

# --- 2. Main Execution Loop ---
for model in MODELS
    for ssp in SSPS
        
        # We will cache the extracted DataFrames here
        yearly_data = Dict{String, Dict{String, DataFrame}}()
        for var in var_avails
            yearly_data[var] = Dict{String, DataFrame}()
        end

        # Phase A: Data Extraction
        for (scen_folder, scen_label, id_filter) in scenarios
            println("Extracting Data for Model: $model | SSP: $ssp | Scenario: $scen_label")
            
                if id_filter == :all
                    folder = "$(ismip_path)_$scen_folder/$model/$ssp/output/"
                else
                    folder = "$(ismip_path_std)_$scen_folder/$model/$ssp/output/"
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
                
                # Extract the last day across all members to build the distribution
                df_snapshots = ensemble_last_day_snapshots(df_vec, scen_label)
                
                println("  Processed $var")
                yearly_data[var][scen_label] = df_snapshots
            end
        end

        # Phase B: Violin Plotting Routine
# Phase B: Violin Plotting Routine
        for var in var_avails
            println("Plotting building steps for Variable: $var")
            
            # 1. Combine all available scenarios for this variable into one master DataFrame
            dfs = [yearly_data[var][s[2]] for s in scenarios if haskey(yearly_data[var], s[2])]
            isempty(dfs) && continue
            df_all = vcat(dfs...)
            
            # 2. Lock in Categories so layout and colors never shuffle
            scen_order = [s[2] for s in scenarios]
            df_all.Scenario = categorical(df_all.Scenario, levels=scen_order)
            
            bin_levels = unique(sort(df_all, :BinStart).Bin)
            df_all.Bin = categorical(df_all.Bin, levels=bin_levels)

            # 3. The Build-up Loop
            for i in 1:length(scenarios)
                visible_scens = [s[2] for s in scenarios[1:i]]
                
                # MASKING TRICK 2.0: Transparency and Dynamic Labels
                # If a scenario is in 'visible_scens', it gets an alpha of 0.7 and a label.
                # If it's a "future" scenario, it gets an alpha of 0.0 (invisible) and an empty label ("").
                c_alphas = [s in visible_scens ? 0.7 : 0.0 for s in scen_order]
                c_lines  = [s in visible_scens ? 1.0 : 0.0 for s in scen_order]
                c_labels = [s in visible_scens ? s   : ""  for s in scen_order]
                
                # Plot grouped violins
                p = groupedviolin(
                    df_all.Bin,             # The 15-year interval bins
                    df_all.Value,
                    group = df_all.Scenario,
                    color = reshape(colors, 1, :),
                    fillalpha = reshape(c_alphas, 1, :),   
                    linealpha = reshape(c_lines, 1, :),    
                    label = reshape(c_labels, 1, :),       
                    title = "Building Scenarios: $var ($model - $ssp)\nStep $i",
                    xlabel = "15-Year Interval",
                    ylabel = "Value",
                    legend = :outertopright,
                    size = (1400, 700),
                    grid = true,
                    fontfamily = "Computer Modern",
                    framestyle = :box,
                    linewidth = 1,
                    trim = true,
                    spacing = 0.1 # Optional: controls the gap between the violins in a group
                )

                # Save step
                step_name = "future_step_$(i)_$(var)_$(model)_$(ssp).png"
                savefig(p, joinpath(post_process_dir, step_name))
                println("  Saved step $i (Added: $(visible_scens[end]))")
            end
        end
        println("Completed processing for $model - $ssp.")
    end
end