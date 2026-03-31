
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

# ide = "sum2003_obs"
# colors = [:red, :black, :blue]
# var_avails=  ["qle_avg", "gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
# target_midday_1 = DateTime("2003-06-01T12:00:00")
# target_midday_2 = DateTime("2003-08-05T12:00:00")
# d1, d2 = DateTime("2003-05-15"), DateTime("2003-08-01")


obs = init_hainich_obs()

ide = "sum2023_obs"
var_avails = ["qle_avg", "gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
d1, d2 = DateTime("2023-05-22"), DateTime("2023-08-01")

rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/63_run_transient_3days/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)

scenarios = [
    (dir="df_psi_stem_leaf_stem_flow_ind", label="Flow (Ensemble)", id_filter=:all),
    (dir="df_ind", label="Flow (ID=0)", id_filter=[0])
]

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
            if isempty(clean_vals) return (mean=NaN,) end
            m = mean(clean_vals)
            if variable == "qle_avg" m = -m end
            if variable == "stem_flow_per_sap_area_avg" m = m * 1000.0 * 0.5 end
            if variable == "G_per_sap_area_avg" m = m * 1000.0 * 0.5 end
            return (mean = m,)
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
            
            # Inner join for overlap diurnal
            df_overlap = innerjoin(df[!, [:DateTime, :Hour, :mean]], obs_clean[!, [:DateTime, :mean]], on = :DateTime, makeunique=true)
            
            mod_diurnal = combine(groupby(df_overlap, :Hour), :mean => mean => :mean)
            obs_diurnal = combine(groupby(df_overlap, :mean_1), :Hour => (h -> h) => :Hour, :mean_1 => mean => :mean) # fix naming from join
            # Simpler grouping for diurnal obs
            obs_diurnal = combine(groupby(df_overlap, :Hour), :mean_1 => mean => :mean)

            all_data[variable]["Obs"] = (daily = combine(groupby(obs_clean, :DateOnly), :mean => mean => :mean), 
                                         diurnal = sort!(obs_diurnal, :Hour),
                                         raw_ts = obs_clean)
        end

        mod_daily = combine(groupby(df, :DateOnly), :mean => mean => :mean)
        mod_diurnal = haskey(all_data[variable], "Obs") ? mod_diurnal : combine(groupby(df, :Hour), :mean => mean => :mean)
        
        all_data[variable][scen.label] = (daily = mod_daily, diurnal = sort!(mod_diurnal, :Hour), raw_ts = df)
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

    if haskey(all_data[variable], "Obs")
        o = all_data[variable]["Obs"]
        x_obs = is_psi ? o.raw_ts.DateTime : o.daily.DateOnly
        y_obs = is_psi ? o.raw_ts.mean : o.daily.mean
        
        if is_leaf
            # Use points for psi_leaf_avg
            scatter!(final_plot[1], x_obs, y_obs, color=:black, label="Obs", markersize=4, markerstrokewidth=0)
            scatter!(final_plot[2], o.diurnal.Hour, o.diurnal.mean, color=:black, label="Obs", markersize=5, markerstrokewidth=0)
        else
            # Use dashed line for everything else
            plot!(final_plot[1], x_obs, y_obs, color=:black, label="Obs", linestyle=:dash)
            plot!(final_plot[2], o.diurnal.Hour, o.diurnal.mean, color=:black, label="Obs", linestyle=:dash)
        end
    end

    for (lab, col) in [("Flow (Ensemble)", :red), ("Flow (ID=0)", :blue)]
        m = all_data[variable][lab]
        plot!(final_plot[1], is_psi ? m.raw_ts.DateTime : m.daily.DateOnly, is_psi ? m.raw_ts.mean : m.daily.mean, color=col, label=lab)
        plot!(final_plot[2], m.diurnal.Hour, m.diurnal.mean, color=col, label="")
    end
    
    savefig(final_plot, joinpath(post_process_dir, "comparison_$(variable).png"))
end