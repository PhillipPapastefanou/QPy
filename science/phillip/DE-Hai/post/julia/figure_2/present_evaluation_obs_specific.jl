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
    s = replace(unit_str, "micro " => "\\mu{}")
    s = replace(s, "micro" => "\\mu{}")
    parts = split(s, " ", keepempty=false)
    formatted_parts = String[]
    for part in parts
        m = match(r"^([A-Za-z\\]+)(-?\d+)$", part)
        if m !== nothing
            base = m.captures[1]
            exponent = m.captures[2]
            push!(formatted_parts, "$(base)^{$(exponent)}")
        else
            push!(formatted_parts, part)
        end
    end
    joined_str = join(formatted_parts, " \\cdot ")
    final_latex_string = "\\mathrm{$(joined_str)}"
    return latexstring(final_latex_string)
end

function to_datetime(y, d, h)
    return DateTime(y) + Day(d - 1) + Millisecond(round(h * 3600000))
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

# --- Setup Shared Variables ---
var_avails = ["qle_avg", "gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
colors = [:red, :black, :blue]
series = ThirtyMinSeries

obs = init_hainich_obs()
df_fnet_22 = obs.df_fnet_22
df_fnet_24 = obs.df_fnet_24
df_psi_stem_obs = obs.df_psi_stem_obs
df_psi_leaf_obs = obs.df_psi_leaf_obs
df_sap_flow_2023 = obs.df_sap_flow_2023

# Make sure rt_path_hyd is defined (your original snippet used rt_path_hyd but defined rt_path_std)
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/70_run_transient_3days_new_mort_new_phen_fix/output"
post_process_dir = joinpath(rt_path_hyd, "../post", "f2_combined_2003_2023")
!isdir(post_process_dir) && mkdir(post_process_dir)

scenarios = [
    (dir="df_psi_stem_leaf_stem_flow_ind", label=L"\psi_{s} + \psi_{L} + J", id_filter=:all),
    (dir="df_ind", label="std", id_filter=[0])
]

# --- 1. Define configurations for both years ---
years_config = [
    (year=2003, d1=DateTime("2003-08-01"), d2=DateTime("2003-09-01")),
    (year=2023, d1=DateTime("2023-05-22"), d2=DateTime("2023-08-01"))
]

# Master dictionary to hold data for both years
yearly_data = Dict{Int, Any}()

# --- 2. Data Processing Loop (Over Years and Scenarios) ---
for conf in years_config
    yr = conf.year
    d1 = conf.d1
    d2 = conf.d2
    
    println("Processing year: $yr")
    
    all_data = Dict() # Data strictly for the current year
    
    df_fnet = yr < 2022 ? df_fnet_22 : df_fnet_24
    df_obs_gpp_slice = get_single_file_slice(df_fnet, "GPP", series, 0.05, 0.95, slice_dates, d1, d2)
    df_obs_le_slice = get_single_file_slice(df_fnet, "LE", series, 0.05, 0.95, slice_dates, d1, d2)
    df_obs_le_slice.mean .= -df_obs_le_slice.mean

    # Initialize safely to avoid @isdefined scoping issues
    df_obs_sapflow_slice = nothing
    df_obs_psi_stem_slice = nothing
    df_obs_psi_leaf_slice = nothing

    if yr == 2023
        df_obs_sapflow_slice = get_single_file_slice(df_sap_flow_2023, "Ji_Fasy", series, 0.1, 0.9, slice_dates, d1, d2)
        df_obs_psi_stem_slice = get_single_file_slice(df_psi_stem_obs, "FAG", series, 0.25, 0.75, slice_dates, d1, d2)    
        df_obs_psi_leaf_slice = get_single_file_slice(df_psi_leaf_obs, "psi_leaf_midday_avg", series, 0.25, 0.75, slice_dates, d1, d2)    
    end

    for scen in scenarios
        if scen.id_filter == :all
            ids_file = joinpath(rt_path_hyd, "../post/ana", "$(scen.dir).csv")
            ids = CSV.read(ids_file, DataFrame)[!, :fid]
        else
            ids = scen.id_filter
        end

        full_dir_paths = [joinpath(rt_path_hyd, string(id)) for id in ids]
        
        first_index = true
        qoutput = nothing
        cats = nothing
        sim_type_times = nothing
        qcol = QMultiRunCollections(QOutputCollection[], String[])

        for fstr in full_dir_paths
            if first_index 
                qoutput = read_quincy_site_output(fstr)
                cats = qoutput.cats
                sim_type_times = qoutput.sim_type_times
                first_index = false
            else
                qoutput = deepcopy(qoutput)
                for sim_type_t in sim_type_times
                    for cat in cats
                        filename = joinpath(fstr, cat*"_"*sim_type_t*".nc")
                        qoutput.data[sim_type_t][cat].filename = filename 
                    end
                end
            end
            push!(qcol.output, qoutput)
        end

        for variable in var_avails
            df_list = get_multi_file_slice(qcol, variable, Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2)
            
            df_ensemble = rename(df_list[1], :mean => "run_1")
            for idx in 2:length(df_list)
                next_df = rename(df_list[idx], :mean => "run_$(idx)")
                df_ensemble = outerjoin(df_ensemble, next_df, on = :DateTime, makeunique=true)
            end
            
            val_cols = names(df_ensemble, Not(:DateTime))
            
            df = transform(df_ensemble, val_cols => ByRow((vals...) -> begin
                clean_vals = filter(v -> !ismissing(v) && !isnan(v), [vals...])
                if isempty(clean_vals)
                    return (mean=NaN, qlow=NaN, qup=NaN, raw=Float64[])
                end
                return (
                    mean = mean(clean_vals),
                    qlow = quantile(clean_vals, 0.1),
                    qup  = quantile(clean_vals, 0.9),
                    raw  = clean_vals
                )
            end) => AsTable)

            df.DateOnly = Date.(df.DateTime)
            df_daily = combine(groupby(df, :DateOnly), [:mean, :qlow, :qup] .=> mean .=> [:mean, :qlow, :qup])
            
            df.Hour = hour.(df.DateTime) .+ minute.(df.DateTime) ./ 60
            df_diurnal = combine(groupby(df, :Hour), [:mean, :qlow, :qup] .=> mean .=> [:mean, :qlow, :qup])
            sort!(df_diurnal, :Hour)
            
            if !haskey(all_data, variable)
                all_data[variable] = Dict{String, Any}()
                all_data[variable]["unit"] = format_unit_to_latex(get_unit(qcol.output[1], variable))
            end
            all_data[variable][scen.label] = (daily = df_daily, diurnal = df_diurnal)

            # --- Process Observational Data ---
            obs_df_raw = if variable == "gpp_avg"
                df_obs_gpp_slice
            elseif variable == "qle_avg" && df_obs_le_slice !== nothing
                df_obs_le_slice
            elseif variable == "stem_flow_per_sap_area_avg" && df_obs_sapflow_slice !== nothing
                df_obs_sapflow_slice
            elseif variable == "psi_stem_avg" && df_obs_psi_stem_slice !== nothing
                df_obs_psi_stem_slice
            elseif variable == "psi_leaf_avg" && df_obs_psi_leaf_slice !== nothing
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
    
    yearly_data[yr] = all_data
end

presentation_style = (
    fontfamily = "Computer Modern",
    guidefontsize = 18,    
    tickfontsize = 14,     
    titlefontsize = 22,    
    legendfontsize = 14,   
    linewidth = 2.5,       
    grid = true,
    gridalpha = 0.2
)

# --- 3. Plotting Loop (2x2 grid per variable) ---
for variable in var_avails
    
    # Check if the variable exists in both years just in case
    if !haskey(yearly_data[2003], variable) || !haskey(yearly_data[2023], variable)
        println("Skipping $variable: missing in one or both years.")
        continue
    end

    unit_label = yearly_data[2003][variable]["unit"]
    
    # 2 rows, 2 columns. Left column slightly wider
    l = @layout [
        a{0.67w} b
        c{0.67w} d
    ]
    
    # Increased height to 1000 to cleanly fit two rows
    final_plot = plot(layout=l, size=(1400, 1000), margin=12Plots.mm)
    
    for (row_idx, yr) in enumerate([2003, 2023])
        # Plot indices: Row 1 uses 1 & 2. Row 2 uses 3 & 4.
        p_daily = (row_idx - 1) * 2 + 1
        p_diurn = (row_idx - 1) * 2 + 2
        
        all_data = yearly_data[yr]

        # Titles include the year for clarity
        plot!(final_plot[p_daily], title="$(variable) Daily ($yr)", ylabel=unit_label; presentation_style...)
        plot!(final_plot[p_diurn], title="Diurnal Cycle ($yr)", xlabel="Hour", xticks=0:6:24, xlims=(0,24); presentation_style...)

        # Plot Obs First
        if haskey(all_data[variable], "Obs")
            o_daily = all_data[variable]["Obs"].daily
            o_diurn = all_data[variable]["Obs"].diurnal
            
            plot!(final_plot[p_daily], o_daily.DateOnly, o_daily.mean, color=:black, label="Obs", linestyle=:dash)
            plot!(final_plot[p_diurn], o_diurn.Hour, o_diurn.mean, color=:black, label="Obs", linestyle=:dash)
        end

        # Plot Ensemble
        ens_daily = all_data[variable][L"\psi_{s} + \psi_{L} + J"].daily
        ens_diurn = all_data[variable][L"\psi_{s} + \psi_{L} + J"].diurnal
        plot!(final_plot[p_daily], ens_daily.DateOnly, ens_daily.mean, color=:red, label=L"\psi_{s} + \psi_{L} + J")
        plot!(final_plot[p_diurn], ens_diurn.Hour, ens_diurn.mean, color=:red, label=L"\psi_{s} + \psi_{L} + J")
        
        # Plot ID=0 (std)
        id0_daily = all_data[variable]["std"].daily
        id0_diurn = all_data[variable]["std"].diurnal
        plot!(final_plot[p_daily], id0_daily.DateOnly, id0_daily.mean, color=:blue, label="std")
        plot!(final_plot[p_diurn], id0_diurn.Hour, id0_diurn.mean, color=:blue, label="std")
    end
    
    # Save the combined 2x2 plot
    fname = "combined_2003_2023_$(variable).png"
    savefig(final_plot, joinpath(post_process_dir, fname))
    println("Saved: $fname")
end