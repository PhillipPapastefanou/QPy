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
ide = "sum2023_obs_hot"
var_avails = ["qle_avg", "gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
d1, d2 = DateTime("2023-07-01"), DateTime("2023-08-01")

rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/63_run_transient_3days/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)

scenarios = [
    (dir="df_psi_stem_leaf_stem_flow_ind", label=L"\psi_{s} + \psi_{L} + J", id_filter=:all),
    (dir="df_ind", label="std", id_filter=[0])
]

# scen_order = ["U", L"\psi_{s}", L"\psi_{s} + \psi_{L}", L"\psi_{s} + \psi_{L} + J"]
# scenarios = [
#     "df_ind" => "U",
#     "df_psi_stem_ind" => L"\psi_{s}",
#     "df_psi_stem_leaf_ind" => L"\psi_{s} + \psi_{L}",
#     "df_psi_stem_leaf_stem_flow_ind" => L"\psi_{s} + \psi_{L} + J"
# ]


series = ThirtyMinSeries
df_fnet = year(d1) < 2022 ? obs.df_fnet_22 : obs.df_fnet_24

# Prepare Observations
df_obs_gpp_slice = get_single_file_slice(df_fnet, "GPP", series, 0.05, 0.95, slice_dates, d1, d2)
df_obs_le_slice = get_single_file_slice(df_fnet, "LE", series, 0.05, 0.95, slice_dates, d1, d2)

if year(d1) == 2023
    df_obs_sapflow_slice = get_single_file_slice(obs.df_sap_flow_2023, "Ji_Fasy", series, 0.1, 0.9, slice_dates, d1, d2)
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

        # A. Ensemble model data
        df_list = get_multi_file_slice(qcol, variable, Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2)
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
            
            if variable == "qle_avg" 
                m = -m
                ql, qu = -qu, -ql # Swap bounds when flipping sign
            end
            if variable == "stem_flow_per_sap_area_avg" || variable == "G_per_sap_area_avg"
                factor = 1000.0 * 0.5
                m *= factor; ql *= factor; qu *= factor
            end
            return (mean = m, qlow = ql, qup = qu)
        end) => AsTable)

        df.DateOnly = Date.(df.DateTime)
        df.Hour = hour.(df.DateTime) .+ minute.(df.DateTime) ./ 60

        # B. Observation Match & Overlap
        obs_df_raw = if variable == "gpp_avg"; df_obs_gpp_slice
        elseif variable == "qle_avg" && @isdefined(df_obs_le_slice); df_obs_le_slice
        elseif variable == "stem_flow_per_sap_area_avg" && @isdefined(df_obs_sapflow_slice); df_obs_sapflow_slice
        elseif variable == "G_per_sap_area_avg" && @isdefined(df_obs_sapflow_slice); df_obs_sapflow_slice
        elseif variable == "psi_stem_avg" && @isdefined(df_obs_psi_stem_slice); df_obs_psi_stem_slice
        elseif variable == "psi_leaf_avg" && @isdefined(df_obs_psi_leaf_slice); df_obs_psi_leaf_slice
        else nothing end

        if obs_df_raw !== nothing
            obs_clean = dropmissing(obs_df_raw, :mean)
            obs_clean.DateOnly = Date.(obs_clean.DateTime)
            obs_clean.Hour = hour.(obs_clean.DateTime) .+ minute.(obs_clean.DateTime) ./ 60
            
            # Join for diurnal overlap
            df_overlap = innerjoin(df[!, [:DateTime, :Hour, :mean, :qlow, :qup]], obs_clean[!, [:DateTime, :mean]], on = :DateTime, makeunique=true)
            
            mod_diurnal = combine(groupby(df_overlap, :Hour), :mean => mean => :mean, :qlow => mean => :qlow, :qup => mean => :qup)
            obs_diurnal = combine(groupby(df_overlap, :Hour), :mean_1 => mean => :mean)

            all_data[variable]["Obs"] = (daily = combine(groupby(obs_clean, :DateOnly), :mean => mean => :mean), 
                                         diurnal = sort!(obs_diurnal, :Hour),
                                         raw_ts = obs_clean)
        end

        mod_daily = combine(groupby(df, :DateOnly), :mean => mean => :mean, :qlow => mean => :qlow, :qup => mean => :qup)
        mod_diurnal_final = haskey(all_data[variable], "Obs") ? mod_diurnal : combine(groupby(df, :Hour), :mean => mean => :mean, :qlow => mean => :qlow, :qup => mean => :qup)
        
        all_data[variable][scen.label] = (daily = mod_daily, diurnal = sort!(mod_diurnal_final, :Hour), raw_ts = df)
    end
end

# --- 4. Plotting ---
presentation_style = (fontfamily="Computer Modern", guidefontsize=18, tickfontsize=14, titlefontsize=22, legendfontsize=14, linewidth=2.5, grid=true, gridalpha=0.2)

for variable in var_avails
    unit_label = all_data[variable]["unit"]
    is_psi = variable in ["psi_stem_avg", "psi_leaf_avg"]
    is_leaf = variable == "psi_leaf_avg"
    
    l = @layout [a{0.67w} b]
    final_plot = plot(layout=l, size=(1400, 500), margin=12Plots.mm)
    
    plot!(final_plot[1], title="$(variable) $(is_psi ? "30-min" : "Daily")", ylabel=unit_label; presentation_style...)
    plot!(final_plot[2], title="Diurnal Overlap", xlabel="Hour", xticks=0:6:24, xlims=(0,24); presentation_style...)

    # Plot Observations
    if haskey(all_data[variable], "Obs")
        o = all_data[variable]["Obs"]
        x_o = is_psi ? o.raw_ts.DateTime : o.daily.DateOnly
        y_o = is_psi ? o.raw_ts.mean : o.daily.mean
        if is_leaf
            scatter!(final_plot[1], x_o, y_o, color=:black, label="Obs", markersize=4, markerstrokewidth=0)
            scatter!(final_plot[2], o.diurnal.Hour, o.diurnal.mean, color=:black, label="Obs", markersize=5, markerstrokewidth=0)
        else
            plot!(final_plot[1], x_o, y_o, color=:black, label="Obs", linestyle=:dash)
            plot!(final_plot[2], o.diurnal.Hour, o.diurnal.mean, color=:black, label="Obs", linestyle=:dash)
        end
    end

    # Plot Models
    for (lab, col) in [(L"\psi_{s} + \psi_{L} + J", :red), ("std", :blue)]
        m = all_data[variable][lab]
        x_m = is_psi ? m.raw_ts.DateTime : m.daily.DateOnly
        y_m = is_psi ? m.raw_ts.mean : m.daily.mean
        
        if lab == L"\psi_{s} + \psi_{L} + J"
            # Determine ribbon data based on resolution
            ql = is_psi ? m.raw_ts.qlow : m.daily.qlow
            qu = is_psi ? m.raw_ts.qup : m.daily.qup
            
            rib_ts = (y_m .- ql, qu .- y_m)
            rib_diurnal = (m.diurnal.mean .- m.diurnal.qlow, m.diurnal.qup .- m.diurnal.mean)
            
            plot!(final_plot[1], x_m, y_m, ribbon=rib_ts, fillalpha=0.2, color=col, label=lab)
            plot!(final_plot[2], m.diurnal.Hour, m.diurnal.mean, ribbon=rib_diurnal, fillalpha=0.2, color=col, label="")
        else
            plot!(final_plot[1], x_m, y_m, color=col, label=lab)
            plot!(final_plot[2], m.diurnal.Hour, m.diurnal.mean, color=col, label="")
        end
    end
    
    savefig(final_plot, joinpath(post_process_dir, "comparison_$(variable).png"))
end