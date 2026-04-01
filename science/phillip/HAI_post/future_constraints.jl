
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

    # 1. Handle "micro" prefixes
    # We replace it with \mu{} so LaTeX separates the macro from the next letters 
    # (e.g., \mu{}mol prevents it from looking for a non-existent \mumol command)
    s = replace(unit_str, "micro " => "\\mu{}")
    s = replace(s, "micro" => "\\mu{}")
    
    # 2. Split the string into individual units based on spaces
    parts = split(s, " ", keepempty=false)
    
    formatted_parts = String[]
    
    for part in parts
        # Regex explanation:
        # ^([A-Za-z\\]+)  -> Captures the base (letters or slashes for \mu)
        # (-?\d+)$        -> Captures the exponent (optional minus sign, then numbers)
        m = match(r"^([A-Za-z\\]+)(-?\d+)$", part)
        
        if m !== nothing
            # If it has an exponent, format it as base^{exponent}
            base = m.captures[1]
            exponent = m.captures[2]
            push!(formatted_parts, "$(base)^{$(exponent)}")
        else
            # If no exponent is found, leave it as is (e.g., "mol", "MPa")
            push!(formatted_parts, part)
        end
    end
    
    # 3. Join everything together with the center dot
    joined_str = join(formatted_parts, " \\cdot ")
    
    # 4. Wrap the whole thing in \mathrm{} to keep the font upright
    final_latex_string = "\\mathrm{$(joined_str)}"
    
    # Convert and return as a LaTeXString
    return latexstring(final_latex_string)
end

# Function to convert Year, DOY, and Decimal Hour to DateTime
function to_datetime(y, d, h)
    # DateTime(year, month, day) + Day offset + Hour offset
    # We use d-1 because January 1st is Day 1
    return DateTime(y) + Day(d - 1) + Millisecond(round(h * 3600000))
end

function seasonal_yearly(df)
    df_season = filter(r -> month(r.DateTime) in 5:9, df)
    df_season.year = year.(df_season.DateTime)

    df_yearly = combine(
        groupby(df_season, :year),
        :median => mean => :median,
        :qlow   => mean => :qlow,
        :qup    => mean => :qup
    )

    df_yearly.DateTime = Date.(df_yearly.year, 1, 1)
    return df_yearly
end

function read_input_df(root_output_folder)

    df  =  CSV.read(joinpath(root_output_folder , "climate.dat"), DataFrame, delim=' ', ignorerepeated=true,header=1, 
              skipto=3)

    transform!(df, [:year, :doy, :hour] => ByRow(to_datetime) => :DateTime)

    return df
end


function calculate_vpd(t_k, q_gkg, p_hpa)
    # 1. Convert Kelvin to Celsius
    t_c = t_k - 273.15
    
    # 2. Saturation Vapor Pressure (es) in kPa
    # Tetens formula constants for water
    es = 0.61078 * exp((17.27 * t_c) / (t_c + 237.3))
    
    # 3. Actual Vapor Pressure (ea) in kPa
    # Convert q from g/kg to kg/kg
    q_kgkg = q_gkg / 1000.0
    # Convert Pressure from hPa to kPa
    p_kpa = p_hpa / 10.0
    
    # ea = (q * P) / (ε + (1 - ε)q) where ε ≈ 0.622
    ea = (q_kgkg * p_kpa) / (0.622 + 0.378 * q_kgkg)
    
    # 4. VPD is the difference (ensure it's not negative due to sensor noise)
    return max(0.0, es - ea)
end



ide = "future"
colors = [:purple, :blue, :green, :red]
var_avails =  ["npp_avg", "total_veg_c", "gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
d1, d2 = DateTime("2020-01-01"), DateTime("2101-01-01")


# --- 1. Setup ---
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/63_run_transient_3days/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)

ismip_path = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/ismip_selection_63"

# Define the scenarios and their display labels
scenarios = [
    "df_ind" => "Ind",
    "df_psi_stem_ind" => "Psi Stem",
    "df_psi_stem_leaf_ind" => "Psi Leaf",
    "df_psi_stem_leaf_stem_flow_ind" => "Flow"
]


series = DailySeries

# We will store the processed data here: Dict{Variable -> Dict{Scenario -> (daily_df, diurnal_df)}}
all_data = Dict()

SSPS = ["ssp126", "ssp370", "ssp585"]
MODELS = ["mri-esm2-0","mpi-esm1-2", "ipsl-cm6a", "gfdl-esm4" ,"ukesm1-0"]

for model in [MODELS[1]]
    for ssp in [SSPS[1]]

        start_time = time()
        last_report = start_time

        first_index = true
        qoutput = nothing
        cats = nothing
        sim_type_times=nothing
        run_collection= QMultiRunCollections(QOutputCollection[], String[])

        scenfolder = scenarios[1][1]
        folder = "$(ismip_path)_$scenfolder/$model/$ssp/output/"

        # Get all names in the directory
        all_names = readdir(folder)

        # Filter to ensure you only get directories (and exclude hidden files if any)
        indexes = filter(x -> isdir(joinpath(folder, x)), all_names)

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
                #We need to override the file paths
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
            @time df = get_multi_file_slice(run_collection, var, Fluxnetdata, DailySeries, 0.1, 0.9, slice_dates, d1, d2 )
            dfy = seasonal_yearly(df)
        end
    end
end