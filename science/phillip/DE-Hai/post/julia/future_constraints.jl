using Statistics, VectorizedStatistics
using DataFrames
using Dates
using Base.Filesystem: basename
using CSV
using Base.Threads
using Plots
using LaTeXStrings
using StatsPlots

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

function seasonal_yearly(df)
    # 1. Filter for summer months (May to September)
    # This syntax is much faster and avoids the "Vector + Int" error
    df_season = filter(:DateTime => d -> month(d) in 5:9, df)
    
    # 2. Extract the year
    df_season.year = year.(df_season.DateTime)

    # 3. Aggregate
    df_yearly = combine(
        groupby(df_season, :year),
        :median => mean => :median,
        :qlow   => mean => :qlow,
        :qup    => mean => :qup
    )

    return df_yearly
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
ide = "future"
colors = [:purple, :blue, :green, :red]
var_avails = ["npp_avg", "total_veg_c", "gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
var_avails = ["total_veg_c","psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
d1, d2 = DateTime("2020-01-01"), DateTime("2101-01-01")

rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/63_run_transient_3days/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)

ismip_path = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/ismip_selection_63"

scenarios = [
    "df_ind" => "U",
    "df_psi_stem_ind" => L"\psi_{s}",
    "df_psi_stem_leaf_ind" => L"\psi_{s} + \psi_{L}",
    "df_psi_stem_leaf_stem_flow_ind" => L"\psi_{s} + \psi_{L} + J"
]

series = DailySeries
SSPS = ["ssp126", "ssp370", "ssp585"]
MODELS = ["mri-esm2-0", "mpi-esm1-2", "ipsl-cm6a", "gfdl-esm4" ,"ukesm1-0"]

# --- 2. Main Execution Loop ---
for model in MODELS
    for ssp in SSPS
        
        # Dictionary to cache our yearly data before plotting: Dict[var][scen_label] = dfy
        yearly_data = Dict{String, Dict{String, DataFrame}}()
        for var in var_avails
            yearly_data[var] = Dict{String, DataFrame}()
        end

        # Phase A: Data Extraction
        for (scen_folder, scen_label) in scenarios
            println("Extracting Data for Model: $model | SSP: $ssp | Scenario: $scen_label")
            
            folder = "$(ismip_path)_$scen_folder/$model/$ssp/output/"
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
                # Note: Assuming slice_dates is defined elsewhere in your workspace
                df = get_multi_file_slice_avg(run_collection, var, Fluxnetdata, DailySeries, 0.1, 0.9, slice_dates, d1, d2)
                dfy = seasonal_yearly(df)
                println(var)
                # Store the processed yearly dataframe
                yearly_data[var][scen_label] = dfy
            end
        end

        # Phase B: Plotting Routine
for var in var_avails
    println("Plotting building steps for Variable: $var")
    
    # Initialize a base plot for this variable
    p = plot(
        title = "Building Scenarios: $var ($model - $ssp)",
        xlabel = "Year",
        ylabel = "Value",
        legend = :outertopright,
        size = (1200, 600),
        grid = true,
        fontfamily = "Computer Modern",
        framestyle = :box,
        # Ensure the Y-axis is fixed across all 4 plots for consistency
        # We find the min/max across all scenarios for this variable first
        ylims = :auto 
    )

    # Loop through the scenarios to add them one by one
    for (idx, (scen_folder, scen_label)) in enumerate(scenarios)
        if haskey(yearly_data[var], scen_label)
            dfy = yearly_data[var][scen_label]
            
            # Calculate ribbon relative distances
            lower_err = dfy.median .- dfy.qlow
            upper_err = dfy.qup .- dfy.median

            # Add the current scenario to the existing plot 'p'
            plot!(p, dfy.year, dfy.median,
                ribbon = (lower_err, upper_err),
                fillalpha = 0.2,
                linewidth = 3,         # Slightly thicker for visibility
                color = colors[idx],
                label = scen_label
            )

            # SAVE STEP: Save the plot at its current state (idx 1, then 1+2, etc.)
            step_name = "future_step_$(idx)_$(var)_$(model)_$(ssp).png"
            savefig(p, joinpath(post_process_dir, step_name))
            println("  Saved step $idx: $scen_label")
        end
    end
end
        
        println("Completed processing for $model - $ssp.")
    end
end