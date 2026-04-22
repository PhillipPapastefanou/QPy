using Statistics, VectorizedStatistics
using DataFrames
using Dates
using Base.Filesystem: basename
using CSV
using Base.Threads
using Plots
using LaTeXStrings
using StatsPlots

include("../../../../../src/postprocessing/julia/core/qcomparer_2023.jl")
include("../../../../../src/postprocessing/julia/core/qslicer.jl")

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

# Safe quantile function for observations 
safe_q20(x) = length(x) > 1 ? quantile(x, 0.2) : first(x)
safe_q80(x) = length(x) > 1 ? quantile(x, 0.8) : first(x)

# --- 2. Setup & Paths ---
obs = init_hainich_obs()
ide = "sum2023_obs_hot_gem"
var_avails = ["qle_avg", "gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]

# STANDARD DATES (For Psi_stem and others)
d1, d2 = DateTime("2023-07-11"), DateTime("2023-07-25")

# SAP FLOW DATES (01/06 to 01/10)
d1_sap, d2_sap = DateTime("2023-06-01"), DateTime("2023-10-01")

rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/68_run_transient_3days_new_mort_new_phen_fix/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)

scenarios = [
    (dir="df_psi_stem_leaf_stem_flow_ind", label=L"\psi_{s} + \psi_{L} + J", id_filter=:all),
    (dir="df_ind", label="std", id_filter=[0])
]

series = ThirtyMinSeries
df_fnet = year(d1) < 2022 ? obs.df_fnet_22 : obs.df_fnet_24

# Prepare Observations
df_obs_gpp_slice = get_single_file_slice(df_fnet, "GPP", series, 0.05, 0.95, slice_dates, d1, d2)
df_obs_le_slice = get_single_file_slice(df_fnet, "LE", series, 0.05, 0.95, slice_dates, d1, d2)

if year(d1) == 2023
    df_obs_sapflow_slice = get_single_file_slice(obs.df_sap_flow_2023, "Ji_Fasy", series, 0.1, 0.9, slice_dates, d1_sap, d2_sap)
    df_obs_psi_stem_slice = get_single_file_slice(obs.df_psi_stem_obs, "FAG", series, 0.25, 0.75, slice_dates, d1, d2)    
    df_obs_psi_leaf_slice = get_single_file_slice(obs.df_psi_leaf_obs, "psi_leaf_midday_avg", series, 0.25, 0.75, slice_dates, d1, d2)    
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

        curr_d1 = (variable == "stem_flow_per_sap_area_avg" || variable == "G_per_sap_area_avg") ? d1_sap : d1
        curr_d2 = (variable == "stem_flow_per_sap_area_avg" || variable == "G_per_sap_area_avg") ? d2_sap : d2

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
            m  = mean(clean_vals); ql = quantile(clean_vals, 0.2); qu = quantile(clean_vals, 0.8)
            if variable == "qle_avg"; m = -m; ql, qu = -qu, -ql; end
            if variable == "stem_flow_per_sap_area_avg" || variable == "G_per_sap_area_avg"
                factor = 1000.0 * 0.5
                m *= factor; ql *= factor; qu *= factor
            end
            return (mean = m, qlow = ql, qup = qu)
        end) => AsTable)

        df.DateOnly = Date.(df.DateTime)
        df.Hour = hour.(df.DateTime) .+ minute.(df.DateTime) ./ 60

        obs_df_raw = if variable == "gpp_avg"; df_obs_gpp_slice
        elseif variable == "qle_avg" && @isdefined(df_obs_le_slice); df_obs_le_slice
        elseif variable == "stem_flow_per_sap_area_avg" && @isdefined(df_obs_sapflow_slice); df_obs_sapflow_slice
        elseif variable == "psi_stem_avg" && @isdefined(df_obs_psi_stem_slice); df_obs_psi_stem_slice
        elseif variable == "psi_leaf_avg" && @isdefined(df_obs_psi_leaf_slice); df_obs_psi_leaf_slice
        else nothing end

        if obs_df_raw !== nothing
            obs_clean = dropmissing(obs_df_raw, :mean)
            obs_clean.Hour = round.((hour.(obs_clean.DateTime) .+ minute.(obs_clean.DateTime) ./ 60) .* 2) ./ 2
            
            obs_diurnal = combine(groupby(obs_clean, :Hour), 
                                  :mean => mean => :mean,
                                  :mean => safe_q20 => :qlow,
                                  :mean => safe_q80 => :qup)
                                  
            all_data[variable]["Obs"] = (diurnal = sort!(obs_diurnal, :Hour), raw_ts = obs_clean)
        end

        mod_diurnal_final = combine(groupby(df, :Hour), :mean => mean => :mean, :qlow => mean => :qlow, :qup => mean => :qup)
        all_data[variable][scen.label] = (diurnal = sort!(mod_diurnal_final, :Hour), raw_ts = df)
    end
end

# --- 4. Hysteresis Loop Logic ---
presentation_style = (fontfamily="Computer Modern", guidefontsize=18, tickfontsize=14, titlefontsize=20, legendfontsize=12, linewidth=2.5, grid=true, gridalpha=0.1)

var_x = "stem_flow_per_sap_area_avg"
var_y = "psi_stem_avg"

if haskey(all_data, var_x) && haskey(all_data, var_y)
    h_plot = plot(title="Diurnal Hysteresis (24h Average)", 
                  xlabel="$(var_x) [$(all_data[var_x]["unit"])]", 
                  ylabel="$(var_y) [$(all_data[var_y]["unit"])]"; 
                  presentation_style...)

    # --- Plot Observation Hysteresis Bands ---
    if haskey(all_data[var_x], "Obs") && haskey(all_data[var_y], "Obs")
        obs_x = all_data[var_x]["Obs"].diurnal
        obs_y = all_data[var_y]["Obs"].diurnal
        df_h_obs = innerjoin(obs_x, obs_y, on=:Hour, renamecols="_x" => "_y")
        
        if nrow(df_h_obs) > 0
            # 1. Ensure vectors wrap around midnight to close the polygon seamlessly
            x_m  = [df_h_obs.mean_x; df_h_obs.mean_x[1]]; x_dn = [df_h_obs.qlow_x; df_h_obs.qlow_x[1]]; x_up = [df_h_obs.qup_x; df_h_obs.qup_x[1]]
            y_m  = [df_h_obs.mean_y; df_h_obs.mean_y[1]]; y_dn = [df_h_obs.qlow_y; df_h_obs.qlow_y[1]]; y_up = [df_h_obs.qup_y; df_h_obs.qup_y[1]]

            # 2. Draw Y-Uncertainty Band (Vertical Polygon)
            plot!(h_plot, [x_m; reverse(x_m)], [y_up; reverse(y_dn)], seriestype=:shape, color=:black, fillalpha=0.1, linealpha=0, label="")
            
            # 3. Draw X-Uncertainty Band (Horizontal Polygon)
            plot!(h_plot, [x_up; reverse(x_dn)], [y_m; reverse(y_m)], seriestype=:shape, color=:black, fillalpha=0.1, linealpha=0, label="")

            # 4. Plot Central Mean Line
            plot!(h_plot, x_m, y_m, color=:black, label="Obs", linestyle=:dash)
        end
    end

    # --- Plot Model Scenarios Hysteresis Bands ---
    for (lab, col) in [(L"\psi_{s} + \psi_{L} + J", :red), ("std", :blue)]
        mod_x = all_data[var_x][lab].diurnal
        mod_y = all_data[var_y][lab].diurnal
        df_h_mod = innerjoin(mod_x, mod_y, on=:Hour, renamecols="_x" => "_y")
        
        if nrow(df_h_mod) > 0
            # 1. Ensure vectors wrap around midnight
            x_m  = [df_h_mod.mean_x; df_h_mod.mean_x[1]]; x_dn = [df_h_mod.qlow_x; df_h_mod.qlow_x[1]]; x_up = [df_h_mod.qup_x; df_h_mod.qup_x[1]]
            y_m  = [df_h_mod.mean_y; df_h_mod.mean_y[1]]; y_dn = [df_h_mod.qlow_y; df_h_mod.qlow_y[1]]; y_up = [df_h_mod.qup_y; df_h_mod.qup_y[1]]

            # 2. Draw Y-Uncertainty Band (Vertical Polygon)
            plot!(h_plot, [x_m; reverse(x_m)], [y_up; reverse(y_dn)], seriestype=:shape, color=col, fillalpha=0.15, linealpha=0, label="")
            
            # 3. Draw X-Uncertainty Band (Horizontal Polygon)
            plot!(h_plot, [x_up; reverse(x_dn)], [y_m; reverse(y_m)], seriestype=:shape, color=col, fillalpha=0.15, linealpha=0, label="")

            # 4. Plot Central Mean Line
            plot!(h_plot, x_m, y_m, color=col, label=lab)
            
            # Midday marker
            midday = filter(r -> r.Hour == 12.0, df_h_mod)
            if !isempty(midday)
                scatter!(h_plot, [midday.mean_x[1]], [midday.mean_y[1]], color=col, markersize=6, label="")
            end
        end
    end
    savefig(h_plot, joinpath(post_process_dir, "hysteresis_areaa_$(var_x)_vs_$(var_y).png"))
end

println("Processing complete. Plots saved to: ", post_process_dir)