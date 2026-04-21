
using Statistics, VectorizedStatistics
using DataFrames
using Dates
using Base.Filesystem: basename
using CSV
using Base.Threads
using CairoMakie

include("../../../../src/postprocessing/julia/core/qcomparer_2024.jl")

obs = init_hainich_obs()



function calculate_mod_obs_rmse_2024(quincy_output::String, hainich_obs::HainichObs, name::String, 
    d1::DateTime, d2::DateTime)
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


    post_process_dir = joinpath("$quincy_output", "../../post")
    if !isdir(post_process_dir)
        mkdir(post_process_dir)
    end

    full_dir_paths = [quincy_output]
    short_dir_paths = basename.(full_dir_paths)

    println("A")
    println(full_dir_paths)
    println("B")
    println(post_process_dir)


    #df_param = CSV.read(joinpath(quincy_output, "parameters.csv"), DataFrame)

    series = ThirtyMinSeries

        df_fnet = ""
        if year(d1) < 2022
            df_fnet =    df_fnet_22  
        else
            df_fnet =    df_fnet_24        
        end

        df_obs_gpp_slice = get_single_file_slice(df_fnet, "GPP", series, 0.05, 0.95,
        slice_dates, 
        d1, d2)
        
        df_obs_le_slice = get_single_file_slice(df_fnet, "LE", series, 0.05, 0.95,
        slice_dates, 
        d1, d2) 
        
        df_obs_psi_stem_slice = get_single_file_slice(df_psi_stem_obs, "psi", series, 0.25, 0.75,slice_dates, 
        d1, d2)    

        df_obs_psi_leaf_slice = get_single_file_slice(df_psi_leaf_obs, "psi_leaf_midday_avg", series, 0.25, 0.75, slice_dates, 
        d1, d2)    

        df_obs_sapflow_slice = get_single_file_slice(df_sap_flow_2023, "Ji_Fasy", series, 0.1, 0.9, slice_dates, d1,d2)

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


        fig = Figure(resolution = (800, 1200))

        # 2. Create Axes for each variable (5 rows, 1 column)
        ax_gpp   = Axis(fig[1, 1], ylabel = "GPP", title = "Site Comparison")
        ax_le    = Axis(fig[2, 1], ylabel = "Latent Heat")
        ax_stem  = Axis(fig[3, 1], ylabel = "Psi Stem")
        ax_leaf  = Axis(fig[4, 1], ylabel = "Psi Leaf")
        ax_flow  = Axis(fig[5, 1], ylabel = "Stem Flow", xlabel = "Time")

        #print(names(df_obs_gpp_slice))

        lines!(ax_gpp,  df_obs_gpp_slice.DateTime, df_obs_gpp_slice.mean,  color = :black, label = "Observed", alpha= 0.5);
        lines!(ax_le,   df_obs_le_slice.DateTime, df_obs_le_slice.mean,  color = :black, alpha= 0.5);
        lines!(ax_stem, df_obs_psi_stem_slice.DateTime, df_obs_psi_stem_slice.mean, color = :black, alpha= 0.5);
        scatter!(ax_leaf, df_obs_psi_leaf_slice.DateTime, df_obs_psi_leaf_slice.mean, color = :black, markersize = 8);
        lines!(ax_flow, df_obs_sapflow_slice.DateTime, df_obs_sapflow_slice.mean * 2.0,    color = :black, alpha= 0.5);

    
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

            df_mod_gpp = get_single_file_slice(qoutput, "gpp_avg", Fluxnetdata,  series, 0.1, 0.9, slice_dates, d1 ,d2);
            df_mod_le = get_single_file_slice(qoutput, "qle_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2);
            df_mod_psi_stem = get_single_file_slice(qoutput, "psi_stem_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2);
            df_mod_psi_leaf = get_single_file_slice(qoutput, "psi_leaf_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2);
            df_mod_stem_flow = get_single_file_slice(qoutput, "stem_flow_per_sap_area_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2);

            # index = findfirst(==(parse(Int,short)), df_param.fid)

            lines!(ax_gpp,  df_mod_gpp.DateTime,  df_mod_gpp.mean,  label = short, alpha = 0.5);
            lines!(ax_le,   df_mod_le.DateTime,   -df_mod_le.mean, alpha= 0.5);
            lines!(ax_stem, df_mod_psi_stem.DateTime, df_mod_psi_stem.mean, alpha = 0.5);
            lines!(ax_leaf, df_mod_psi_leaf.DateTime, df_mod_psi_leaf.mean, alpha = 0.5);
            lines!(ax_flow,  df_mod_stem_flow.DateTime,  df_mod_stem_flow.mean * 1000.0, alpha = 0.5);
            

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
    # Save as a standard PNG
    print(joinpath(post_process_dir, "$name.png"))
    save(joinpath(post_process_dir, "$name.png"), fig)
    
    #CSV.write(joinpath(post_process_dir,"params_rmse_2024.csv"), df_param)
end

root_output_folder= "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2024_bench/51_run_transient_slurm_array_mort_hyd_fail_mort_g1/output"
id, d1, d2 = "17217", DateTime("2018-05-01"), DateTime("2018-10-30")
quincy_output = joinpath(root_output_folder, id)


calculate_mod_obs_rmse_2024(quincy_output, obs, id,d1, d2)
