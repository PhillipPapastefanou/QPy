include("qoutput.jl")
include("qtypes.jl")
include("qsite_reader.jl")
include("qslicer.jl")

using Statistics, VectorizedStatistics
using DataFrames
using Dates
using Base.Filesystem: basename
using CSV
using Base.Threads


mutable struct HainichObs
    df_fnet_22::DataFrame
    df_fnet_24::DataFrame
    df_psi_stem_obs::DataFrame
    df_psi_leaf_obs::DataFrame
    df_sap_flow_2023::DataFrame
end


function init_hainich_obs()

rtobspath = "/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed"

    # 2000–2021
    full_path_df_22 = joinpath(rtobspath, "Fluxnet2000_2021_eval.csv")
    df_fnet_22 = CSV.read(
        full_path_df_22,
        DataFrame;
        types      = Dict(:time => DateTime),
        dateformat = Dict(:time => dateformat"yyyy-mm-dd HH:MM:SS"),
    )
    rename!(df_fnet_22, :time => :DateTime)
    df_fnet_22 = dropmissing(df_fnet_22)

    # 2023–2024
    full_path_df_24 = joinpath(rtobspath, "Fluxnet2023_2024_eval.csv")
    df_fnet_24 = CSV.read(
        full_path_df_24,
        DataFrame;
        types      = Dict(:date => DateTime),
        dateformat = Dict(:date => dateformat"yyyy-mm-dd HH:MM:SS"),
    )
    rename!(df_fnet_24, :date => :DateTime)

    # Psi stem
    full_path_psi_stem = joinpath(rtobspath, "psi_stem_2024_flora.csv")
    df_psi_stem_obs = CSV.read(
        full_path_psi_stem,
        DataFrame;
        types      = Dict(:date => DateTime),
        dateformat = Dict(:date => dateformat"yyyy-mm-dd HH:MM:SS"),
    )
    rename!(df_psi_stem_obs, :date => :DateTime)


    # Psi leaf
    full_path_psi_leaf = joinpath(rtobspath, "psi_leaf_midday_2023_2024_avg.csv")
    df_psi_leaf_obs = CSV.read(
        full_path_psi_leaf,
        DataFrame;
        types      = Dict(:date => DateTime),
        dateformat = Dict(:date => dateformat"yyyy-mm-dd HH:MM:SS"),
    )
    rename!(df_psi_leaf_obs, :date => :DateTime)

    # Sap flow
    full_path_sap_flow_2023_2024 = joinpath(rtobspath, "DE-Hai_forcing_30min_20230101_20251227.csv")
    df_sap_flow_2023 = CSV.read(
        full_path_sap_flow_2023_2024,
        DataFrame;
        types = Dict(:datetime => String)
    )

    df_sap_flow_2023.datetime = DateTime.(first.(df_sap_flow_2023.datetime, 19), dateformat"yyyy-mm-dd HH:MM:SS")
    rename!(df_sap_flow_2023, :datetime => :DateTime)
    df_sap_flow_2023 = filter(row -> !ismissing(row["Ji_Fasy"]), df_sap_flow_2023)
    df_sap_flow_2023[!, "Ji_Fasy"] = convert(Vector{Float64}, df_sap_flow_2023[!, "Ji_Fasy"])
    df_sap_flow_2023[df_sap_flow_2023[:, "Ji_Fasy"] .< 0.0, "Ji_Fasy"] .= 0.0

    return HainichObs(df_fnet_22, df_fnet_24, df_psi_stem_obs, df_psi_leaf_obs, df_sap_flow_2023)

end

function calculate_mod_obs_rmse_2024(quincy_output::String, hainich_obs::HainichObs; check_all = false)
    df_fnet_22 = hainich_obs.df_fnet_22
    df_fnet_24 = hainich_obs.df_fnet_24
    df_psi_stem_obs = hainich_obs.df_psi_stem_obs
    df_psi_leaf_obs = hainich_obs.df_psi_leaf_obs
    df_sap_flow_2023 = hainich_obs.df_sap_flow_2023


    date_ranges = [
    ("24", DateTime("2024-05-01"), DateTime("2024-10-30")),
    ("full", DateTime("2000-01-01"), DateTime("2024-12-31")),
    ("03", DateTime("2003-05-01"), DateTime("2003-10-30")),
     ("18", DateTime("2018-05-01"), DateTime("2018-10-30"))
    ]


    post_process_dir = joinpath("$quincy_output", "post")
    if !isdir(post_process_dir)
        mkdir(post_process_dir)
    end

    full_dir_paths = filter(isdir, readdir("$quincy_output/output", join=true))
    short_dir_paths = basename.(full_dir_paths)


    df_param = CSV.read(joinpath(quincy_output, "parameters.csv"), DataFrame)

    series = ThirtyMinSeries


    for (ystr, d1, d2) in date_ranges

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

        df_obs_sapflow_slice = get_single_file_slice(df_sap_flow_2023, "Ji_Fasy", series, 0.1, 0.9, slice_dates, DateTime("2023-06-01"), DateTime("2024-11-01"))  

        start_time = time()
        last_report = start_time

        df_param[!, Symbol("gpp_rmse_$ystr")] .= NaN
        df_param[!, Symbol("le_rmse_$ystr")] .= NaN
        df_param[!, Symbol("psi_stem_rmse_$ystr")] .= NaN
        df_param[!, Symbol("psi_leaf_rmse_$ystr")] .= NaN
        df_param[!, Symbol("stem_flow_rmse_$ystr")] .= NaN
        df_param[!, Symbol("stem_flow_rmse_05_$ystr")] .= NaN
        df_param[!, Symbol("stem_flow_rmse_2_$ystr")] .= NaN
        df_param[!, Symbol("stem_flow_rmse_025_$ystr")] .= NaN
        df_param[!, Symbol("G_rmse_05_$ystr")] .= NaN
        df_param[!, Symbol("G_rmse_$ystr")] .= NaN
        df_param[!, Symbol("G_rmse_2_$ystr")] .= NaN
        df_param[!, Symbol("G_rmse_025_$ystr")] .= NaN
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
                                qoutput.data[sim_type_t][cat].filename = filename      
                    end
                end
            end

            df_mod_gpp = get_single_file_slice(qoutput, "gpp_avg", Fluxnetdata,  series, 0.1, 0.9, slice_dates, d1 ,d2);
            df_mod_le = get_single_file_slice(qoutput, "qle_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2);
            df_mod_psi_stem = get_single_file_slice(qoutput, "psi_stem_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2);
            df_mod_psi_leaf = get_single_file_slice(qoutput, "psi_leaf_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2);
            df_mod_stem_flow = get_single_file_slice(qoutput, "stem_flow_per_sap_area_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2);
            df_mod_G = get_single_file_slice(qoutput, "G_per_sap_area_avg", Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2);

            index = findfirst(==(parse(Int,short)), df_param.fid)

            df_join = innerjoin(df_mod_gpp, df_obs_gpp_slice, on = :DateTime, makeunique=true)
            rmse = sqrt(mean((df_join.mean .- df_join.mean_1).^2))
            df_param[index, Symbol("gpp_rmse_$ystr")] = rmse

          
            df_join = innerjoin(df_mod_le, df_obs_le_slice, on = :DateTime, makeunique=true)
            rmse = sqrt(mean((abs.(df_join.mean) .- abs.(df_join.mean_1)).^2))
            df_param[index,Symbol("le_rmse_$ystr")] = rmse

            df_join = innerjoin(df_mod_psi_stem, df_obs_psi_stem_slice, on = :DateTime, makeunique=true)
            rmse = sqrt(mean((df_join.mean .- df_join.mean_1).^2))
            df_param[index, Symbol("psi_stem_rmse_$ystr")] = rmse

            df_join = innerjoin(df_mod_psi_leaf, df_obs_psi_leaf_slice, on = :DateTime, makeunique=true)
            rmse = sqrt(mean((df_join.mean .- df_join.mean_1).^2))
            df_param[index, Symbol("psi_leaf_rmse_$ystr")] = rmse

            df_join = innerjoin(df_mod_stem_flow, df_obs_sapflow_slice, on = :DateTime, makeunique=true)
            rmse = sqrt(mean((df_join.mean * 1000.0 .- df_join.mean_1).^2))
            df_param[index,Symbol("stem_flow_rmse_$ystr")] = rmse
            rmse = sqrt(mean((0.5 * df_join.mean * 1000.0 .- df_join.mean_1).^2))
            df_param[index,Symbol("stem_flow_rmse_05_$ystr")] = rmse
            rmse = sqrt(mean((0.25 * df_join.mean * 1000.0 .- df_join.mean_1).^2))
            df_param[index,Symbol("stem_flow_rmse_025_$ystr")] = rmse
            rmse = sqrt(mean((2.0 * df_join.mean * 1000.0 .- df_join.mean_1).^2))
            df_param[index,Symbol("stem_flow_rmse_2_$ystr")] = rmse

            df_join = innerjoin(df_mod_G, df_obs_sapflow_slice, on = :DateTime, makeunique=true)
            rmse = sqrt(mean((df_join.mean * 1000.0 .- df_join.mean_1).^2))
            df_param[index,Symbol("G_rmse_$ystr")] = rmse
            rmse = sqrt(mean((0.5 * df_join.mean * 1000.0 .- df_join.mean_1).^2))
            df_param[index,Symbol("G_rmse_05_$ystr")] = rmse
            rmse = sqrt(mean((0.25 * df_join.mean * 1000.0 .- df_join.mean_1).^2))
            df_param[index,Symbol("G_rmse_025_$ystr")] = rmse
            rmse = sqrt(mean((2.0 * df_join.mean * 1000.0 .- df_join.mean_1).^2))
            df_param[index,Symbol("G_rmse_2_$ystr")] = rmse


            last_report = progress_report(i, length(short_dir_paths), start_time, last_report)
        end

    end


    CSV.write(joinpath(post_process_dir,"params_rmse_2024.csv"), df_param)
end





