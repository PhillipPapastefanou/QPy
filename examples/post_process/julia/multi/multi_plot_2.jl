include("../../../../src/postprocessing/julia/core/qslicer.jl")
using PyPlot
using CSV

script_dir = dirname(@__FILE__)

rtobspath = "/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed"
full_path_df_22 = joinpath(rtobspath, "Fluxnet2000_2021_eval.csv")
df_fnet_22 = CSV.read(full_path_df_22, DataFrame, dateformat = Dict(:time => "yyyy-mm-dd HH:MM:SS"))
rename!(df_fnet_22, :time => :DateTime)
df_fnet_22 = dropmissing(df_fnet_22)

rt_path_hyd = "/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/science/phillip/output/03_transient_fluxnet"
run_collections = QMultiRunCollections(QOutputCollection[], String[])
indexes = [0,1]

plt_dir = joinpath("$script_dir", "plots")
if !isdir(plt_dir)
    mkdir(plt_dir)
end


for i in indexes
    i_str = string(i)
    folder = "$rt_path_hyd/output/$i_str"
    push!(run_collections.idstr, i_str);
    push!(run_collections.output, read_quincy_site_output(folder));
    println(i)
end

pltname = "test"
df_vec = get_multi_file_slice(run_collections, "gpp_avg", 
Fluxnetdata, DailySeries,
0.25, 0.75, slice_dates, DateTime("2018-05-01"), DateTime("2018-10-30"))


fig = PyPlot.figure(figsize=(12, 6), layout="constrained")
ax = fig.add_subplot(1,1,1)
for i in 1:2
    ax.plot(df_vec[i][:,"DateTime"], df_vec[i][:,"mean"])
end

PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)

h  = run_collections.output[1].var_names
run_collections.output[1]


fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "LAI"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)

    df_vec = get_multi_file_slice(run_collections, "LAI", 
    Fluxnetdata, DailySeries,
    0.25, 0.75, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));
    ax_jsb.plot(df_vec[1][:,"DateTime"], df_vec[1][:,"mean"])
    #ax_jsb.set_yscale("log")
    ax_jsb.set_title("JSB - $year")
    #ax_jsb.set_ylim((0,12))
    ax_jsb.tick_params(axis="x", labelrotation=60)
    ax_jsb.set_ylabel("LAI [m2 m-2]")

    ax_spq.plot(df_vec[2][:,"DateTime"], df_vec[2][:,"mean"])
    #ax_spq.set_yscale("log")
    ax_spq.set_title("QUINCY - $year")    
    #ax_spq.set_ylim((0,12))

    ax_spq.tick_params(axis="x", labelrotation=60)
    ax_spq.set_ylabel("LAI [m2 m-2]")
    yi = yi +2

    ax_jsb.legend()
    ax_spq.legend()
end

PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)


fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "veg_c"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)

    df_vec = get_multi_file_slice(run_collections, "total_veg_c", 
    Fluxnetdata, DailySeries,
    0.25, 0.75, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));
    ax_jsb.plot(df_vec[1][:,"DateTime"], df_vec[1][:,"mean"])
    #ax_jsb.set_yscale("log")
    ax_jsb.set_title("JSB - $year")
    #ax_jsb.set_ylim((0,12))
    ax_jsb.tick_params(axis="x", labelrotation=60)
    ax_jsb.set_ylabel("cveg [mol C m-2]")

    ax_spq.plot(df_vec[2][:,"DateTime"], df_vec[2][:,"mean"])
    #ax_spq.set_yscale("log")
    ax_spq.set_title("QUINCY - $year")    
    #ax_spq.set_ylim((0,12))

    ax_spq.tick_params(axis="x", labelrotation=60)
    ax_spq.set_ylabel("cveg [mol C m-2]")
    yi = yi +2

    ax_jsb.legend()
ax_spq.legend()
end

PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)


fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "gpp"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)


    df_slice_obs = get_single_file_slice(df_fnet_22, "GPP", DailySeries, 0.05, 0.95,slice_dates, 
    DateTime("$year-04-01"), DateTime("$year-11-30"))    
    df_slice_obs = sort(df_slice_obs, :DateTime)

    df_vec = get_multi_file_slice(run_collections, "gpp_avg", 
    Fluxnetdata, DailySeries,
    0.25, 0.75, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));
    ax_jsb.plot(df_vec[1][:,"DateTime"], df_vec[1][:,"mean"])
    #ax_jsb.set_yscale("log")
    ax_jsb.set_title("JSB - $year")
    ax_jsb.set_ylim((0,15))
    ax_jsb.tick_params(axis="x", labelrotation=60)
    ax_jsb.set_ylabel("gpp [μmol C s-1 m-2]")
    ax_jsb.plot(df_slice_obs[:, "DateTime"], df_slice_obs[:, "mean"], label ="obs")

    ax_spq.plot(df_vec[2][:,"DateTime"], df_vec[2][:,"mean"])
    #ax_spq.set_yscale("log")
    ax_spq.set_title("SPQ - $year")    
    ax_spq.set_ylim((0,15))

    ax_spq.tick_params(axis="x", labelrotation=60)
    ax_spq.set_ylabel("gpp [μmol C s-1 m-2]")
    ax_spq.plot(df_slice_obs[:, "DateTime"], df_slice_obs[:, "mean"], label ="obs")
    yi = yi +2
    ax_jsb.legend()
    ax_spq.legend()
end

PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)


fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "qle_avg"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)

    df_slice_obs = get_single_file_slice(df_fnet_22, "LE", DailySeries, 0.05, 0.95,  slice_dates, DateTime("$year-01-01"), DateTime("$year-12-31"))    

    
    
    df_slice_obs = sort(df_slice_obs, :DateTime)

    df_vec = get_multi_file_slice(run_collections, "qle_avg", 
    Fluxnetdata, DailySeries,
    0.25, 0.75, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));
    ax_jsb.plot(df_vec[1][:,"DateTime"], -df_vec[1][:,"mean"])
    #ax_jsb.set_yscale("log")
    ax_jsb.set_title("JSB - $year")
    #ax_jsb.set_ylim((0,6 *10^-5))
    ax_jsb.tick_params(axis="x", labelrotation=60)
    #ax_jsb.set_ylabel("T [kg s-1 m-2]")

    ax_jsb.plot(df_slice_obs[:, "DateTime"], df_slice_obs[:, "mean"], label ="obs")

    ax_spq.plot(df_vec[2][:,"DateTime"], -df_vec[2][:,"mean"])
    #ax_spq.set_yscale("log")
    ax_spq.set_title("SPQ - $year")    
    #ax_spq.set_ylim((0,6 *10^-5))

    ax_spq.plot(df_slice_obs[:, "DateTime"], df_slice_obs[:, "mean"], label ="obs")

    ax_spq.tick_params(axis="x", labelrotation=60)
    #ax_spq.set_ylabel("T [kg s-1 m-2]")
    yi = yi +2

    ax_jsb.legend()
ax_spq.legend() 
end

PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)



fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "psi_soil"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)
    for sl  in 1:6
        df_vec = get_multi_file_slice_layered(run_collections, "water_potential_soil_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));
        ax_jsb.plot(df_vec[1][:,"DateTime"], df_vec[1][:,"mean"], label =sl)
        #ax_jsb.set_yscale("log")
        ax_jsb.set_title("JSB - $year")
        ax_jsb.set_ylim((-3,0))
        ax_jsb.tick_params(axis="x", labelrotation=60)
        ax_jsb.set_ylabel("ψ [MPa]")

        ax_spq.plot(df_vec[2][:,"DateTime"], df_vec[2][:,"mean"], label =sl)
        #ax_spq.set_yscale("log")
        ax_spq.set_title("SPQ - $year")    
        ax_spq.set_ylim((-3,0))
        ax_spq.tick_params(axis="x", labelrotation=60)
        ax_spq.set_ylabel("ψ [MPa]")
    end
    yi = yi + 2
    ax_jsb.legend()
    ax_spq.legend()
end
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)



fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "conductivity"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)
    for sl  in 1:6
        df_vec = get_multi_file_slice_layered(run_collections, "hyd_cond_avg_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));
        ax_jsb.plot(df_vec[1][:,"DateTime"], df_vec[1][:,"mean"], label =sl)
        ax_jsb.set_yscale("log")
        ax_jsb.set_title("JSB - $year")
        ax_jsb.set_ylim((10^-15, 10^-7))
        ax_jsb.tick_params(axis="x", labelrotation=60)
        ax_jsb.set_ylabel("K [m s -1]")

        ax_spq.plot(df_vec[2][:,"DateTime"], df_vec[2][:,"mean"], label =sl)
        ax_spq.set_yscale("log")
        ax_spq.set_title("SPQ - $year")    
        ax_spq.set_ylim((10^-15, 10^-7))
        ax_spq.tick_params(axis="x", labelrotation=60)
        ax_spq.set_ylabel("K [m s -1]")
    end
    yi = yi + 2
    ax_jsb.legend()
    ax_spq.legend()
end
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)




soil_depth = [ 0.065, 0.065, 0.065, 0.0699001, 0.09755344, 0.1361468, 
    0.1900082, 0.2651778, 0.3700854, 0.5164957, 0.7208278, 1.005996, 
    1.403981, 1.959413, 2.569414]

fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "wcont"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)
    for sl  in 1:6
        df_vec = get_multi_file_slice_layered(run_collections, "water_content_soil_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));
        ax_jsb.plot(df_vec[1][:,"DateTime"], df_vec[1][:,"mean"]/soil_depth[sl], label =sl)
        #ax_jsb.set_yscale("log")
        ax_jsb.set_title("JSB - $year")
        ax_jsb.set_ylim((0.15,0.47))
        ax_jsb.tick_params(axis="x", labelrotation=60)
        ax_jsb.set_ylabel("θ [-]")

        ax_spq.plot(df_vec[2][:,"DateTime"], df_vec[2][:,"mean"]/soil_depth[sl], label =sl)
        # ax_spq.set_yscale("log")
        ax_spq.set_title("SPQ - $year")  
        ax_spq.set_ylim((0.15,0.47))  
        #ax_spq.set_ylim((10^-15, 10^-7))
        ax_spq.tick_params(axis="x", labelrotation=60)
        ax_spq.set_ylabel("θ [-]")
    end
    yi = yi + 2
    ax_jsb.legend()
    ax_spq.legend()
end
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)


df_vec = get_multi_file_slice_layered(run_collections, "water_potential_soil_L", 
Fluxnetdata, DailySeries,
0.25, 0.75, layer, slice_dates, DateTime("2018-05-01"), DateTime("2018-10-30"));

fig = PyPlot.figure(figsize=(12, 6), layout="constrained")
ax = fig.add_subplot(1, 1, 1)
for i in 1:2
    ax.plot(df_vec[i][:,"DateTime"], df_vec[i][:,"mean"])
end

PyPlot.savefig(joinpath(plt_dir,"2$pltname.png"))
PyPlot.close(fig)

# df_vec = get_multi_file_slice(run_collections, "hyd_cond_avg", 
# Fluxnetdata, DailySeries,
# 0.25, 0.75, slice_dates, DateTime("2018-07-01"), DateTime("2018-09-30"));

# df_vec
