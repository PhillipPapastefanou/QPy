
using Statistics, VectorizedStatistics
using DataFrames
using Dates
using Base.Filesystem: basename
using CSV
using Base.Threads
using Plots
using LaTeXStrings
using StatsPlots

include("../../../../../../src/postprocessing/julia/core/qcomparer_2023.jl")
include("../../../../../../src/postprocessing/julia/core/qslicer.jl")


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






# ide = "sum23"
# colors = [:purple, :blue, :green, :red]
# var_avails=  ["gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
# target_midday_1 = DateTime("2023-06-01T12:00:00")
# target_midday_2 = DateTime("2023-07-20T12:00:00")
# d1, d2 = DateTime("2023-05-15"), DateTime("2023-09-30")

# ide = "sum03"
# colors = [:purple, :blue, :green, :red]
# var_avails=  ["gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
# target_midday_1 = DateTime("2003-06-01T12:00:00")
# target_midday_2 = DateTime("2003-08-05T12:00:00")
# d1, d2 = DateTime("2003-05-15"), DateTime("2003-09-30")

ide = "f_sum2003_obs"
colors = [:red, :black, :blue]
var_avails=  ["qle_avg", "gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
target_midday_1 = DateTime("2003-06-01T12:00:00")
target_midday_2 = DateTime("2003-08-05T12:00:00")
d1, d2 = DateTime("2003-08-01"), DateTime("2003-09-01")


# ide = "f_sum2018_obs"
# colors = [:red, :black, :blue]
# # Note: "qle_avg" is removed here based on your commented-out 2018 code
# var_avails = ["qle_avg", "gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
# target_midday_1 = DateTime("2018-06-01T12:00:00")
# target_midday_2 = DateTime("2018-08-05T12:00:00")
# d1, d2 = DateTime("2018-05-15"), DateTime("2018-09-30")


# ide = "f_sum2023_obs"
# colors = [:red, :black, :blue]
# var_avails = ["qle_avg", "gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
# target_midday_1 = DateTime("2023-06-01T12:00:00")
# target_midday_2 = DateTime("2023-07-20T12:00:00")
# d1, d2 = DateTime("2023-05-22"), DateTime("2023-08-01")


obs = init_hainich_obs()
df_fnet_22 = obs.df_fnet_22
df_fnet_24 = obs.df_fnet_24
df_psi_stem_obs = obs.df_psi_stem_obs
df_psi_leaf_obs = obs.df_psi_leaf_obs
df_sap_flow_2023 = obs.df_sap_flow_2023


# ide = "sum2023_obs"
# colors = [:red, :black, :blue]
# var_avails=  ["qle_avg", "gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
# d1, d2 = DateTime("2023-05-22"), DateTime("2023-08-01")


# ide = "sum2018_obs"
# colors = [:red, :black, :blue]
# var_avails=  ["gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
# target_midday_1 = DateTime("2018-06-01T12:00:00")
# target_midday_2 = DateTime("2018-08-05T12:00:00")
# d1, d2 = DateTime("2018-05-15"), DateTime("2018-09-30")

rt_path_std = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/68_run_transient_3days_new_mort_new_phen_fix/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)

# Define the scenarios with a specific ID filter
scenarios = [
    (dir="df_psi_stem_leaf_stem_flow_ind", label=L"\psi_{s} + \psi_{L} + J", id_filter=:all),
    (dir="df_ind", label="std", id_filter=[0])
]

series = ThirtyMinSeries

df_fnet = ""
if year(d1) < 2022
    df_fnet =    df_fnet_22  
else
    df_fnet =    df_fnet_24        
end

df_obs_gpp_slice = get_single_file_slice(df_fnet, "GPP", series, 0.05, 0.95,
slice_dates, 
d1, d2 )
df_obs_le_slice = get_single_file_slice(df_fnet, "LE", series, 0.05, 0.95,
slice_dates, 
d1, d2)
df_obs_le_slice.mean .= -df_obs_le_slice.mean

if year(d1) == 2023
    df_obs_sapflow_slice = get_single_file_slice(df_sap_flow_2023, "Ji_Fasy", series, 0.1, 0.9, slice_dates,
    d1, d2 )

    series = ThirtyMinSeries

    df_obs_psi_stem_slice = get_single_file_slice(df_psi_stem_obs, "FAG", series, 0.25, 0.75,slice_dates, 
    d1, d2 )    
    df_obs_psi_leaf_slice = get_single_file_slice(df_psi_leaf_obs, "psi_leaf_midday_avg", series, 0.25, 0.75, slice_dates, 
    d1, d2)    
end


# We will store the processed data here: Dict{Variable -> Dict{Scenario -> (daily_df, diurnal_df)}}
all_data = Dict()

# --- 2. Data Processing Loop ---
# This part runs for every scenario to collect the data first
for scen in scenarios
# Determine which IDs to load based on the scenario filter
    if scen.id_filter == :all
        ids_file = joinpath(rt_path_hyd, "../post/ana", "$(scen.dir).csv")
        ids = CSV.read(ids_file, DataFrame)[!, :fid]
    else
        ids = scen.id_filter
    end



    full_dir_paths = [joinpath(rt_path_hyd, string(id)) for id in ids]
    
    println(full_dir_paths)

    first_index = true
    qoutput = nothing
    cats = nothing
    sim_type_times=nothing
    qcol = QMultiRunCollections(QOutputCollection[], String[])

    full_dir_paths
    for fstr in full_dir_paths
        if first_index 
            qoutput = read_quincy_site_output(fstr)
            cats = qoutput.cats
            sim_type_times = qoutput.sim_type_times
            first_index = false
        else
            qoutput = deepcopy(qoutput)
            #We need to override the file paths
            for sim_type_t in sim_type_times
                for cat in cats
                    filename = joinpath(fstr, cat*"_"*sim_type_t*".nc")
                    qoutput.data[sim_type_t][cat].filename = filename 
                end
            end

        end
        #push!(run_collections_new.idstr, i_str);
        push!(qcol.output, qoutput);
        #last_report = progress_report(i, ids[end], start_time, last_report)
    end

    # for variable in var_avails
    #     df = get_multi_file_slice_avg(qcol, variable, Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2)

    #     # Daily Aggregation
    #     df.DateOnly = Date.(df.DateTime)
    #     df_daily = combine(groupby(df, :DateOnly), [:mean, :qlow, :qup] .=> mean .=> [:mean, :qlow, :qup])
        
    #     # Diurnal Aggregation
    #     df.Hour = hour.(df.DateTime) .+ minute.(df.DateTime) ./ 60
    #     df_diurnal = combine(groupby(df, :Hour), [:mean, :qlow, :qup] .=> mean .=> [:mean, :qlow, :qup])
    #     sort!(df_diurnal, :Hour)
        
    #     # Store metadata and data
    #     if !haskey(all_data, variable)
    #                 all_data[variable] = Dict{String, Any}()
    #                 all_data[variable]["unit"] = format_unit_to_latex(get_unit(qcol.output[1], variable))
    #                 all_data[variable]["violin_data_1"] = Dict{String, Vector{Float64}}()
    #                 all_data[variable]["violin_data_2"] = Dict{String, Vector{Float64}}()
    #     end
    #     all_data[variable][scen_name] = (daily = df_daily, diurnal = df_diurnal)


    #     all_data[variable]["violin_data_1"][scen_name] = df[df.DateOnly .== target_midday_1, :mean]
    #     all_data[variable]["violin_data_2"][scen_name] = df[df.DateOnly .== target_midday_2, :mean]
    # end


    for variable in var_avails
        # 1. Get the Vector of DataFrames (one per run)
        df_list = get_multi_file_slice(qcol, variable, Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2)
        
        # 2. Join all DataFrames into one "Wide" DataFrame
        # We assume each df in df_list has columns [:DateTime, :mean] 
        # (where :mean is the value for that specific run)
        df_ensemble = rename(df_list[1], :mean => "run_1")
        for idx in 2:length(df_list)
            next_df = rename(df_list[idx], :mean => "run_$(idx)")
            df_ensemble = outerjoin(df_ensemble, next_df, on = :DateTime, makeunique=true)
        end
        
        # 3. Calculate Mean, Q10, and Q90 across the rows (the "ensemble")
        # Identify the columns that contain data (all except DateTime)
        val_cols = names(df_ensemble, Not(:DateTime))
        
        # Create the summary DataFrame (df)
        df = transform(df_ensemble, val_cols => ByRow((vals...) -> begin
            # Clean out NaNs/Missings for this specific timestamp
            clean_vals = filter(v -> !ismissing(v) && !isnan(v), [vals...])
            
            if isempty(clean_vals)
                return (mean=NaN, qlow=NaN, qup=NaN, raw=Float64[])
            end
            
            return (
                mean = mean(clean_vals),
                qlow = quantile(clean_vals, 0.1),
                qup  = quantile(clean_vals, 0.9),
                raw  = clean_vals # Stored for the violin plots
            )
        end) => AsTable)

        # 4. Daily Aggregation (Same logic as before)
        df.DateOnly = Date.(df.DateTime)
        df_daily = combine(groupby(df, :DateOnly), 
            [:mean, :qlow, :qup] .=> mean .=> [:mean, :qlow, :qup])
        
        # 5. Diurnal Aggregation
        df.Hour = hour.(df.DateTime) .+ minute.(df.DateTime) ./ 60
        df_diurnal = combine(groupby(df, :Hour), 
            [:mean, :qlow, :qup] .=> mean .=> [:mean, :qlow, :qup])
        sort!(df_diurnal, :Hour)
        
        # 6. Store in all_data
        if !haskey(all_data, variable)
            all_data[variable] = Dict{String, Any}()
            all_data[variable]["unit"] = format_unit_to_latex(get_unit(qcol.output[1], variable))
            all_data[variable]["violin_data_1"] = Dict{String, Vector{Float64}}()
            all_data[variable]["violin_data_2"] = Dict{String, Vector{Float64}}()
        end
        all_data[variable][scen.label] = (daily = df_daily, diurnal = df_diurnal)

        # 1. Identify which columns contain the ensemble data (everything except DateTime)
        val_cols = names(df_ensemble, Not(:DateTime))



        # --- B. Process Observational Data (If applicable) ---
        obs_df_raw = if variable == "gpp_avg"
            df_obs_gpp_slice
        elseif variable == "qle_avg" && @isdefined(df_obs_le_slice)
            df_obs_le_slice
        elseif variable == "stem_flow_per_sap_area_avg" && @isdefined(df_obs_sapflow_slice)
            df_obs_sapflow_slice
        elseif variable == "psi_stem_avg" && @isdefined(df_obs_psi_stem_slice)
            df_obs_psi_stem_slice
        elseif variable == "psi_leaf_avg" && @isdefined(df_obs_psi_leaf_slice)
            df_obs_psi_leaf_slice
        else
            nothing
        end

        if obs_df_raw !== nothing
            obs_clean = dropmissing(obs_df_raw, :mean)
            obs_clean.DateOnly = Date.(obs_clean.DateTime)
            obs_daily = combine(groupby(obs_clean, :DateOnly), :mean => mean => :mean)
            
            obs_clean.Hour = hour.(obs_clean.DateTime) .+ minute.(obs_clean.DateTime) ./ 60
            obs_diurnal = combine(groupby(obs_clean, :Hour), :mean => mean => :mean)
            sort!(obs_diurnal, :Hour)
            
            all_data[variable]["Obs"] = (daily = obs_daily, diurnal = obs_diurnal)
        end

    end
end

all_data["gpp_avg"]["Obs"]

presentation_style = (
    fontfamily = "Computer Modern",
    guidefontsize = 18,    # Axis labels (GPP, Hour, etc.)
    tickfontsize = 14,     # Axis numbers
    titlefontsize = 22,    # Plot titles
    legendfontsize = 14,   # Legend text
    linewidth = 2.5,       # Thicker lines for visibility
    grid = true,
    gridalpha = 0.2
)

for variable in var_avails
    unit_label = all_data[variable]["unit"]
    
    l = @layout [a{0.67w} b]
    final_plot = plot(layout=l, size=(1400, 500), margin=12Plots.mm)
    
    # Main Plot Backgrounds
    plot!(final_plot[1], title="$(variable) Daily", ylabel=unit_label; presentation_style...)
    plot!(final_plot[2], title="Diurnal Cycle", xlabel="Hour", xticks=0:6:24, xlims=(0,24); presentation_style...)

    # Plot Obs First (so Models draw on top of it)
    if haskey(all_data[variable], "Obs")
        o_daily = all_data[variable]["Obs"].daily
        o_diurn = all_data[variable]["Obs"].diurnal
        
        plot!(final_plot[1], o_daily.DateOnly, o_daily.mean, color=:black, label="Obs", linestyle=:dash)
        plot!(final_plot[2], o_diurn.Hour, o_diurn.mean, color=:black, label="Obs", linestyle=:dash)
    end

    # Plot Model Data: Ensemble (Using the correct label key)
    ens_daily = all_data[variable][L"\psi_{s} + \psi_{L} + J"].daily
    ens_diurn = all_data[variable][L"\psi_{s} + \psi_{L} + J"].diurnal
    plot!(final_plot[1], ens_daily.DateOnly, ens_daily.mean, color=:red, label=L"\psi_{s} + \psi_{L} + J")
    plot!(final_plot[2], ens_diurn.Hour, ens_diurn.mean, color=:red, label=L"\psi_{s} + \psi_{L} + J")
    
    # Plot Model Data: ID=0 (Using the correct label key)
    id0_daily = all_data[variable]["std"].daily
    id0_diurn = all_data[variable]["std"].diurnal
    plot!(final_plot[1], id0_daily.DateOnly, id0_daily.mean, color=:blue, label="std")
    plot!(final_plot[2], id0_diurn.Hour, id0_diurn.mean, color=:blue, label="std")
    
    # Save
    fname = "comparison_$(variable)_ensemble_vs_id0.png"
    savefig(final_plot, joinpath(post_process_dir, fname))
end