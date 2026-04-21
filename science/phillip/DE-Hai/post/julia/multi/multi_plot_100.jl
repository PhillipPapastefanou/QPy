include("../../../../src/postprocessing/julia/core/qslicer.jl")
using PyPlot
using CSV

script_dir = dirname(@__FILE__)

rtobspath = "/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed"
full_path_df_22 = joinpath(rtobspath, "Fluxnet2000_2021_eval.csv")
df_fnet_22 = CSV.read(full_path_df_22, DataFrame, dateformat = Dict(:time => "yyyy-mm-dd HH:MM:SS"))
rename!(df_fnet_22, :time => :DateTime)
df_fnet_22 = dropmissing(df_fnet_22)

rt_path_hyd = "/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/science/phillip/output/04_transient_fluxnet"
run_collections_jsb = QMultiRunCollections(QOutputCollection[], String[])
run_collections_spq = QMultiRunCollections(QOutputCollection[], String[])
indexes_spq = range(0,49)
indexes_jsb = range(50,99)

using CSV

parameters = CSV.read(joinpath(rt_path_hyd, "parameters.csv"), DataFrame)
parameters

plt_dir = joinpath("$script_dir", "plots", "100")
if !isdir(plt_dir)
    mkdir(plt_dir)
end


for i in indexes_jsb
    i_str = string(i)
    folder = "$rt_path_hyd/output/$i_str"
    push!(run_collections_jsb.idstr, i_str);
    push!(run_collections_jsb.output, read_quincy_site_output(folder));
    println(i)
end

for i in indexes_spq
    i_str = string(i)
    folder = "$rt_path_hyd/output/$i_str"
    push!(run_collections_spq.idstr, i_str);
    push!(run_collections_spq.output, read_quincy_site_output(folder));
    println(i)
end

print(run_collections_spq.output[1].var_names)


fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "veg_c"
varname ="total_veg_c"
yi = 1
@time for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)

    df_vec_jsb = get_multi_file_slice_avg(run_collections_jsb, varname, 
    Fluxnetdata, DailySeries,
    0.1, 0.9, slice_dates, DateTime("$year-05-01"), DateTime("$year-10-30"))
    df_vec_spq = get_multi_file_slice_avg(run_collections_spq, varname, 
    Fluxnetdata, DailySeries,
    0.1, 0.9, slice_dates, DateTime("$year-05-01"), DateTime("$year-10-30"))


    ax_jsb.plot(df_vec_jsb[:,"DateTime"], df_vec_jsb[:,"mean"])
    ax_jsb.fill_between(df_vec_jsb[:,"DateTime"], df_vec_jsb[:,"qlow"], df_vec_jsb[:,"qup"], alpha = 0.3)

    #ax_jsb.set_yscale("log")
    ax_jsb.set_title("JSB - $year")
    #ax_jsb.set_ylim((0,12))
    ax_jsb.tick_params(axis="x", labelrotation=60)
    #ax_jsb.set_ylabel("LAI [m2 m-2]")

    ax_spq.plot(df_vec_spq[:,"DateTime"], df_vec_spq[:,"mean"])
    ax_spq.fill_between(df_vec_jsb[:,"DateTime"], df_vec_spq[:,"qlow"], df_vec_spq[:,"qup"], alpha = 0.3)
    #ax_spq.set_yscale("log")
    ax_spq.set_title("QUINCY - $year")    
    #ax_spq.set_ylim((0,12))

    ax_spq.tick_params(axis="x", labelrotation=60)
    #ax_spq.set_ylabel("LAI [m2 m-2]")
    yi = yi +2

    ax_jsb.legend()
    ax_spq.legend()
end
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)



fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "gpp"
varname ="gpp_avg"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)

    df_vec_jsb = get_multi_file_slice_avg(run_collections_jsb, varname, 
    Fluxnetdata, DailySeries,
    0.1, 0.9, slice_dates, DateTime("$year-05-01"), DateTime("$year-10-30"))
    df_vec_spq = get_multi_file_slice_avg(run_collections_spq, varname, 
    Fluxnetdata, DailySeries,
    0.1, 0.9, slice_dates, DateTime("$year-05-01"), DateTime("$year-10-30"))

    df_slice_obs = get_single_file_slice(df_fnet_22, "GPP", DailySeries, 0.05, 0.95,slice_dates, 
    DateTime("$year-04-01"), DateTime("$year-11-30"))    
    df_slice_obs = sort(df_slice_obs, :DateTime)


    ax_jsb.plot(df_vec_jsb[:,"DateTime"], df_vec_jsb[:,"mean"])
    ax_jsb.fill_between(df_vec_jsb[:,"DateTime"], df_vec_jsb[:,"qlow"], df_vec_jsb[:,"qup"], alpha = 0.3)

    #ax_jsb.set_yscale("log")
    ax_jsb.set_title("JSB - $year")
    #ax_jsb.set_ylim((0,12))
    ax_jsb.tick_params(axis="x", labelrotation=60)
    #ax_jsb.set_ylabel("LAI [m2 m-2]")
    ax_jsb.plot(df_slice_obs[:, "DateTime"], df_slice_obs[:, "mean"], label ="obs")

    ax_spq.plot(df_vec_spq[:,"DateTime"], df_vec_spq[:,"mean"])
    ax_spq.fill_between(df_vec_jsb[:,"DateTime"], df_vec_spq[:,"qlow"], df_vec_spq[:,"qup"], alpha = 0.3)
    #ax_spq.set_yscale("log")
    ax_spq.set_title("QUINCY - $year")    
    #ax_spq.set_ylim((0,12))
    ax_spq.plot(df_slice_obs[:, "DateTime"], df_slice_obs[:, "mean"], label ="obs")

    ax_spq.tick_params(axis="x", labelrotation=60)
    #ax_spq.set_ylabel("LAI [m2 m-2]")
    yi = yi +2

    ax_jsb.legend()
    ax_spq.legend()
end
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)



fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "qle"
varname ="qle_avg"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)

    df_vec_jsb = get_multi_file_slice_avg(run_collections_jsb, varname, 
    Fluxnetdata, DailySeries,
    0.1, 0.9, slice_dates, DateTime("$year-05-01"), DateTime("$year-10-30"))
    df_vec_spq = get_multi_file_slice_avg(run_collections_spq, varname, 
    Fluxnetdata, DailySeries,
    0.1, 0.9, slice_dates, DateTime("$year-05-01"), DateTime("$year-10-30"))

    df_slice_obs = get_single_file_slice(df_fnet_22, "LE", DailySeries, 0.05, 0.95,slice_dates, 
    DateTime("$year-04-01"), DateTime("$year-11-30"))    
    df_slice_obs = sort(df_slice_obs, :DateTime)


    ax_jsb.plot(df_vec_jsb[:,"DateTime"], df_vec_jsb[:,"mean"])
    ax_jsb.fill_between(df_vec_jsb[:,"DateTime"], df_vec_jsb[:,"qlow"], df_vec_jsb[:,"qup"], alpha = 0.3)

    #ax_jsb.set_yscale("log")
    ax_jsb.set_title("JSB - $year")
    #ax_jsb.set_ylim((0,12))
    ax_jsb.tick_params(axis="x", labelrotation=60)
    #ax_jsb.set_ylabel("LAI [m2 m-2]")
    ax_jsb.plot(df_slice_obs[:, "DateTime"],- df_slice_obs[:, "mean"], label ="obs")

    ax_spq.plot(df_vec_spq[:,"DateTime"], df_vec_spq[:,"mean"])
    ax_spq.fill_between(df_vec_jsb[:,"DateTime"], df_vec_spq[:,"qlow"], df_vec_spq[:,"qup"], alpha = 0.3)
    #ax_spq.set_yscale("log")
    ax_spq.set_title("QUINCY - $year")    
    #ax_spq.set_ylim((0,12))
    ax_spq.plot(df_slice_obs[:, "DateTime"],- df_slice_obs[:, "mean"], label ="obs")

    ax_spq.tick_params(axis="x", labelrotation=60)
    #ax_spq.set_ylabel("LAI [m2 m-2]")
    yi = yi +2

    ax_jsb.legend()
    ax_spq.legend()
end
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)





fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "wcont"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)
    for sl  in 1:6
        df_jsb = get_multi_file_slice_layered_avg(run_collections_jsb, "water_content_soil_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));

        df_spq = get_multi_file_slice_layered_avg(run_collections_spq, "water_content_soil_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));


        ax_jsb.plot(df_jsb[:,"DateTime"], df_jsb[:,"mean"]/soil_depth[sl], label =sl)
        #ax_jsb.set_yscale("log")
        ax_jsb.set_title("JSB - $year")
        ax_jsb.set_ylim((0.15,0.47))
        ax_jsb.tick_params(axis="x", labelrotation=60)
        ax_jsb.set_ylabel("θ [-]")

        ax_spq.plot(df_spq[:,"DateTime"], df_spq[:,"mean"]/soil_depth[sl], label =sl)
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




soil_depth = [ 0.065, 0.065, 0.065, 0.0699001, 0.09755344, 0.1361468, 
    0.1900082, 0.2651778, 0.3700854, 0.5164957, 0.7208278, 1.005996, 
    1.403981, 1.959413, 2.569414]

size(soil_depth)

fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "wcont"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)
    for sl  in 1:6
        df_jsb = get_multi_file_slice_layered_avg(run_collections_jsb, "water_content_soil_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));

        df_spq = get_multi_file_slice_layered_avg(run_collections_spq, "water_content_soil_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));


        ax_jsb.plot(df_jsb[:,"DateTime"], df_jsb[:,"mean"]/soil_depth[sl], label =sl)
        #ax_jsb.set_yscale("log")
        ax_jsb.set_title("JSB - $year")
        ax_jsb.set_ylim((0.15,0.47))
        ax_jsb.tick_params(axis="x", labelrotation=60)
        ax_jsb.set_ylabel("θ [-]")

        ax_spq.plot(df_spq[:,"DateTime"], df_spq[:,"mean"]/soil_depth[sl], label =sl)
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




fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "hyd_cond"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)
    for sl  in 1:6
        df_jsb = get_multi_file_slice_layered_avg(run_collections_jsb, "hyd_cond_avg_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));

        df_spq = get_multi_file_slice_layered_avg(run_collections_spq, "hyd_cond_avg_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));


        ax_jsb.plot(df_jsb[:,"DateTime"], df_jsb[:,"mean"]/soil_depth[sl], label =sl)
        ax_jsb.set_yscale("log")
        ax_jsb.set_title("JSB - $year")

        ax_jsb.set_ylim((10^-14, 10^-6))
        ax_jsb.tick_params(axis="x", labelrotation=60)
        #ax_jsb.set_ylabel("θ [-]")

        ax_spq.plot(df_spq[:,"DateTime"], df_spq[:,"mean"]/soil_depth[sl], label =sl)
        ax_spq.set_yscale("log")
        ax_spq.set_title("SPQ - $year")  
        #ax_spq.set_ylim((0.15,0.47))  
        ax_spq.set_ylim((10^-14, 10^-6))
        ax_spq.tick_params(axis="x", labelrotation=60)
        #ax_spq.set_ylabel("θ [-]")
    end
    yi = yi + 2
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
        df_jsb = get_multi_file_slice_layered_avg(run_collections_jsb, "water_potential_soil_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));

        df_spq = get_multi_file_slice_layered_avg(run_collections_spq, "water_potential_soil_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));


        ax_jsb.plot(df_jsb[:,"DateTime"], df_jsb[:,"mean"], label =sl)
        #ax_jsb.set_yscale("log")
        ax_jsb.set_title("JSB - $year")

        ax_jsb.set_ylim((-3,0))
        ax_jsb.tick_params(axis="x", labelrotation=60)
        #ax_jsb.set_ylabel("θ [-]")

        ax_spq.plot(df_spq[:,"DateTime"], df_spq[:,"mean"], label =sl)
        #ax_spq.set_yscale("log")
        ax_spq.set_title("SPQ - $year")  

        ax_spq.set_ylim((-3,0))
        #ax_spq.set_ylim((0.15,0.47))  
        #ax_spq.set_ylim((10^-13, 10^-6))
        ax_spq.tick_params(axis="x", labelrotation=60)
        #ax_spq.set_ylabel("θ [-]")
    end
    yi = yi + 2
    ax_jsb.legend()
    ax_spq.legend()
end
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)



fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "wcont_mid"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)
    for sl  in 6:10
        df_jsb = get_multi_file_slice_layered_avg(run_collections_jsb, "water_content_soil_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));

        df_spq = get_multi_file_slice_layered_avg(run_collections_spq, "water_content_soil_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));


        ax_jsb.plot(df_jsb[:,"DateTime"], df_jsb[:,"mean"]/soil_depth[sl], label =sl)
        #ax_jsb.set_yscale("log")
        ax_jsb.set_title("JSB - $year")
        ax_jsb.set_ylim((0.15,0.47))
        ax_jsb.tick_params(axis="x", labelrotation=60)
        ax_jsb.set_ylabel("θ [-]")

        ax_spq.plot(df_spq[:,"DateTime"], df_spq[:,"mean"]/soil_depth[sl], label =sl)
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




fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "wcont_bottom"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)
    for sl  in 10:15
        df_jsb = get_multi_file_slice_layered_avg(run_collections_jsb, "water_content_soil_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));

        df_spq = get_multi_file_slice_layered_avg(run_collections_spq, "water_content_soil_L", 
        Fluxnetdata, DailySeries,
        0.25, 0.75, sl, slice_dates, DateTime("$year-04-01"), DateTime("$year-11-30"));


        ax_jsb.plot(df_jsb[:,"DateTime"], df_jsb[:,"mean"]/soil_depth[sl], label =sl)
        #ax_jsb.set_yscale("log")
        ax_jsb.set_title("JSB - $year")
        ax_jsb.set_ylim((0.15,0.47))
        ax_jsb.tick_params(axis="x", labelrotation=60)
        ax_jsb.set_ylabel("θ [-]")

        ax_spq.plot(df_spq[:,"DateTime"], df_spq[:,"mean"]/soil_depth[sl], label =sl)
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



fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "rain"
varname ="rain_avg"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)

    df_vec_jsb = get_multi_file_slice_avg(run_collections_jsb, varname, 
    Fluxnetdata, ThirtyMinSeries,
    0.1, 0.9, slice_dates, DateTime("$year-05-01"), DateTime("$year-10-30"))



    df_vec_spq = get_multi_file_slice_avg(run_collections_spq, varname, 
    Fluxnetdata, ThirtyMinSeries,
    0.1, 0.9, slice_dates, DateTime("$year-05-01"), DateTime("$year-10-30"))


    ax_jsb.plot(df_vec_jsb[:,"DateTime"], df_vec_jsb[:,"mean"])
    ax_jsb.fill_between(df_vec_jsb[:,"DateTime"], df_vec_jsb[:,"qlow"], df_vec_jsb[:,"qup"], alpha = 0.3)

    #ax_jsb.set_yscale("log")
    ax_jsb.set_title("JSB - $year")
    #ax_jsb.set_ylim((0,12))
    ax_jsb.tick_params(axis="x", labelrotation=60)
    #ax_jsb.set_ylabel("LAI [m2 m-2]")

    ax_spq.plot(df_vec_spq[:,"DateTime"], df_vec_spq[:,"mean"])
    ax_spq.fill_between(df_vec_jsb[:,"DateTime"], df_vec_spq[:,"qlow"], df_vec_spq[:,"qup"], alpha = 0.3)
    #ax_spq.set_yscale("log")
    ax_spq.set_title("QUINCY - $year")    
    #ax_spq.set_ylim((0,12))

    ax_spq.tick_params(axis="x", labelrotation=60)
    #ax_spq.set_ylabel("LAI [m2 m-2]")
    yi = yi +2

    ax_jsb.legend()
    ax_spq.legend()
end
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)




fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "rain"
varname ="rain_avg"
yi = 1
for year in [2003, 2017]
    ax_jsb = fig.add_subplot(2, 2, yi)
    ax_spq = fig.add_subplot(2, 2, yi+1)

    df_vec_jsb = get_multi_file_slice_avg(run_collections_jsb, varname, 
    Fluxnetdata, ThirtyMinSeries,
    0.1, 0.9, slice_dates, DateTime("$year-05-01"), DateTime("$year-10-30"))



    df_vec_spq = get_multi_file_slice_avg(run_collections_spq, varname, 
    Fluxnetdata, ThirtyMinSeries,
    0.1, 0.9, slice_dates, DateTime("$year-05-01"), DateTime("$year-10-30"))


    ax_jsb.plot(df_vec_jsb[:,"DateTime"], df_vec_jsb[:,"mean"])
    ax_jsb.fill_between(df_vec_jsb[:,"DateTime"], df_vec_jsb[:,"qlow"], df_vec_jsb[:,"qup"], alpha = 0.3)

    #ax_jsb.set_yscale("log")
    ax_jsb.set_title("JSB - $year")
    #ax_jsb.set_ylim((0,12))
    ax_jsb.tick_params(axis="x", labelrotation=60)
    #ax_jsb.set_ylabel("LAI [m2 m-2]")

    ax_spq.plot(df_vec_spq[:,"DateTime"], df_vec_spq[:,"mean"])
    ax_spq.fill_between(df_vec_jsb[:,"DateTime"], df_vec_spq[:,"qlow"], df_vec_spq[:,"qup"], alpha = 0.3)
    #ax_spq.set_yscale("log")
    ax_spq.set_title("QUINCY - $year")    
    #ax_spq.set_ylim((0,12))

    ax_spq.tick_params(axis="x", labelrotation=60)
    #ax_spq.set_ylabel("LAI [m2 m-2]")
    yi = yi +2

    ax_jsb.legend()
    ax_spq.legend()
end
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)




for var_q in ["rain_avg", "snow_avg", "air_temperature_avg", "wind_avg",
     "swnir_srf_down_avg", "swvis_srf_down_avg", "water_potential_soil",

     "swpar_srf_down_avg", "lw_down_avg", "rootzone_soilwater_potential"]
    fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
    pltname = var_q
    varname =var_q
    yi = 1
    for year in [2003, 2017]
        ax_jsb = fig.add_subplot(2, 2, yi)
        ax_spq = fig.add_subplot(2, 2, yi+1)

        df_vec_jsb = get_multi_file_slice_avg(run_collections_jsb, varname, 
        Fluxnetdata, ThirtyMinSeries,
        0.1, 0.9, slice_dates, DateTime("$year-10-01"), DateTime("$year-10-30"))



        df_vec_spq = get_multi_file_slice_avg(run_collections_spq, varname, 
        Fluxnetdata, ThirtyMinSeries,
        0.1, 0.9, slice_dates, DateTime("$year-10-01"), DateTime("$year-10-30"))

        K_TO_C = 273.15
        if var_q == "air_temperature_avg"
            ax_jsb.plot(df_vec_jsb[:,"DateTime"], df_vec_jsb[:,"mean"] .- K_TO_C)
            ax_jsb.fill_between(df_vec_jsb[:,"DateTime"], df_vec_jsb[:,"qlow"].- K_TO_C, df_vec_jsb[:,"qup"].- K_TO_C, alpha = 0.3)
            ax_spq.plot(df_vec_spq[:,"DateTime"], df_vec_spq[:,"mean"].- K_TO_C)
            ax_spq.fill_between(df_vec_spq[:,"DateTime"], df_vec_spq[:,"qlow"].- K_TO_C, df_vec_spq[:,"qup"].- K_TO_C, alpha = 0.3)
        else
            ax_jsb.plot(df_vec_jsb[:,"DateTime"], df_vec_jsb[:,"mean"])
            ax_jsb.fill_between(df_vec_jsb[:,"DateTime"], df_vec_jsb[:,"qlow"], df_vec_jsb[:,"qup"], alpha = 0.3)
            ax_spq.plot(df_vec_spq[:,"DateTime"], df_vec_spq[:,"mean"])
            ax_spq.fill_between(df_vec_spq[:,"DateTime"], df_vec_spq[:,"qlow"], df_vec_spq[:,"qup"], alpha = 0.3)
        end

        

        #ax_jsb.set_yscale("log")
        ax_jsb.set_title("JSB - $year")
        #ax_jsb.set_ylim((0,12))
        ax_jsb.tick_params(axis="x", labelrotation=60)
        #ax_jsb.set_ylabel("LAI [m2 m-2]")


        #ax_spq.set_yscale("log")
        ax_spq.set_title("SPQ - $year")    
        #ax_spq.set_ylim((0,12))

        ax_spq.tick_params(axis="x", labelrotation=60)
        #ax_spq.set_ylabel("LAI [m2 m-2]")
        yi = yi +2

        ax_jsb.legend()
        ax_spq.legend()
    end
    PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
    PyPlot.close(fig)
end


list_jsb = Any[]
list_sqp = Any[]

varnames = ["air_temperature_avg", "water_potential_soil_L"]
for vname in varnames

    if vname == "water_potential_soil_L"
        df_vec_jsb = get_multi_file_slice_layered_avg(run_collections_jsb, vname, 
        Fluxnetdata, ThirtyMinSeries,
        0.1, 0.9,1, slice_dates, DateTime("2002-10-01"), DateTime("2020-10-30"))
        push!(list_jsb, df_vec_jsb)

        df_vec_spq = get_multi_file_slice_layered_avg(run_collections_spq, vname, 
        Fluxnetdata, ThirtyMinSeries,
        0.1, 0.9,1, slice_dates, DateTime("2002-10-01"), DateTime("2020-10-30"))
        push!(list_sqp, df_vec_spq)

    else
        df_vec_jsb = get_multi_file_slice_avg(run_collections_jsb, vname, 
        Fluxnetdata, ThirtyMinSeries,
        0.1, 0.9, slice_dates, DateTime("2002-10-01"), DateTime("2020-10-30"))
        push!(list_jsb, df_vec_jsb)

        df_vec_spq = get_multi_file_slice_avg(run_collections_spq, vname, 
        Fluxnetdata, ThirtyMinSeries,
        0.1, 0.9, slice_dates, DateTime("2002-10-01"), DateTime("2020-10-30"))
        push!(list_sqp, df_vec_spq)
    end


end


fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
ax = fig.add_subplot(1,1,1)
ax.scatter(list_jsb[1][:,"mean"].-273.15, list_jsb[2][:,"mean"], s=10)
PyPlot.savefig(joinpath(plt_dir,"Tvswpot.png"))
PyPlot.close(fig)

list_jsb = Any[]
list_sqp = Any[]
varnames = ["air_temperature_avg", "beta_gs"]
for vname in varnames

    if vname == "water_potential_soil_L"
        df_vec_jsb = get_multi_file_slice_layered_avg(run_collections_jsb, vname, 
        Fluxnetdata, ThirtyMinSeries,
        0.1, 0.9,1, slice_dates, DateTime("2002-10-01"), DateTime("2020-10-30"))
        push!(list_jsb, df_vec_jsb)

        df_vec_spq = get_multi_file_slice_layered_avg(run_collections_spq, vname, 
        Fluxnetdata, ThirtyMinSeries,
        0.1, 0.9,1, slice_dates, DateTime("2002-10-01"), DateTime("2020-10-30"))
        push!(list_sqp, df_vec_spq)

    else
        df_vec_jsb = get_multi_file_slice_avg(run_collections_jsb, vname, 
        Fluxnetdata, ThirtyMinSeries,
        0.1, 0.9, slice_dates, DateTime("2002-10-01"), DateTime("2020-10-30"))
        push!(list_jsb, df_vec_jsb)

        df_vec_spq = get_multi_file_slice_avg(run_collections_spq, vname, 
        Fluxnetdata, ThirtyMinSeries,
        0.1, 0.9, slice_dates, DateTime("2002-10-01"), DateTime("2020-10-30"))
        push!(list_sqp, df_vec_spq)
    end


end

fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
ax = fig.add_subplot(1,1,1)
ax.scatter(list_jsb[1][:,"mean"].-273.15, list_jsb[2][:,"mean"], s=10)
PyPlot.savefig(joinpath(plt_dir,"Tvsveta.png"))
PyPlot.close(fig)