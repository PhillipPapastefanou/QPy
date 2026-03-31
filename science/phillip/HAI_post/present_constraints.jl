
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


ide = "sum18"
colors = [:purple, :blue, :green, :red]
var_avails=  ["gpp_avg", "stem_flow_per_sap_area_avg", "G_per_sap_area_avg", "psi_stem_avg", "psi_leaf_avg", "beta_gs", "gc_avg"]
target_midday_1 = DateTime("2018-06-01T12:00:00")
target_midday_2 = DateTime("2018-08-05T12:00:00")
d1, d2 = DateTime("2018-05-15"), DateTime("2018-09-30")

# --- 1. Setup ---
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/63_run_transient_3days/output"
post_process_dir = joinpath(rt_path_hyd, "../post", ide)
!isdir(post_process_dir) && mkdir(post_process_dir)

# Define the scenarios and their display labels
scenarios = [
    "df_ind" => "Ind",
    "df_psi_stem_ind" => "Psi Stem",
    "df_psi_stem_leaf_ind" => "Psi Leaf",
    "df_psi_stem_leaf_stem_flow_ind" => "Flow"
]


series = ThirtyMinSeries

# We will store the processed data here: Dict{Variable -> Dict{Scenario -> (daily_df, diurnal_df)}}
all_data = Dict()

# --- 2. Data Processing Loop ---
# This part runs for every scenario to collect the data first
for (scen_name, label) in scenarios
    ids_file = joinpath(rt_path_hyd, "../post/ana", "$(scen_name).csv")
    ids = CSV.read(ids_file, DataFrame)[!, :fid]
    full_dir_paths = [joinpath(rt_path_hyd, string(id)) for id in ids]
    
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
        all_data[variable][scen_name] = (daily = df_daily, diurnal = df_diurnal)

        # 1. Identify which columns contain the ensemble data (everything except DateTime)
        val_cols = names(df_ensemble, Not(:DateTime))

        # 2. Find the row index that matches your target time exactly
        # We use findfirst to get the integer index of the matching row
        idx1 = findfirst(==(target_midday_1), df_ensemble.DateTime)
        idx2 = findfirst(==(target_midday_2), df_ensemble.DateTime)

        # 3. Extract the row and convert to a cleaned vector
        if idx1 !== nothing
            # Extract the row at idx1, only the data columns, and convert to a Vector
            row_values = collect(values(df_ensemble[idx1, val_cols]))
            # Filter out any NaNs or missings from the ensemble at that moment
            all_data[variable]["violin_data_1"][scen_name] = filter(v -> !ismissing(v) && !isnan(v), row_values)
        else
            @warn "Target time $target_midday_1 not found in $(variable) $(scen_name)"
            all_data[variable]["violin_data_1"][scen_name] = Float64[]
        end

        if idx2 !== nothing
            row_values = collect(values(df_ensemble[idx2, val_cols]))
            all_data[variable]["violin_data_2"][scen_name] = filter(v -> !ismissing(v) && !isnan(v), row_values)
        else
            all_data[variable]["violin_data_2"][scen_name] = Float64[]
        end
    end
end


all_data["gpp_avg"]["violin_data_1"]["df_ind"]

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

# --- 3. Incremental Plotting Loop ---
# This creates 4 sets of files: _1 (scen 1), _2 (scen 1+2), etc.
for i in 1:length(scenarios)
    for variable in var_avails
        unit_label = all_data[variable]["unit"]
        
        # 1. Initialize Layout
        l = @layout [a{0.67w} b]
        final_plot = plot(layout=l, size=(1400, 600), margin=12Plots.mm)
        
        # 2. Add Insets to the Right of Subplot 1
        # bbox(x, y, width, height)
        # Inset 1 (Left): x=0.05
        plot!(final_plot, inset=(1, bbox(0.07, 0.55, 0.22, 0.38)), subplot=3, bg_inside=:white)
        #plot!(final_plot, inset=(1, bbox(0.07, 0.05, 0.22, 0.38)), subplot=3, bg_inside=:white)

        # Inset 2 (Right): x=0.72
        plot!(final_plot, inset=(1, bbox(0.76, 0.05, 0.22, 0.38)), subplot=4, bg_inside=:white)
        #plot!(final_plot, inset=(1, bbox(0.72, 0.55, 0.22, 0.38)), subplot=4, bg_inside=:white)
        
        # 3. Apply styles to Main Plots
        plot!(final_plot[1], title="$(variable) Daily", ylabel=unit_label, legend=false; presentation_style...)
        plot!(final_plot[2], title="Diurnal Cycle", xlabel="Hour", xticks=0:6:24, xlims=(0,24); presentation_style...)

        # 4. Apply styles to Violin Insets
        # We set xlims=(0.5, 4.5) so the axis doesn't jump as we add scenarios
        date_str1 = Dates.format(target_midday_1, "yyyy-mm-dd")
        date_str2 = Dates.format(target_midday_2, "yyyy-mm-dd")

        plot!(final_plot[3], titlefontsize=14, xticks=:none, framestyle=:box, xlabel = Dates.format(target_midday_1, "yyyy-mm-dd"), 
              legend=false, xlims=(0.5, 4.5), fontfamily="Computer Modern",  guidefontsize=10 )
        
        plot!(final_plot[4], titlefontsize=14, xticks=:none, framestyle=:box,xlabel = Dates.format(target_midday_2, "yyyy-mm-dd"), 
              legend=false, xlims=(0.5, 4.5), fontfamily="Computer Modern", guidefontsize=10)
              


        # 5. Add Data
        for j in 1:i
            s_name, s_label = scenarios[j]
            d_daily = all_data[variable][s_name].daily
            d_diurn = all_data[variable][s_name].diurnal
            
            # Daily & Diurnal
            plot!(final_plot[1], d_daily.DateOnly, d_daily.mean, 
                  ribbon=(d_daily.mean .- d_daily.qlow, d_daily.qup .- d_daily.mean),
                  fillalpha=0.15, color=colors[j], label=s_label)
            
            plot!(final_plot[2], d_diurn.Hour, d_diurn.mean, 
                  ribbon=(d_diurn.mean .- d_diurn.qlow, d_diurn.qup .- d_diurn.mean),
                  fillalpha=0.15, color=colors[j], label=s_label)
            
            # Violins
            v1_vals = all_data[variable]["violin_data_1"][s_name]
            v2_vals = all_data[variable]["violin_data_2"][s_name]
            
            if !isempty(v1_vals)
                violin!(final_plot[3], [j], v1_vals, color=colors[j], alpha=0.5, linewidth=0)
            end
            if !isempty(v2_vals)
                violin!(final_plot[4], [j], v2_vals, color=colors[j], alpha=0.5, linewidth=0)
            end
        end

        # Final adjustments for saving
        fname = "comparison_$(variable)_step_$(i).png"
        savefig(final_plot, joinpath(post_process_dir, fname))
    end
end

#vscodedisplay(df_mod_gpp)
