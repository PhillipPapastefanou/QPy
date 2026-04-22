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

# --- 1. Helper Functions ---
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

# --- 2. Setup & Paths ---
obs = init_hainich_obs()
ide = "fig_1_2023_timeseries_and_diurnal"

# UPDATED: Swapped stem_flow for G_per_sap_area_avg
var_avails = ["psi_leaf_avg", "psi_stem_avg", "G_per_sap_area_avg"]

# STANDARD DATES (For Psi_stem)
d1, d2 = DateTime("2023-07-01"), DateTime("2023-08-01")

# SAP FLOW DATES
d1_sap, d2_sap = DateTime("2023-06-01"), DateTime("2023-08-01")

# PSI LEAF EXACT DATES (01/06 to 01/06)
d1_leaf = DateTime("2023-06-01")
d2_leaf = DateTime("2023-10-01") # Set to the 2nd to capture the full 24h of the 1st

rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/68_run_transient_3days_new_mort_new_phen_fix/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)

# Removed the 'std' scenario
scenarios = [
    (dir="df_psi_stem_leaf_stem_flow_ind", label=L"\psi_{s} + \psi_{L} + J", id_filter=:all)
]

series = ThirtyMinSeries
df_fnet = year(d1) < 2022 ? obs.df_fnet_22 : obs.df_fnet_24

# Prepare Observations with specific date windows
if year(d1) == 2023
    df_obs_sapflow_slice = get_single_file_slice(obs.df_sap_flow_2023, "Ji_Fasy", series, 0.1, 0.9, slice_dates, d1_sap, d2_sap)
    df_obs_psi_stem_slice = get_single_file_slice(obs.df_psi_stem_obs, "FAG", series, 0.25, 0.75, slice_dates, d1, d2)    
    df_obs_psi_leaf_slice = get_single_file_slice(obs.df_psi_leaf_obs, "psi_leaf_midday_avg", series, 0.25, 0.75, slice_dates, d1_leaf, d2_leaf)    
end

all_data = Dict()

# --- 3. Data Processing Loop ---
for scen in scenarios
    if scen.id_filter == :all
        ids_file = joinpath(rt_path_hyd, "../post/ana", "$(scen.dir).csv")
        ids = CSV.read(ids_file, DataFrame)[!, :fid]
    else
        ids = scen.id_filter
    end

    full_dir_paths = [joinpath(rt_path_hyd, string(id)) for id in ids]
    qcol = QMultiRunCollections(QOutputCollection[], String[])

    first_index = true
    for fstr in full_dir_paths
        qoutput = read_quincy_site_output(fstr)
        if !first_index
            for sim_type_t in qoutput.sim_type_times, cat in qoutput.cats
                qoutput.data[sim_type_t][cat].filename = joinpath(fstr, cat*"_"*sim_type_t*".nc")
            end
        end
        push!(qcol.output, qoutput)
        first_index = false
    end

    for variable in var_avails
        if !haskey(all_data, variable)
            all_data[variable] = Dict{String, Any}()
            all_data[variable]["unit"] = format_unit_to_latex(get_unit(qcol.output[1], variable))
        end
        
        # Apply correct dates based on variable
        curr_d1 = variable == "psi_leaf_avg" ? d1_leaf : (variable == "G_per_sap_area_avg" ? d1_sap : d1)
        curr_d2 = variable == "psi_leaf_avg" ? d2_leaf : (variable == "G_per_sap_area_avg" ? d2_sap : d2)

        # Extract ensemble model data
        df_list = get_multi_file_slice(qcol, variable, Fluxnetdata, series, 0.1, 0.9, slice_dates, curr_d1, curr_d2)
        df_ensemble = rename(df_list[1], :mean => "run_1")
        for idx in 2:length(df_list)
            next_df = rename(df_list[idx], :mean => "run_$(idx)")
            df_ensemble = outerjoin(df_ensemble, next_df, on = :DateTime, makeunique=true)
        end
        
        val_cols = names(df_ensemble, Not(:DateTime))
        df = transform(df_ensemble, val_cols => ByRow((vals...) -> begin
            clean_vals = filter(v -> !ismissing(v) && !isnan(v), [vals...])
            if isempty(clean_vals) return (mean=NaN, qlow=NaN, qup=NaN) end
            
            m  = mean(clean_vals)
            ql = quantile(clean_vals, 0.1)
            qu = quantile(clean_vals, 0.9)
            
            # Make sure G gets scaled just like sapflow did
            if variable == "G_per_sap_area_avg"
                factor = 1000.0 * 0.5
                m *= factor; ql *= factor; qu *= factor
            end
            return (mean = m, qlow = ql, qup = qu)
        end) => AsTable)

        df.DateOnly = Date.(df.DateTime)
        df.Hour = hour.(df.DateTime) .+ minute.(df.DateTime) ./ 60

        # Observations mapping
        obs_df_raw = if variable == "G_per_sap_area_avg" && @isdefined(df_obs_sapflow_slice); df_obs_sapflow_slice
        elseif variable == "psi_stem_avg" && @isdefined(df_obs_psi_stem_slice); df_obs_psi_stem_slice
        elseif variable == "psi_leaf_avg" && @isdefined(df_obs_psi_leaf_slice); df_obs_psi_leaf_slice
        else nothing end

        if obs_df_raw !== nothing
            obs_clean = dropmissing(obs_df_raw, :mean)
            obs_clean.DateOnly = Date.(obs_clean.DateTime)
            # Round hours for diurnal join
            obs_clean.Hour = round.((hour.(obs_clean.DateTime) .+ minute.(obs_clean.DateTime) ./ 60) .* 2) ./ 2
            
            # Safely handle quantiles if they are not present in the raw extraction
            if !hasproperty(obs_clean, :qlow)
                obs_clean.qlow = obs_clean.mean
                obs_clean.qup = obs_clean.mean
            end

            # Propagate observation uncertainties into the diurnal aggregation
            obs_diurnal = combine(groupby(obs_clean, :Hour), 
                :mean => (x -> mean(skipmissing(x))) => :mean,
                :qlow => (x -> mean(skipmissing(x))) => :qlow,
                :qup  => (x -> mean(skipmissing(x))) => :qup
            )
            all_data[variable]["Obs"] = (raw_ts = obs_clean, diurnal = sort!(obs_diurnal, :Hour))
        end
        
        mod_diurnal = combine(groupby(df, :Hour), :mean => mean => :mean, :qlow => mean => :qlow, :qup => mean => :qup)
        all_data[variable][scen.label] = (raw_ts = df, diurnal = sort!(mod_diurnal, :Hour))
    end
end

# --- 4. Plotting (3 Rows x 2 Columns) ---
presentation_style = (fontfamily="Computer Modern", guidefontsize=16, tickfontsize=12, titlefontsize=16, legendfontsize=10, linewidth=2.5, grid=true, gridalpha=0.2)

plots_array = []
main_scen_label = L"\psi_{s} + \psi_{L} + J"
col = :red # Explicitly red for the main model scenario

for (i, variable) in enumerate(var_avails)
    unit_label = all_data[variable]["unit"]
    is_leaf = variable == "psi_leaf_avg"
    is_sap  = variable == "G_per_sap_area_avg" # TRIGGER FLAG FOR DAILY AGGREGATION
    
    # Create two subplots for this row: Time Series (Left) and Diurnal (Right)
    p_ts = plot(ylabel=unit_label, title="$(variable) (Time Series)"; presentation_style...)
    p_di = plot(xlabel="Hour", title="Diurnal Average", xticks=0:6:24, xlims=(0,24); presentation_style...)
    
    # Get Observation Overlap Bounds
    t_min, t_max = d1, d2
    if haskey(all_data[variable], "Obs")
        obs_ts = all_data[variable]["Obs"].raw_ts
        obs_di = all_data[variable]["Obs"].diurnal
        
        if nrow(obs_ts) > 0
            t_min = minimum(obs_ts.DateTime)
            t_max = maximum(obs_ts.DateTime)
            
            # Left: Plot TS Observations (WITH UNCERTAINTY)
            if is_leaf
                scatter!(p_ts, obs_ts.DateTime, obs_ts.mean, color=:black, label="Obs", markersize=6, markerstrokewidth=0)
            elseif is_sap
                # Aggregate Observations to Daily Mean + Daily Uncertainty for Sap Flow
                obs_ts_daily = combine(groupby(obs_ts, :DateOnly), 
                    :mean => (x -> mean(skipmissing(x))) => :mean,
                    :qlow => (x -> mean(skipmissing(x))) => :qlow,
                    :qup  => (x -> mean(skipmissing(x))) => :qup
                )
                rib_obs_ts = (coalesce.(obs_ts_daily.mean .- obs_ts_daily.qlow, 0.0), coalesce.(obs_ts_daily.qup .- obs_ts_daily.mean, 0.0))
                plot!(p_ts, obs_ts_daily.DateOnly, obs_ts_daily.mean, ribbon=rib_obs_ts, fillalpha=0.15, color=:black, label="Obs (Sapflow)", linealpha=0.9)
            else
                rib_obs_ts = (coalesce.(obs_ts.mean .- obs_ts.qlow, 0.0), coalesce.(obs_ts.qup .- obs_ts.mean, 0.0))
                plot!(p_ts, obs_ts.DateTime, obs_ts.mean, ribbon=rib_obs_ts, fillalpha=0.15, color=:black, label="Obs", linealpha=0.9)
            end
            
            # Right: Plot Diurnal Observations (WITH UNCERTAINTY)
            if !is_leaf
                rib_obs_di = (coalesce.(obs_di.mean .- obs_di.qlow, 0.0), coalesce.(obs_di.qup .- obs_di.mean, 0.0))
                plot!(p_di, obs_di.Hour, obs_di.mean, ribbon=rib_obs_di, fillalpha=0.15, color=:black, label="Obs", linealpha=0.9)
            end
        end
    end

    # Plot Model Data
    if haskey(all_data[variable], main_scen_label)
        mod_ts_full = all_data[variable][main_scen_label].raw_ts
        mod_di = all_data[variable][main_scen_label].diurnal
        
        # Filter TS to overlap window only
        mod_ts = filter(r -> r.DateTime >= t_min && r.DateTime <= t_max, mod_ts_full)
        
        if nrow(mod_ts) > 0
            # Left: Plot TS Model
            if is_leaf
                # Only plot Midday points (Hour == 12.0) for Leaf TS
                mod_ts_midday = filter(r -> r.Hour == 12.0, mod_ts)
                if nrow(mod_ts_midday) > 0
                    rib_ts = (mod_ts_midday.mean .- mod_ts_midday.qlow, mod_ts_midday.qup .- mod_ts_midday.mean)
                    plot!(p_ts, mod_ts_midday.DateTime, mod_ts_midday.mean, color=col, label="", linealpha=0.5)
                end
            elseif is_sap
                # Aggregate Model to Daily Mean for G_per_sap_area_avg
                mod_ts_daily = combine(groupby(mod_ts, :DateOnly), :mean => mean => :mean, :qlow => mean => :qlow, :qup => mean => :qup)
                rib_ts = (mod_ts_daily.mean .- mod_ts_daily.qlow, mod_ts_daily.qup .- mod_ts_daily.mean)
                plot!(p_ts, mod_ts_daily.DateOnly, mod_ts_daily.mean, ribbon=rib_ts, fillalpha=0.2, color=col, label="Model (G)")
            else
                # Plot full continuous 30-min data for others
                rib_ts = (mod_ts.mean .- mod_ts.qlow, mod_ts.qup .- mod_ts.mean)
                plot!(p_ts, mod_ts.DateTime, mod_ts.mean, ribbon=rib_ts, fillalpha=0.2, color=col, label="Model")
            end
        end
        
        # Right: Plot Diurnal Model (Full 24h curve for all variables)
        if nrow(mod_di) > 0
            rib_di = (mod_di.mean .- mod_di.qlow, mod_di.qup .- mod_di.mean)
            plot!(p_di, mod_di.Hour, mod_di.mean, ribbon=rib_di, fillalpha=0.2, color=col, label="Model")
        end
    end
    
    # Push left and right plots to the array sequentially
    push!(plots_array, p_ts)
    push!(plots_array, p_di)
end

# Combine into a 3 Row x 2 Column layout
l = @layout [grid(3, 2)]
final_figure = plot(plots_array..., layout=l, size=(1600, 1000), margin=8Plots.mm)

# Save the final compiled plot
savefig(final_figure, joinpath(post_process_dir, "timeseries_and_diurnal_3x2_comparison.png"))
println("Processing complete. 3x2 Plot saved to: ", post_process_dir)