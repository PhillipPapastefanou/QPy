using PyPlot
using CSV
using DataFrames
using PyCall
mdates = pyimport("matplotlib.dates")
mticker = pyimport("matplotlib.ticker")

include("../../../../src/postprocessing/julia/core/qcomparer.jl")

hainich_obs = init_hainich_obs();
df_fnet_22 = hainich_obs.df_fnet_22
df_fnet_24 = hainich_obs.df_fnet_24
df_psi_stem_obs = hainich_obs.df_psi_stem_obs
df_sap_flow_2023 = hainich_obs.df_sap_flow_2023


rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/12_std_transient_slurm_array"

run_collections = QMultiRunCollections(QOutputCollection[], String[])
full_dir_paths = filter(isdir, readdir("$rt_path_hyd/output", join=true))
postdir = joinpath(rt_path_hyd, "post")
plt_dir = postdir

indexes_all = 0:(length(full_dir_paths)-1)
indexes_all[end]

start_time = time()
last_report = start_time

first_index = true
qoutput = nothing
cats = nothing
sim_type_times=nothing

for i in indexes_all

    i_str = string(i)
    folder = "$rt_path_hyd/output/$i_str"

    if first_index 
        qoutput = read_quincy_site_output(folder)
        cats = qoutput.cats
        sim_type_times = qoutput.sim_type_times
        first_index = false
    else
        qoutput = deepcopy(qoutput)
        #We need to override the file paths
        for sim_type_t in sim_type_times
            for cat in cats
                filename = joinpath(folder, cat*"_"*sim_type_t*".nc")
                qoutput.data[sim_type_t][cat].filename = filename 
            end
        end

    end
    push!(run_collections.idstr, i_str);
    push!(run_collections.output, qoutput);
    last_report = progress_report(i, indexes_all[end], start_time, last_report)
end



rmse_data_path = joinpath(rt_path_hyd, "post", "params_rmse.csv")

df = CSV.read(rmse_data_path, DataFrame)
#vscodedisplay(df)

soil_water_types = unique(df.soil_pyhs_ret)
fids = Int[]
fids_str = String[]
for swr in soil_water_types 
    best_row = sort(filter(row -> (row.soil_pyhs_ret == swr && abs(row.silt - 0.3) < 0.01 && abs(row.sand - 0.2) < 0.01), df), :le_rmse_full)[1,:]
    #best_row = sort(filter(row -> (abs(row.sand - 30) < 20), df), :le_rmse_full)[1,:]
    #best_row = sort(filter(row -> (row.soil_pyhs_ret == swr), df), :le_rmse_full)[1,:]
    push!(fids , best_row.fid)
    push!(fids_str, string(best_row.fid))
end

fids_str


run_sel = run_collections[fids_str];


date_ranges = [
("23", DateTime("2023-07-01"), DateTime("2023-10-30"), DailySeries),
("full", DateTime("2000-01-01"), DateTime("2024-12-31"), DailyAvg),
("03", DateTime("2003-05-01"), DateTime("2003-10-30"), DailySeries),
("18", DateTime("2018-06-01"), DateTime("2018-10-30"), DailySeries),
("19", DateTime("2019-04-01"), DateTime("2018-08-31"), DailySeries)
]


for (ystr, d1, d2, series) in date_ranges


    fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
    pltname = "fluxes"
    varname ="gpp_avg"
    list_gpp = get_multi_file_slice(run_sel, varname, 
    Fluxnetdata, series,
    0.1, 0.9, slice_dates, d1, d2); 
    varname ="qle_avg"
    list_le = get_multi_file_slice(run_sel, varname, 
    Fluxnetdata, series,
    0.1, 0.9, slice_dates, d1, d2); 

    if year(d1) < 2023
        df_obs_gpp_slice = get_single_file_slice(df_fnet_22, "GPP", series, 0.05, 0.95,
        slice_dates, 
        d1, d2)

        df_obs_le_slice = get_single_file_slice(df_fnet_22, "LE", series, 0.05, 0.95,
        slice_dates, 
        d1, d2)
    else
        df_obs_gpp_slice = get_single_file_slice(df_fnet_24, "GPP", series, 0.05, 0.95,
        slice_dates, 
        d1, d2)

        df_obs_le_slice = get_single_file_slice(df_fnet_24, "LE", series, 0.05, 0.95,
        slice_dates, 
        d1, d2)
    end


    
    ax = fig.add_subplot(2,1,1)
    for i in 1:length(list_gpp)
            df_join = innerjoin(list_gpp[i], df_obs_gpp_slice, on = :DateTime, makeunique=true)
            rmse = round(sqrt(mean((df_join.mean .- df_join.mean_1).^2)), sigdigits =2)
            ax.plot(list_gpp[i][!,:DateTime], list_gpp[i][!,:mean], label="$(soil_water_types[i]) RMSE: $rmse" , alpha= 0.7)
    end
    ax.plot(df_obs_gpp_slice[!,:DateTime], df_obs_gpp_slice[!,:mean], label = "obs", color = "black", alpha= 0.7)
    ax.set_ylim((0, 16))

    if ystr == "full"
        # Format ticks: show only abbreviated month names
        ax = gca()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

        # Optionally: set ticks to appear once per month
        ax.xaxis.set_major_locator(mdates.MonthLocator())
    end
    ax.set_ylabel("GPP [μmol C m-2 s-1]")

    ax.legend()

    ax = fig.add_subplot(2,1,2)
    for i in 1:length(list_le)
        df_join = innerjoin(list_le[i], df_obs_le_slice, on = :DateTime, makeunique=true)
        rmse = round(sqrt(mean((abs.(df_join.mean) .- abs.(df_join.mean_1)).^2)), sigdigits =2)
        ax.plot(list_le[i][!,:DateTime], -list_le[i][!,:mean], label="$(soil_water_types[i]) RMSE: $rmse" , alpha= 0.7)
    end
    ax.plot(df_obs_le_slice[!,:DateTime], df_obs_le_slice[!,:mean], label = "obs", color = "black", alpha= 0.7)
    ax.set_ylim((0, 160))
    ax.set_ylabel("LE [W m-2 s-1]")
    if ystr == "full"
        # Format ticks: show only abbreviated month names
        ax = gca()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

        # Optionally: set ticks to appear once per month
        ax.xaxis.set_major_locator(mdates.MonthLocator())
    end
    ax.legend()
    PyPlot.savefig(joinpath(plt_dir,"$(pltname)_$ystr.png"))
    PyPlot.close(fig)

end




soil_depth = [ 0.065, 0.065, 0.065, 0.0699001, 0.09755344, 0.1361468, 
    0.1900082, 0.2651778, 0.3700854, 0.5164957, 0.7208278, 1.005996, 
    1.403981, 1.959413, 2.569414]

date_ranges = [
("23", DateTime("2023-05-01"), DateTime("2023-9-30"), DailySeries),
("full", DateTime("2000-01-01"), DateTime("2024-12-31"), MonthlySeries),
("03", DateTime("2003-05-01"), DateTime("2003-9-30"), DailySeries),
("18", DateTime("2018-05-01"), DateTime("2018-9-30"), DailySeries),
("19", DateTime("2019-04-01"), DateTime("2019-08-31"), DailySeries)
]


run_sel
soil_water_types

cols = ["#82CFFD",   # light blue
 "#4FA5E0",   # medium blue
 "#F2A65A",   # soft orange transition
 "#FF7A1A",   # strong orange
 "#7A3C10",   # dark burnt orange → near black transition
 "#000000"]   # black



for (ystr, d1, d2, series) in date_ranges
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    axes =  vec(permutedims(axes))


    pltname = "wcont"   

    for sl  in 1:6

        dates , listout = get_multi_file_slice_layered(run_sel, "water_content_soil_L", 
        Fluxnetdata, series,
        0.25, 0.75, sl, slice_dates, d1, d2);

        id = 1
        for ax in axes 
            ax.plot(listout[id][!, :DateTime], listout[id][!, :mean]/soil_depth[sl], label =sl, color = cols[sl])
            #ax_jsb.set_yscale("log")
            ax.set_title("$(soil_water_types[id])")
            ax.set_ylim((0.15,0.47))
            ax.tick_params(axis="x", labelrotation=60)
            ax.set_ylabel("θ [-]")
            ax.legend()
            id +=1 
        end

    end
    PyPlot.subplots_adjust(hspace = 0.5)

    PyPlot.savefig(joinpath(plt_dir,"$(pltname)_$ystr.png"))
    PyPlot.close(fig)
end




for (ystr, d1, d2, series) in date_ranges
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    axes =  vec(permutedims(axes))


    pltname = "water_potential_soil_L"   

    for sl  in 1:6

        dates , listout = get_multi_file_slice_layered(run_sel, "water_potential_soil_L", 
        Fluxnetdata, series,
        0.25, 0.75, sl, slice_dates, d1, d2);

        id = 1
        for ax in axes 
            ax.plot(listout[id][!, :DateTime], listout[id][!, :mean], label =sl, color= cols[sl])
            #ax_jsb.set_yscale("log")
            ax.set_title("$(soil_water_types[id])")
            ax.tick_params(axis="x", labelrotation=60)
            ax.set_ylabel("Ψ soil [MPa]")
            id +=1 
            ax.legend()
        end

    end
    PyPlot.subplots_adjust(hspace = 0.5)

    PyPlot.savefig(joinpath(plt_dir,"$(pltname)_$ystr.png"))
    PyPlot.close(fig)
end





for (ystr, d1, d2, series) in date_ranges
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    axes =  vec(permutedims(axes))


    pltname = "hyd_cond_avg_L"   

    for sl  in 1:6

        dates , listout = get_multi_file_slice_layered(run_sel, "hyd_cond_avg_L", 
        Fluxnetdata, series,
        0.25, 0.75, sl, slice_dates, d1, d2);

        id = 1
        for ax in axes 
            ax.plot(listout[id][!, :DateTime], listout[id][!, :mean], label =sl, color= cols[sl])
            ax.set_yscale("log")
            ax.set_ylim((10^-15, 10^-6))
            ax.set_title("$(soil_water_types[id])")
            ax.tick_params(axis="x", labelrotation=60)
            ax.set_ylabel("Ψ soil [MPa]")
            ax.legend()
            id +=1 
        end

    end
    PyPlot.subplots_adjust(hspace = 0.5)

    PyPlot.savefig(joinpath(plt_dir,"$(pltname)_$ystr.png"))
    PyPlot.close(fig)
end