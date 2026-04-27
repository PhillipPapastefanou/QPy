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

obs = init_hainich_obs()

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
    return latexstring("\\mathrm{$(joined_str)}")
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

# --- 1. Shared Setup & Configurations ---
colors = [:blue, :green, :red]
var_avails = ["qle_avg", "gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
series = ThirtyMinSeries

rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/68_run_transient_3days_new_mort_new_phen_fix/output"
post_process_dir = joinpath(rt_path_hyd, "../post", "f3_combined_incremental_with_obs")
!isdir(post_process_dir) && mkdir(post_process_dir)

scenarios = [
    "df_psi_leaf_ind" => L"\psi_{L}",
    "df_psi_stem_leaf_ind" => L"\psi_{s} + \psi_{L}",
    "df_psi_stem_leaf_stem_flow_ind" => L"\psi_{s} + \psi_{L} + J"
]

# Define parameters for both years
years_config = [
    (year=2003, d1=DateTime("2003-07-20"), d2=DateTime("2003-08-30"), t1=DateTime("2003-07-21T12:00:00"), t2=DateTime("2003-08-10T12:00:00")),
    (year=2023, d1=DateTime("2023-05-15"), d2=DateTime("2023-08-01"), t1=DateTime("2023-06-15T12:00:00"), t2=DateTime("2023-07-15T12:00:00"))
]

df_fnet_22 = obs.df_fnet_22
df_fnet_24 = obs.df_fnet_24
df_psi_stem_obs = obs.df_psi_stem_obs
df_psi_leaf_obs = obs.df_psi_leaf_obs
df_sap_flow_2023 = obs.df_sap_flow_2023

# --- 2. Data Extraction Loop ---
yearly_data = Dict{Int, Any}()

for conf in years_config
    yr = conf.year
    d1, d2 = conf.d1, conf.d2
    target_1, target_2 = conf.t1, conf.t2
    
    println("Processing Data for $yr...")
    all_data = Dict()

    # Get Observations for the current year
    df_fnet = yr < 2022 ? df_fnet_22 : df_fnet_24
    df_obs_gpp_slice = get_single_file_slice(df_fnet, "GPP", series, 0.05, 0.95, slice_dates, d1, d2)
    df_obs_le_slice = get_single_file_slice(df_fnet, "LE", series, 0.05, 0.95, slice_dates, d1, d2)
    df_obs_le_slice.mean .= -df_obs_le_slice.mean # Invert LE

    df_obs_sapflow_slice = nothing
    df_obs_psi_stem_slice = nothing
    df_obs_psi_leaf_slice = nothing

    if yr == 2023
        df_obs_sapflow_slice = get_single_file_slice(df_sap_flow_2023, "Ji_Fasy", series, 0.1, 0.9, slice_dates, d1, d2)
        df_obs_psi_stem_slice = get_single_file_slice(df_psi_stem_obs, "FAG", series, 0.25, 0.75, slice_dates, d1, d2)    
        df_obs_psi_leaf_slice = get_single_file_slice(df_psi_leaf_obs, "psi_leaf_midday_avg", series, 0.25, 0.75, slice_dates, d1, d2)    
    end

    # Extract Model Data
    for (scen_name, label) in scenarios
        ids_file = joinpath(rt_path_hyd, "../post/ana", "$(scen_name).csv")
        ids = CSV.read(ids_file, DataFrame)[!, :fid]
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
            push!(qcol.output, qoutput);
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
                return (mean=mean(clean_vals), qlow=quantile(clean_vals, 0.1), qup=quantile(clean_vals, 0.9), raw=clean_vals)
            end) => AsTable)

            df.DateOnly = Date.(df.DateTime)
            df_daily = combine(groupby(df, :DateOnly), [:mean, :qlow, :qup] .=> mean .=> [:mean, :qlow, :qup])
            
            df.Hour = hour.(df.DateTime) .+ minute.(df.DateTime) ./ 60
            df_diurnal = combine(groupby(df, :Hour), [:mean, :qlow, :qup] .=> mean .=> [:mean, :qlow, :qup])
            sort!(df_diurnal, :Hour)
            
            if !haskey(all_data, variable)
                all_data[variable] = Dict{String, Any}()
                all_data[variable]["unit"] = format_unit_to_latex(get_unit(qcol.output[1], variable))
                all_data[variable]["violin_data_1"] = Dict{String, Vector{Float64}}()
                all_data[variable]["violin_data_2"] = Dict{String, Vector{Float64}}()
            end
            all_data[variable][scen_name] = (daily = df_daily, diurnal = df_diurnal)

            # Violin extractions
            idx1 = findfirst(==(target_1), df_ensemble.DateTime)
            idx2 = findfirst(==(target_2), df_ensemble.DateTime)

            if idx1 !== nothing
                row_values = collect(values(df_ensemble[idx1, val_cols]))
                all_data[variable]["violin_data_1"][scen_name] = filter(v -> !ismissing(v) && !isnan(v), row_values)
            else
                all_data[variable]["violin_data_1"][scen_name] = Float64[]
            end

            if idx2 !== nothing
                row_values = collect(values(df_ensemble[idx2, val_cols]))
                all_data[variable]["violin_data_2"][scen_name] = filter(v -> !ismissing(v) && !isnan(v), row_values)
            else
                all_data[variable]["violin_data_2"][scen_name] = Float64[]
            end
            
            # Aggregate and Save Observations (do this only once per variable, ignoring scen_name loops)
            if !haskey(all_data[variable], "Obs")
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

# --- 3. Incremental Plotting Loop (2-Row Layout with Obs & Insets) ---
println("Generating combined incremental plots...")
# Use length(scenarios) + 0.5 to keep violin x-axis static across steps
v_xlims = (0.5, length(scenarios) + 0.5)

for i in 1:length(scenarios)
    for variable in var_avails
        if !haskey(yearly_data[2003], variable) || !haskey(yearly_data[2023], variable)
            continue
        end

        unit_label = yearly_data[2003][variable]["unit"]
        
        # Initialize 2x2 Layout
        l = @layout [
            a{0.67w} b
            c{0.67w} d
        ]
        final_plot = plot(layout=l, size=(1400, 1100), margin=12Plots.mm)
        
        # Add Insets (Subplots 5 & 6 attach to 2003 Daily [1], 7 & 8 attach to 2023 Daily [3])
        plot!(final_plot, inset=(1, bbox(0.07, 0.55, 0.22, 0.38)), subplot=5, bg_inside=:white)
        plot!(final_plot, inset=(1, bbox(0.76, 0.05, 0.22, 0.38)), subplot=6, bg_inside=:white)
        
        plot!(final_plot, inset=(3, bbox(0.07, 0.55, 0.22, 0.38)), subplot=7, bg_inside=:white)
        plot!(final_plot, inset=(3, bbox(0.76, 0.05, 0.22, 0.38)), subplot=8, bg_inside=:white)
        
        for (row_idx, conf) in enumerate(years_config)
            yr = conf.year
            all_data = yearly_data[yr]
            
            p_daily = (row_idx - 1) * 2 + 1   # 1 or 3
            p_diurn = (row_idx - 1) * 2 + 2   # 2 or 4
            p_in1   = row_idx == 1 ? 5 : 7    # 5 or 7
            p_in2   = row_idx == 1 ? 6 : 8    # 6 or 8
            
            # Base Plot Styling
            plot!(final_plot[p_daily], title="$(variable) Daily ($yr)", ylabel=unit_label, legend=false; presentation_style...)
            plot!(final_plot[p_diurn], title="Diurnal Cycle ($yr)", xlabel="Hour", xticks=0:6:24, xlims=(0,24); presentation_style...)

            # Violin Inset Styling
            plot!(final_plot[p_in1], titlefontsize=14, xticks=:none, framestyle=:box, xlabel = Dates.format(conf.t1, "yyyy-mm-dd"), legend=false, xlims=v_xlims, fontfamily="Computer Modern", guidefontsize=10)
            plot!(final_plot[p_in2], titlefontsize=14, xticks=:none, framestyle=:box, xlabel = Dates.format(conf.t2, "yyyy-mm-dd"), legend=false, xlims=v_xlims, fontfamily="Computer Modern", guidefontsize=10)
            
            # Plot Obs First (so it stays in the background)
            if haskey(all_data[variable], "Obs")
                o_daily = all_data[variable]["Obs"].daily
                o_diurn = all_data[variable]["Obs"].diurnal
                plot!(final_plot[p_daily], o_daily.DateOnly, o_daily.mean, color=:black, label="Obs", linestyle=:dash, linewidth=2.5)
                plot!(final_plot[p_diurn], o_diurn.Hour, o_diurn.mean, color=:black, label="Obs", linestyle=:dash, linewidth=2.5)
            end

            # Plot Incremental Scenarios
            for j in 1:i
                s_name, s_label = scenarios[j]
                d_daily = all_data[variable][s_name].daily
                d_diurn = all_data[variable][s_name].diurnal
                
                # Main lines and ribbons
                plot!(final_plot[p_daily], d_daily.DateOnly, d_daily.mean, ribbon=(d_daily.mean .- d_daily.qlow, d_daily.qup .- d_daily.mean), fillalpha=0.15, color=colors[j], label=s_label)
                plot!(final_plot[p_diurn], d_diurn.Hour, d_diurn.mean, ribbon=(d_diurn.mean .- d_diurn.qlow, d_diurn.qup .- d_diurn.mean), fillalpha=0.15, color=colors[j], label=s_label)
                
                # Inset violins
                v1_vals = all_data[variable]["violin_data_1"][s_name]
                v2_vals = all_data[variable]["violin_data_2"][s_name]
                
                if !isempty(v1_vals)
                    violin!(final_plot[p_in1], [j], v1_vals, color=colors[j], alpha=0.5, linewidth=0)
                end
                if !isempty(v2_vals)
                    violin!(final_plot[p_in2], [j], v2_vals, color=colors[j], alpha=0.5, linewidth=0)
                end
            end
        end

        fname = "comparison_$(variable)_step_$(i).png"
        savefig(final_plot, joinpath(post_process_dir, fname))
    end
end
println("All incremental combined plots completed!")