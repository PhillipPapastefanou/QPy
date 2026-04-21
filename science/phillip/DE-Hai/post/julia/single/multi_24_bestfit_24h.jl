
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


        # d1_gpp, d2_gpp = DateTime("2024-05-01"), DateTime("2024-09-10")
        # d1_psi_stem, d2_psi_stem = DateTime("2024-05-01"), DateTime("2024-09-10")
        # d1_psi_leaf, d2_psi_leaf = DateTime("2024-05-01"), DateTime("2024-09-10")
        # d1_sap, d2_sap = DateTime("2024-05-01"), DateTime("2024-09-10")


        d1_gpp, d2_gpp = d1, d2
        d1_psi_stem, d2_psi_stem = d1, d2
        d1_psi_leaf, d2_psi_leaf = d1, d2
        d1_sap, d2_sap = d1, d2


        fig = Figure(resolution = (1600, 1200))  

        for j in 1:2
            ax_gpp   = Axis(fig[1, j], ylabel = "GPP", title = "Site Comparison $j")
            ax_le    = Axis(fig[2, j], ylabel = "Latent Heat")
            ax_stem  = Axis(fig[3, j], ylabel = "Psi Stem")
            ax_leaf  = Axis(fig[4, j], ylabel = "Psi Leaf")
            ax_flow  = Axis(fig[5, j], ylabel = "Stem Flow", xlabel = "Time")
            ax_G  = Axis(fig[6, j], ylabel = "Lateral Flow", xlabel = "Time")
            ax_beta_gs  = Axis(fig[7, j], ylabel = "beta_gs", xlabel = "Time")
            ax_rad = Axis(fig[8, j], ylabel = "obs_rad", xlabel = "Time")
            ax_vpd = Axis(fig[9, j], ylabel = "obs_vpd", xlabel = "Time")
            ax_gs = Axis(fig[10, j], ylabel = "mod_gs", xlabel = "Time")


        if j == 1
            series = DailySeries
        else
            series = ThirtyMinSeries
        end
        
        df_obs_gpp_slice = get_single_file_slice(df_fnet, "GPP", series, 0.05, 0.95,
        slice_dates, 
        d1_gpp, d2_gpp )
        df_obs_le_slice = get_single_file_slice(df_fnet, "LE", series, 0.05, 0.95,
        slice_dates, 
        d1_gpp, d2_gpp)

        df_climate_input = read_input_df(joinpath(full_dir_paths[1]))

        df_obs_rad = get_single_file_slice(df_climate_input, "swvis_srf_down", series, 0.05, 0.95,
        slice_dates, 
        d1_gpp, d2_gpp)

        df_obs_t_k = get_single_file_slice(df_climate_input, "t_air", series, 0.05, 0.95,
        slice_dates, 
        d1_gpp, d2_gpp)

        df_obs_q_gkg = get_single_file_slice(df_climate_input, "q_air", series, 0.05, 0.95,
        slice_dates, 
        d1_gpp, d2_gpp)

        df_obs_p_hpa = get_single_file_slice(df_climate_input, "press_srf", series, 0.05, 0.95,
        slice_dates, 
        d1_gpp, d2_gpp)


        df_obs_rad.mean_vpd = calculate_vpd.(df_obs_t_k[!,:mean], df_obs_q_gkg[!,:mean], df_obs_p_hpa[!, :mean])
        
        if year(d1) >= 2023
            df_obs_sapflow_slice = get_single_file_slice(df_sap_flow_2023, "Ji_Fasy", series, 0.1, 0.9, slice_dates,
            d1_sap, d2_sap )

            series = ThirtyMinSeries

            df_obs_psi_stem_slice = get_single_file_slice(df_psi_stem_obs, "psi", series, 0.25, 0.75,slice_dates, 
            d1_psi_stem, d2_psi_stem )    
            df_obs_psi_leaf_slice = get_single_file_slice(df_psi_leaf_obs, "psi_leaf_midday_avg", series, 0.25, 0.75, slice_dates, 
            d1_psi_leaf, d2_psi_leaf)    
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
            df_mod_gpp = get_single_file_slice(qoutput, "gpp_avg", Fluxnetdata,  series, 0.1, 0.9, slice_dates, d1_gpp ,d2_gpp);
            df_mod_le = get_single_file_slice(qoutput, "qle_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1_gpp, d2_gpp);
            df_mod_stem_flow = get_single_file_slice(qoutput, "stem_flow_per_sap_area_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1_sap, d2_sap);
            df_mod_G = get_single_file_slice(qoutput, "G_per_sap_area_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1_psi_leaf, d2_psi_leaf);


            series = ThirtyMinSeries
            df_mod_psi_stem = get_single_file_slice(qoutput, "psi_stem_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1_psi_stem, d2_psi_stem);
            df_mod_psi_leaf = get_single_file_slice(qoutput, "psi_leaf_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1_psi_leaf, d2_psi_leaf);
            df_mod_beta_gs = get_single_file_slice(qoutput, "beta_gs", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1_psi_leaf, d2_psi_leaf);
            df_mod_gs = get_single_file_slice(qoutput, "gc_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1_psi_leaf, d2_psi_leaf);

            # index = findfirst(==(parse(Int,short)), df_param.fid)


            if j == 1
                lines!(ax_gpp,  df_obs_gpp_slice.DateTime, df_obs_gpp_slice.mean,  color = :black, label = "Observed", alpha= 0.5);
                lines!(ax_le,   df_obs_le_slice.DateTime, df_obs_le_slice.mean,  color = :black, alpha= 0.5);
                
                if year(d1) >= 2023
                    lines!(ax_stem, df_obs_psi_stem_slice.DateTime, df_obs_psi_stem_slice.mean, color = :black, alpha= 0.5);
                    scatter!(ax_leaf, df_obs_psi_leaf_slice.DateTime, df_obs_psi_leaf_slice.mean, color = :black, markersize = 8);
                    lines!(ax_flow, df_obs_sapflow_slice.DateTime, df_obs_sapflow_slice.mean * 2.0,    color = :black, alpha= 0.5);
                    lines!(ax_G, df_obs_sapflow_slice.DateTime, df_obs_sapflow_slice.mean * 2.0,    color = :black, alpha= 0.5);
                end 

                lines!(ax_gpp,  df_mod_gpp.DateTime,  df_mod_gpp.mean,  label = short, alpha = 0.5);
                lines!(ax_le,   df_mod_le.DateTime,   -df_mod_le.mean, alpha= 0.5);
                lines!(ax_stem, df_mod_psi_stem.DateTime, df_mod_psi_stem.mean, alpha = 0.5);
                lines!(ax_leaf, df_mod_psi_leaf.DateTime, df_mod_psi_leaf.mean, alpha = 0.5);
                lines!(ax_flow,  df_mod_stem_flow.DateTime,  df_mod_stem_flow.mean * 1000.0, alpha = 0.5);
                lines!(ax_G,  df_mod_G.DateTime,  df_mod_G.mean * 1000.0, alpha = 0.5);
                lines!(ax_beta_gs,  df_mod_beta_gs.DateTime,  df_mod_beta_gs.mean, alpha = 0.5);
                lines!(ax_gs,  df_mod_gs.DateTime,  df_mod_gs.mean, alpha = 0.5);

                lines!(ax_rad,  df_obs_rad.DateTime,  df_obs_rad.mean, alpha = 0.5, color = :black, label = "Observed");
                lines!(ax_vpd,  df_obs_rad.DateTime,  df_obs_rad.mean_vpd, alpha = 0.5, color = :black, label = "Observed");

            else

                df_hourly = df_obs_rad |>
                    # 1. Create a temporary 'Hour' column for grouping
                    df -> transform(df, :DateTime => ByRow(hour) => :Hour) |>
                    # 2. Group by that hour and calculate the mean
                    df -> combine(groupby(df, :Hour), :mean => mean, :mean_vpd => mean) |>
                    # 3. Rename the column back to DateTime (as you had it)
                    df -> rename(df, :Hour => :DateTime)              
                lines!(ax_rad,  df_hourly.DateTime,  df_hourly.mean_mean, color = :black, label = "Observed", alpha = 0.5);
                lines!(ax_vpd,  df_hourly.DateTime,  df_hourly.mean_vpd_mean, color = :black, label = "Observed", alpha = 0.5);

                df_join = innerjoin(df_mod_gpp, df_obs_gpp_slice, on = :DateTime, makeunique=true)
                df_join.Hour = hour.(df_join.DateTime)
                df_join = combine(groupby(df_join, :Hour), :mean => mean, :mean_1 => mean)
                rename!(df_join, :Hour => :DateTime)
                lines!(ax_gpp,  df_join.DateTime, df_join.mean_1_mean,  color = :black, label = "Observed", alpha= 0.5);
                lines!(ax_gpp,  df_join.DateTime, df_join.mean_mean, label = short, alpha= 0.5);


                df_join = innerjoin(df_mod_le, df_obs_le_slice, on = :DateTime, makeunique=true)
                df_join.Hour = hour.(df_join.DateTime)
                df_join = combine(groupby(df_join, :Hour), :mean => mean, :mean_1 => mean)
                rename!(df_join, :Hour => :DateTime)
                lines!(ax_le,  df_join.DateTime, -df_join.mean_mean, label = short, alpha= 0.5);
                lines!(ax_le,  df_join.DateTime, df_join.mean_1_mean,  color = :black, label = "Observed", alpha= 0.5);


                if year(d1) >= 2023
                    df_join = innerjoin(df_mod_psi_stem, df_obs_psi_stem_slice, df_mod_psi_leaf, df_mod_G, df_mod_gs, on = :DateTime, makeunique=true)
                    df_join.Hour = hour.(df_join.DateTime)
                    df_join = combine(groupby(df_join, :Hour), :mean => mean,
                    :mean_1 => mean, :mean_2 => mean, :mean_3 => mean, :mean_4 => mean)
                    rename!(df_join, :Hour => :DateTime)

                    lines!(ax_stem,  df_join.DateTime, df_join.mean_mean,  label = short, alpha= 0.5);
                    lines!(ax_stem,  df_join.DateTime, df_join.mean_1_mean, color = :black, label = "Observed", alpha= 0.5);
                    lines!(ax_leaf,  df_join.DateTime, df_join.mean_2_mean, alpha= 0.5);
                    lines!(ax_G,  df_join.DateTime, df_join.mean_3_mean* 1000.0, label = short, alpha= 0.5);
                    lines!(ax_gs,  df_join.DateTime, df_join.mean_4_mean, label = short, alpha= 0.5);

                    df_join = innerjoin(df_mod_stem_flow, df_obs_sapflow_slice, on = :DateTime, makeunique=true)
                    df_join.Hour = hour.(df_join.DateTime)
                    df_join = combine(groupby(df_join, :Hour), :mean => mean, :mean_1 => mean)
                    rename!(df_join, :Hour => :DateTime)
                    lines!(ax_flow,  df_join.DateTime, df_join.mean_1_mean *2.0,  color = :black, label = "Observed", alpha= 0.5);
                    lines!(ax_G,  df_join.DateTime, df_join.mean_1_mean *2.0,  color = :black, label = "Observed", alpha= 0.5);
                    lines!(ax_flow,  df_join.DateTime, df_join.mean_mean* 1000.0, label = short, alpha= 0.5);
                end
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

    println(joinpath(post_process_dir, "multi_$(year(d1))_24h_.png"))
    save(joinpath(post_process_dir, "multi_$(year(d1))_24h_.png"), fig)
    
    #CSV.write(joinpath(post_process_dir,"params_rmse_2024.csv"), df_param)
end

root_output_folder= "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/56_refix_run_transient_g1_low_gamma_leaf/output"
#root_output_folder= "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/254_run_transient_no_texture/output"

for year in ["2003", "2024", "2023", "2018"]
    print("$year..")
    ids, d1, d2 = ["1836", "7366"], DateTime("$year-05-01"), DateTime("$year-10-30")
    #ids, d1, d2 = ["0", "10378", "16137"], DateTime("$year-05-01"), DateTime("$year-10-30")
    #ids, d1, d2 = ["0", "3686", "4293", "4191"], DateTime("$year-05-01"), DateTime("$year-10-30")
    ids, d1, d2 = ["0", "829", "19230"], DateTime("$year-05-01"), DateTime("$year-10-30")
    calculate_mod_obs_rmse_2024(root_output_folder, obs, ids, d1, d2)
    println("Done!")
end

