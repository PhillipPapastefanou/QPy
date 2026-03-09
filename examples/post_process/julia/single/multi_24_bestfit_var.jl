
using Statistics, VectorizedStatistics
using DataFrames
using Dates
using Base.Filesystem: basename
using CSV
using Base.Threads
using CairoMakie

include("../../../../src/postprocessing/julia/core/qcomparer_2024.jl")

obs = init_hainich_obs()


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



function calculate_mod_obs_rmse_2024(quincy_output::String, hainich_obs::HainichObs, ids, d1 ,d2)
    df_fnet_22 = hainich_obs.df_fnet_22
    df_fnet_24 = hainich_obs.df_fnet_24
    df_psi_stem_obs = hainich_obs.df_psi_stem_obs
    df_psi_leaf_obs = hainich_obs.df_psi_leaf_obs
    df_sap_flow_2023 = hainich_obs.df_sap_flow_2023


    # date_ranges = [
    # ("24", DateTime("2024-05-01"), DateTime("2024-10-30")),
    # ("full", DateTime("2000-01-01"), DateTime("2024-12-31")),
    # ("03", DateTime("2003-05-01"), DateTime("2003-10-30")),
    #  ("18", DateTime("2018-05-01"), DateTime("2018-10-30"))
    # ]


    post_process_dir = joinpath("$quincy_output", "../post")
    if !isdir(post_process_dir)
        mkdir(post_process_dir)
    end

    full_dir_paths = [joinpath(quincy_output, id) for id in ids]
    short_dir_paths = basename.(full_dir_paths)

    # println("A")
    # println(full_dir_paths)
    # println("B")
    # println(post_process_dir)


    #df_param = CSV.read(joinpath(quincy_output, "parameters.csv"), DataFrame)

    

        df_fnet = ""
        if year(d1) < 2022
            df_fnet =    df_fnet_22  
        else
            df_fnet =    df_fnet_24        
        end


        vars = ["gpp_avg", "npp_avg", "total_veg_c", "gc_avg"]


        fig = Figure(resolution = (1600, 1200))  

        axis = []

        for j in 1:2

            i = 1
            for var in vars
                push!(axis, Axis(fig[i, j], ylabel = var))
                i += 1
            end

        if j == 1
            series = DailySeries
        else
            series = ThirtyMinSeries
        end
        
        start_time = time()
        #last_report = start_time

        # df_param[!, Symbol("gpp_rmse_$ystr")] .= NaN
        # df_param[!, Symbol("le_rmse_$ystr")] .= NaN
        # df_param[!, Symbol("psi_stem_rmse_$ystr")] .= NaN
        # df_param[!, Symbol("psi_leaf_rmse_$ystr")] .= NaN
        # df_param[!, Symbol("stem_flow_rmse_$ystr")] .= NaN
        # df_param[!, Symbol("stem_flow_rmse_05_$ystr")] .= NaN
        # df_param[!, Symbol("stem_flow_rmse_2_$ystr")] .= NaN
        # df_param[!, Symbol("stem_flow_rmse_025_$ystr")] .= NaN

        qoutput = nothing
        cats = nothing
        sim_type_times=nothing
   
    
        for (i, (full, short)) in enumerate(zip(full_dir_paths, short_dir_paths))

            if i == 1 
                qoutput = read_quincy_site_output(full)
                cats = qoutput.cats
                sim_type_times = qoutput.sim_type_times
            else
                #We need to override the file paths
                for sim_type_t in sim_type_times
                    for cat in cats
                        filename = joinpath(full, cat*"_"*sim_type_t*".nc")
                        qoutput.data[sim_type_t][cat].filename = filename;  
                    end
                end
            end

            #print(qoutput);
            if j == 1
                series = DailySeries
            else
                series = ThirtyMinSeries
            end





            if j == 1
                i = 1
                for var in vars
                    df = get_single_file_slice(qoutput, var, Fluxnetdata,  series, 0.1, 0.9, slice_dates, d1 ,d2);

                    lines!(axis[i], df.DateTime, df.mean);
                    i += 1
                end

            else

                # df_hourly = df_obs_rad |>
                #     # 1. Create a temporary 'Hour' column for grouping
                #     df -> transform(df, :DateTime => ByRow(hour) => :Hour) |>
                #     # 2. Group by that hour and calculate the mean
                #     df -> combine(groupby(df, :Hour), :mean => mean, :mean_vpd => mean) |>
                #     # 3. Rename the column back to DateTime (as you had it)
                #     df -> rename(df, :Hour => :DateTime)              
                # lines!(ax_rad,  df_hourly.DateTime,  df_hourly.mean_mean, color = :black, label = "Observed", alpha = 0.5);
                # lines!(ax_vpd,  df_hourly.DateTime,  df_hourly.mean_vpd_mean, color = :black, label = "Observed", alpha = 0.5);

                # df_join = innerjoin(df_mod_gpp, df_obs_gpp_slice, on = :DateTime, makeunique=true)
                # df_join.Hour = hour.(df_join.DateTime)
                # df_join = combine(groupby(df_join, :Hour), :mean => mean, :mean_1 => mean)
                # rename!(df_join, :Hour => :DateTime)
                # lines!(ax_gpp,  df_join.DateTime, df_join.mean_1_mean,  color = :black, label = "Observed", alpha= 0.5);
                # lines!(ax_gpp,  df_join.DateTime, df_join.mean_mean, label = short, alpha= 0.5);


                # df_join = innerjoin(df_mod_le, df_obs_le_slice, on = :DateTime, makeunique=true)
                # df_join.Hour = hour.(df_join.DateTime)
                # df_join = combine(groupby(df_join, :Hour), :mean => mean, :mean_1 => mean)
                # rename!(df_join, :Hour => :DateTime)
                # lines!(ax_le,  df_join.DateTime, -df_join.mean_mean, label = short, alpha= 0.5);
                # lines!(ax_le,  df_join.DateTime, df_join.mean_1_mean,  color = :black, label = "Observed", alpha= 0.5);


                # if year(d1) >= 2023
                #     df_join = innerjoin(df_mod_psi_stem, df_obs_psi_stem_slice, df_mod_psi_leaf, df_mod_G, df_mod_gs, on = :DateTime, makeunique=true)
                #     df_join.Hour = hour.(df_join.DateTime)
                #     df_join = combine(groupby(df_join, :Hour), :mean => mean,
                #     :mean_1 => mean, :mean_2 => mean, :mean_3 => mean, :mean_4 => mean)
                #     rename!(df_join, :Hour => :DateTime)

                #     lines!(ax_stem,  df_join.DateTime, df_join.mean_mean,  label = short, alpha= 0.5);
                #     lines!(ax_stem,  df_join.DateTime, df_join.mean_1_mean, color = :black, label = "Observed", alpha= 0.5);
                #     lines!(ax_leaf,  df_join.DateTime, df_join.mean_2_mean, alpha= 0.5);
                #     lines!(ax_G,  df_join.DateTime, df_join.mean_3_mean* 1000.0, label = short, alpha= 0.5);
                #     lines!(ax_gs,  df_join.DateTime, df_join.mean_4_mean, label = short, alpha= 0.5);

                #     df_join = innerjoin(df_mod_stem_flow, df_obs_sapflow_slice, on = :DateTime, makeunique=true)
                #     df_join.Hour = hour.(df_join.DateTime)
                #     df_join = combine(groupby(df_join, :Hour), :mean => mean, :mean_1 => mean)
                #     rename!(df_join, :Hour => :DateTime)
                #     lines!(ax_flow,  df_join.DateTime, df_join.mean_1_mean *2.0,  color = :black, label = "Observed", alpha= 0.5);
                #     lines!(ax_G,  df_join.DateTime, df_join.mean_1_mean *2.0,  color = :black, label = "Observed", alpha= 0.5);
                #     lines!(ax_flow,  df_join.DateTime, df_join.mean_mean* 1000.0, label = short, alpha= 0.5);
                # end
            end
            

            # df_join = innerjoin(df_mod_gpp, df_obs_gpp_slice, on = :DateTime, makeunique=true)
            # rmse = sqrt(mean((df_join.mean .- df_join.mean_1).^2))
            # df_param[index, Symbol("gpp_rmse_$ystr")] = rmse

          
            # df_join = innerjoin(df_mod_le, df_obs_le_slice, on = :DateTime, makeunique=true)
            # rmse = sqrt(mean((abs.(df_join.mean) .- abs.(df_join.mean_1)).^2))
            # df_param[index,Symbol("le_rmse_$ystr")] = rmse

            # df_join = innerjoin(df_mod_psi_stem, df_obs_psi_stem_slice, on = :DateTime, makeunique=true)
            # rmse = sqrt(mean((df_join.mean .- df_join.mean_1).^2))
            # df_param[index, Symbol("psi_stem_rmse_$ystr")] = rmse

            # df_join = innerjoin(df_mod_psi_leaf, df_obs_psi_leaf_slice, on = :DateTime, makeunique=true)
            # rmse = sqrt(mean((df_join.mean .- df_join.mean_1).^2))
            # df_param[index, Symbol("psi_leaf_rmse_$ystr")] = rmse

            # df_join = innerjoin(df_mod_stem_flow, df_obs_sapflow_slice, on = :DateTime, makeunique=true)
            # #print(names(df_join))
            # #print(df_join.mean * 1000.0)
            # #print(df_join.mean_1)
            # rmse = sqrt(mean((df_join.mean * 1000.0 .- df_join.mean_1).^2))
            # df_param[index,Symbol("stem_flow_rmse_$ystr")] = rmse

            # rmse = sqrt(mean((0.5 * df_join.mean * 1000.0 .- df_join.mean_1).^2))
            # df_param[index,Symbol("stem_flow_rmse_05_$ystr")] = rmse

            # rmse = sqrt(mean((0.25 * df_join.mean * 1000.0 .- df_join.mean_1).^2))
            # df_param[index,Symbol("stem_flow_rmse_025_$ystr")] = rmse

            # rmse = sqrt(mean((2.0 * df_join.mean * 1000.0 .- df_join.mean_1).^2))
            # df_param[index,Symbol("stem_flow_rmse_2_$ystr")] = rmse


            #last_report = progress_report(i, length(short_dir_paths), start_time, last_report)

            end
        end
    # Save as a standard PNG
    #print(joinpath(post_process_dir, "test.png"))
    colsize!(fig.layout, 1, Relative(2/3))
    colsize!(fig.layout, 2, Relative(1/3))

    save(joinpath(post_process_dir, "var_$(year(d1))_$(year(d2)).png"), fig)
    
    #CSV.write(joinpath(post_process_dir,"params_rmse_2024.csv"), df_param)
end

root_output_folder= "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/53_run_transient_g1_low_gamma_leaf/output"
root_output_folder= "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/254_run_transient_no_texture/output"

for year in ["2003", "2024", "2023", "2018"]
    print("$year..")
    #ids, d1, d2 = ["1836", "7366"], DateTime("$year-05-01"), DateTime("$year-10-30")
    ids, d1, d2 = ["0", "3686", "4293", "4191"], DateTime("$year-05-01"), DateTime("$year-10-30")
    calculate_mod_obs_rmse_2024(root_output_folder, obs, ids, d1, d2)
    println("Done!")
end

