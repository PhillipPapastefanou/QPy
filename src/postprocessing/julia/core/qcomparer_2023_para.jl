# hyd_auto_analysis_mpi.jl

using MPI
using Dates
using CSV
using DataFrames
using Statistics, VectorizedStatistics
using Base.Filesystem: basename

# Include your custom scripts
include("qoutput.jl")
include("qtypes.jl")
include("qsite_reader.jl")
include("qslicer.jl")

mutable struct HainichObs
    df_fnet_22::DataFrame
    df_fnet_24::DataFrame
    df_psi_stem_obs::DataFrame
    df_psi_leaf_obs::DataFrame
    df_sap_flow_2023::DataFrame
end

function init_hainich_obs()
    rtobspath = "/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed"

    df_fnet_22 = CSV.read(joinpath(rtobspath, "Fluxnet2000_2021_eval.csv"), DataFrame; types = Dict(:time => DateTime), dateformat = Dict(:time => dateformat"yyyy-mm-dd HH:MM:SS"))
    rename!(df_fnet_22, :time => :DateTime)
    df_fnet_22 = dropmissing(df_fnet_22)

    df_fnet_24 = CSV.read(joinpath(rtobspath, "Fluxnet2023_2024_eval.csv"), DataFrame; types = Dict(:date => DateTime), dateformat = Dict(:date => dateformat"yyyy-mm-dd HH:MM:SS"))
    rename!(df_fnet_24, :date => :DateTime)

    df_psi_stem_obs = CSV.read(joinpath(rtobspath, "PsiStem2023.csv"), DataFrame; types = Dict(:date => DateTime), dateformat = Dict(:date => dateformat"yyyy-mm-dd HH:MM:SS"))
    rename!(df_psi_stem_obs, :date => :DateTime)

    df_sap_flow_2023 = CSV.read(joinpath(rtobspath, "Sapflow2023.csv"), DataFrame; types = Dict(:date => DateTime), dateformat = Dict(:date => dateformat"yyyy-mm-dd HH:MM:SS"))
    rename!(df_sap_flow_2023, :date => :DateTime)

    df_psi_leaf_obs = CSV.read(joinpath(rtobspath, "psi_leaf_midday_2023_2024_avg.csv"), DataFrame; types = Dict(:date => DateTime), dateformat = Dict(:date => dateformat"yyyy-mm-dd HH:MM:SS"))
    rename!(df_psi_leaf_obs, :date => :DateTime)

    df_sap_flow_2023 = filter(row -> !ismissing(row["J0.5"]), df_sap_flow_2023)
    df_sap_flow_2023[!, "J0.5"] = convert(Vector{Float64}, df_sap_flow_2023[!, "J0.5"])
    df_sap_flow_2023[df_sap_flow_2023[:, "J0.5"] .< 0.0, "J0.5"] .= 0.0

    return HainichObs(df_fnet_22, df_fnet_24, df_psi_stem_obs, df_psi_leaf_obs, df_sap_flow_2023)
end

function calculate_mod_obs_rmse_2023_mpi(quincy_output::String)



    # 1. Initialize MPI
    MPI.Init()
    comm = MPI.COMM_WORLD
    rank = MPI.Comm_rank(comm)       # IDs from 0 to (Size - 1)
    world_size = MPI.Comm_size(comm) # Total number of processes



    if rank == 0
        println("--- Starting Julia MPI Job with $world_size processes ---")
    end

    hainich_obs = init_hainich_obs()

    date_ranges = [
        ("23", DateTime("2023-05-01"), DateTime("2023-10-30")),
        ("full", DateTime("2000-01-01"), DateTime("2024-12-31")),
        ("03", DateTime("2003-05-01"), DateTime("2003-10-30")),
        ("18", DateTime("2018-05-01"), DateTime("2018-10-30"))
    ]

    post_process_dir = joinpath(quincy_output, "post2")
    if rank == 0 && !isdir(post_process_dir)
        mkdir(post_process_dir)
    end
    MPI.Barrier(comm) # Wait for Rank 0 to create the directory

    full_dir_paths = filter(isdir, readdir(joinpath(quincy_output, "output"), join=true))
    short_dir_paths = basename.(full_dir_paths)
    dir_pairs = collect(zip(full_dir_paths, short_dir_paths))

    # 2. Divide the work among ranks
    my_dirs = dir_pairs[(rank + 1):world_size:length(dir_pairs)]
    println("Rank $rank reporting for duty! I have $(length(my_dirs)) directories to process.")

    df_param = CSV.read(joinpath(quincy_output, "parameters.csv"), DataFrame)
    series = ThirtyMinSeries 

    for (ystr, d1, d2) in date_ranges
        if rank == 0 println("\nProcessing Date Range: $ystr ($d1 to $d2)") end
        
        df_fnet = year(d1) < 2022 ? hainich_obs.df_fnet_22 : hainich_obs.df_fnet_24        

        df_obs_gpp_slice = get_single_file_slice(df_fnet, "GPP", series, 0.05, 0.95, slice_dates, d1, d2)
        df_obs_le_slice = get_single_file_slice(df_fnet, "LE", series, 0.05, 0.95, slice_dates, d1, d2) 
        df_obs_psi_stem_slice = get_single_file_slice(hainich_obs.df_psi_stem_obs, "FAG", series, 0.25, 0.75, slice_dates, d1, d2)    
        df_obs_sapflow_slice = get_single_file_slice(hainich_obs.df_sap_flow_2023, "J0.5", series, 0.1, 0.9, slice_dates, DateTime("2023-06-01"), DateTime("2023-08-01"))  
        df_obs_psi_leaf_slice = get_single_file_slice(hainich_obs.df_psi_leaf_obs, "psi_leaf_midday_avg", series, 0.25, 0.75, slice_dates, d1, d2)    

        # Initialize NaN columns
        prefixes = ["gpp", "le", "psi_stem", "psi_leaf"]
        flow_prefixes = ["stem_flow", "G"]
        multipliers = ["", "_05", "_025", "_2"]
        
        for p in prefixes df_param[!, Symbol("$(p)_rmse_$ystr")] .= NaN end
        for p in flow_prefixes
            for m in multipliers df_param[!, Symbol("$(p)_rmse$(m)_$ystr")] .= NaN end
        end

        standard_vars = [
            (mod_var="gpp_avg",      obs_df=df_obs_gpp_slice,      prefix="gpp",      scale=1.0, use_abs=false),
            (mod_var="qle_avg",      obs_df=df_obs_le_slice,       prefix="le",       scale=1.0, use_abs=true),
            (mod_var="psi_stem_avg", obs_df=df_obs_psi_stem_slice, prefix="psi_stem", scale=1.0, use_abs=false),
            (mod_var="psi_leaf_avg", obs_df=df_obs_psi_leaf_slice, prefix="psi_leaf", scale=1.0, use_abs=false)
        ]
        flow_vars = [
            (mod_var="stem_flow_per_sap_area_avg", obs_df=df_obs_sapflow_slice, prefix="stem_flow", scale=1000.0),
            (mod_var="G_per_sap_area_avg",         obs_df=df_obs_sapflow_slice, prefix="G",         scale=1000.0)
        ]

        # 3. Process assigned directories
        for (full, short) in my_dirs
            local_qoutput = read_quincy_site_output(full)
            index = findfirst(==(parse(Int, short)), df_param.fid)

            for v in standard_vars
                df_mod = get_single_file_slice(local_qoutput, v.mod_var, Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2)
                df_join = innerjoin(df_mod, v.obs_df, on = :DateTime, makeunique=true)
                rmse = v.use_abs ? sqrt(mean((abs.(df_join.mean .* v.scale) .- abs.(df_join.mean_1)).^2)) : sqrt(mean((df_join.mean .* v.scale .- df_join.mean_1).^2))
                df_param[index, Symbol("$(v.prefix)_rmse_$ystr")] = rmse
            end

            for v in flow_vars
                df_mod = get_single_file_slice(local_qoutput, v.mod_var, Fluxnetdata, series, 0.1, 0.9, slice_dates, d1, d2)
                df_join = innerjoin(df_mod, v.obs_df, on = :DateTime, makeunique=true)
                for (mult, suffix) in multipliers
                    rmse = sqrt(mean((mult .* df_join.mean .* v.scale .- df_join.mean_1).^2))
                    df_param[index, Symbol("$(v.prefix)_rmse$(suffix)_$ystr")] = rmse
                end
            end
        end
    end

    # 4. Save a rank-specific temporary CSV file
    rank_file = joinpath(post_process_dir, "params_rmse_2023_rank$(rank).csv")
    CSV.write(rank_file, df_param)
    
    # Wait for all ranks to finish writing their files
    MPI.Barrier(comm)

    # 5. Rank 0 merges the files together
    if rank == 0
        println("All ranks finished! Rank 0 is stitching the results together...")
        final_df = copy(df_param)
        
        for r in 0:(world_size-1)
            temp_df = CSV.read(joinpath(post_process_dir, "params_rmse_2023_rank$(r).csv"), DataFrame)
            for col in names(final_df)
                if col != "fid" 
                    # If the temp_df has a value (not NaN), update the final_df
                    mask = .!isnan.(temp_df[!, col])
                    final_df[mask, col] .= temp_df[mask, col]
                end
            end
            # Clean up temporary rank files
            rm(joinpath(post_process_dir, "params_rmse_2023_rank$(r).csv"))
        end
        
        CSV.write(joinpath(post_process_dir, "params_rmse_2023.csv"), final_df)
        println("Successfully wrote final params_rmse_2023.csv!")
    end
end