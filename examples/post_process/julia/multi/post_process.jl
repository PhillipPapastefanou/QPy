include("../../../../src/postprocessing/julia/core/qslicer.jl")
using PyPlot


using CSV


script_dir = dirname(@__FILE__)


plt_dir = joinpath("$script_dir", "plots", "hyd_tests")
if !isdir(plt_dir)
    mkdir(plt_dir)
end


rtobspath = "/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed"
full_path_df_22 = joinpath(rtobspath, "Fluxnet2000_2021_eval.csv")
df_fnet_22 = CSV.read(full_path_df_22, DataFrame, dateformat = Dict(:time => "yyyy-mm-dd HH:MM:SS"))
rename!(df_fnet_22, :time => :DateTime)
df_fnet_22 = dropmissing(df_fnet_22)

full_path_df_24 = joinpath(rtobspath, "Fluxnet2023_2024_eval.csv")
df_fnet_24 = CSV.read(full_path_df_24, DataFrame, dateformat = Dict(:date => "yyyy-mm-dd HH:MM:SS"))
rename!(df_fnet_24, :date => :DateTime)

full_path_psi_stem = joinpath(rtobspath, "PsiStem2023.csv")
df_psi_stem_obs = CSV.read(full_path_psi_stem, DataFrame, dateformat = Dict(:date => "yyyy-mm-dd HH:MM:SS"))
rename!(df_psi_stem_obs, :date => :DateTime)

full_path_sap_flow_2023 = joinpath(rtobspath, "Sapflow2023.csv");
df_sap_flow_2023 = CSV.read(full_path_sap_flow_2023, DataFrame, dateformat = Dict(:date => "yyyy-mm-dd HH:MM:SS"));
df_sap_flow_2023 = filter(row -> !ismissing(row["J0.5"]), df_sap_flow_2023);
df_sap_flow_2023[!,"J0.5"]= convert(Vector{Float64}, df_sap_flow_2023[:,"J0.5"]);
df_sap_flow_2023[df_sap_flow_2023[:,"J0.5"] .< 0.0, "J0.5"] .= 0.0
rename!(df_sap_flow_2023, :date => :DateTime)



varn = "LE"

fig = PyPlot.figure(figsize = (12,6))
ax = fig.add_subplot(1,2,1)
for yeari in [2003, 2018]
    df_slice_obs = get_single_file_slice(df_fnet_22, varn, DailySeries, 0.05, 0.95,slice_dates, 
    DateTime("$yeari-07-01"), DateTime("$yeari-09-30"))    
    df_slice_obs = sort(df_slice_obs, :DateTime)
    ts = round(sum(df_slice_obs[!,:mean]),sigdigits=3)
    ax.plot(df_slice_obs[!,:mean], label = "$yeari $ts")
    #x.set_ylim(-10, 150)
end
ax.legend()


ax = fig.add_subplot(1,2,2)
for yeari in setdiff(2010:2020, [2003, 2018])
    df_slice_obs = get_single_file_slice(df_fnet_22, varn, DailySeries, 0.05, 0.95,slice_dates, 
    DateTime("$yeari-07-01"), DateTime("$yeari-09-30"))    
    df_slice_obs = sort(df_slice_obs, :DateTime)
    ts = round(sum(df_slice_obs[!,:mean]),sigdigits=3)
    ax.plot(df_slice_obs[!,:mean], label = "$yeari $ts")
    #ax.set_ylim(-10, 150)
end
ax.legend()

PyPlot.savefig(joinpath(plt_dir, "$varn.png"))
PyPlot.close(fig)



rt_path_hyd = "/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/science/phillip/output/05_transient_fluxnet"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/06s_transient_fluxnet_finer"
run_collections = QMultiRunCollections(QOutputCollection[], String[])
indexes_all = 0:(5120-1)
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

run_collections.output[100]

#d1, d2 =     DateTime("2000-01-01"), DateTime("2020-12-31")
d1, d2 =     DateTime("2023-05-01"), DateTime("2023-10-30")
series = ThirtyMinSeries


df_obs_gpp_slice = get_single_file_slice(df_fnet_24, "GPP", series, 0.05, 0.95,
slice_dates, 
   d1, d2)
   
df_obs_le_slice = get_single_file_slice(df_fnet_24, "LE", series, 0.05, 0.95,
slice_dates, 
   d1, d2) 

df_obs_psi_stem_slice = get_single_file_slice(df_psi_stem_obs, "FAG", series, 0.25, 0.75,slice_dates, 
   d1, d2)    

df_obs_sapflow_slice = get_single_file_slice(df_sap_flow_2023, "J0.5", series, 0.1, 0.9, slice_dates, DateTime("2023-06-01"), DateTime("2023-08-01"))  
df_obs_sapflow_slice[!,:mean_norm]= df_obs_sapflow_slice[!,:mean]/ maximum(df_obs_sapflow_slice[!,:mean])


vec_mod_gpp = get_multi_file_slice(run_collections, "gpp_avg", 
    Fluxnetdata, series,
    0.1, 0.9, slice_dates, d1, d2);

vec_mod_le = get_multi_file_slice(run_collections, "qle_avg", 
    Fluxnetdata, series,
    0.1, 0.9, slice_dates, d1, d2);

vec_mod_psi_stem = get_multi_file_slice(run_collections, "psi_stem_avg", 
    Fluxnetdata, series,
    0.1, 0.9, slice_dates, d1, d2);

vec_mod_stem_flow = get_multi_file_slice(run_collections, "stem_flow_avg", 
    Fluxnetdata, series,
    0.1, 0.9, slice_dates, d1, d2);


df_param = CSV.read(joinpath(rt_path_hyd, "parameters.csv"), DataFrame)
df_param.gpp_rmse .= NaN;
df_param.le_rmse .= NaN;
df_param.psi_stem_rmse .= NaN;
df_param.stem_flow_rmse .= NaN;

for i in indexes_all
    df_join = innerjoin(vec_mod_gpp[i+1], df_obs_gpp_slice, on = :DateTime, makeunique=true)
    rmse = sqrt(mean((df_join.mean .- df_join.mean_1).^2))
    df_param[i+1,:gpp_rmse] = rmse

    # Note the -1.0 to account for the differences in LE
    df_join = innerjoin(vec_mod_le[i+1], df_obs_le_slice, on = :DateTime, makeunique=true)
    rmse = sqrt(mean((-1.0 * df_join.mean .- df_join.mean_1).^2))
    df_param[i+1,:le_rmse] = rmse

    df_join = innerjoin(vec_mod_psi_stem[i+1], df_obs_psi_stem_slice, on = :DateTime, makeunique=true)
    rmse = sqrt(mean((df_join.mean .- df_join.mean_1).^2))
    df_param[i+1,:psi_stem_rmse] = rmse

    max_mod = maximum(vec_mod_stem_flow[i+1][!,:mean])
    vec_mod_stem_flow[i+1][!,:mean_norm] = vec_mod_stem_flow[i+1][!,:mean]/max_mod
    df_join = innerjoin(vec_mod_stem_flow[i+1], df_obs_sapflow_slice, on = :DateTime, makeunique=true)
    rmse = sqrt(mean((df_join.mean_norm .- df_join.mean_norm_1).^2))
    df_param[i+1,:stem_flow_rmse] = rmse

end;


#vscodedisplay(df_param)
sort(df_param, :psi_stem_rmse)[!,[:id,:gpp_rmse,:le_rmse,:psi_stem_rmse, :stem_flow_rmse]]
sort(df_param, :stem_flow_rmse)[!,[:id,:gpp_rmse,:le_rmse,:psi_stem_rmse, :stem_flow_rmse]]
sort(df_param, :gpp_rmse)[!,[:id,:gpp_rmse,:le_rmse,:psi_stem_rmse, :stem_flow_rmse]]


CSV.write(joinpath(plt_dir,"params_rmse209.csv") ,df_param)

vscodedisplay(sort(df_param, :psi_stem_rmse))
vscodedisplay(sort(df_param, :gpp_rmse))


vscodedisplay(filter(row -> row.psi_stem_rmse < 0.1, df_param))

df_param





selids = ["4726", "1150"]
run_sel = run_collections[selids];

run_sel.idstr

d1, d2 =     DateTime("2023-05-01"), DateTime("2023-10-30")

fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "fluxes"
varname ="gpp_avg"
series = ThirtyMinSeries
list_gpp = get_multi_file_slice(run_sel, varname, 
Fluxnetdata, series,
0.1, 0.9, slice_dates, d1, d2); 
varname ="qle_avg"
list_le = get_multi_file_slice(run_sel, varname, 
Fluxnetdata, series,
0.1, 0.9, slice_dates, d1, d2); 


ax = fig.add_subplot(2,1,1)
for i in 1:length(list_gpp)
    ax.plot(list_gpp[i][!,:DateTime], list_gpp[i][!,:mean], label=selids[i], alpha= 0.4)
end
ax.plot(df_obs_gpp_slice[!,:DateTime], df_obs_gpp_slice[!,:mean], label = "obs", color = "black", alpha= 0.3)


ax = fig.add_subplot(2,1,2)
for i in 1:length(list_gpp)
    ax.plot(list_le[i][!,:DateTime], -list_le[i][!,:mean], label=selids[i], alpha= 0.4)
end
ax.plot(df_obs_le_slice[!,:DateTime], df_obs_le_slice[!,:mean], label = "obs", color = "black", alpha= 0.3)

ax.legend()
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)






selids = ["5070", "500"]
run_sel = run_collections[selids];

run_sel.idstr

d1, d2 =     DateTime("2023-05-01"), DateTime("2023-9-30")

fig = PyPlot.figure(figsize=(8, 6), layout="constrained")
pltname = "fluxes"
varname ="gpp_avg"
series = DailySeries
list_gpp = get_multi_file_slice(run_sel, varname, 
Fluxnetdata, series,
0.1, 0.9, slice_dates, d1, d2); 
varname ="qle_avg"
list_le = get_multi_file_slice(run_sel, varname, 
Fluxnetdata, series,
0.1, 0.9, slice_dates, d1, d2); 

df_obs_gpp_slice = get_single_file_slice(df_fnet_24, "GPP", series, 0.05, 0.95,
slice_dates, 
   d1, d2)
   
df_obs_le_slice = get_single_file_slice(df_fnet_24, "LE", series, 0.05, 0.95,
slice_dates, 
   d1, d2)

ax = fig.add_subplot(2,1,1)
for i in 1:length(list_gpp)
    ax.plot(list_gpp[i][!,:DateTime], list_gpp[i][!,:mean], label=selids[i])
end
ax.plot(df_obs_gpp_slice[!,:DateTime], df_obs_gpp_slice[!,:mean], label = "obs", color = "black", alpha= 0.3)

ax.legend()

ax = fig.add_subplot(2,1,2)
for i in 1:length(list_gpp)
    ax.plot(list_le[i][!,:DateTime], -list_le[i][!,:mean], label=selids[i])
end
ax.plot(df_obs_le_slice[!,:DateTime], df_obs_le_slice[!,:mean], label = "obs", color = "black", alpha= 0.3)

ax.legend()
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)




d1, d2 =     DateTime("2023-07-07"), DateTime("2023-8-1")


pltname = "psi_stem"
varname ="psi_stem_avg"
series = ThirtyMinSeries
list_psi_stem = get_multi_file_slice(run_sel, varname, 
Fluxnetdata, series,
0.1, 0.9, slice_dates, d1, d2);

df_obs_psi_stem_slice = get_single_file_slice(df_psi_stem_obs, "FAG", series, 0.25, 0.75,slice_dates, 
   d1, d2)   
   
fig = PyPlot.figure(figsize=(8, 6), layout="constrained")

ax = fig.add_subplot(1,1,1)
for i in 1:length(list_psi_stem)
    ax.plot(list_psi_stem[i][!,:DateTime], list_psi_stem[i][!,:mean], label=selids[i], alpha= 0.5)
end
ax.plot(df_obs_psi_stem_slice[!,:DateTime], df_obs_psi_stem_slice[!,:mean], label = "obs", color = "black", alpha= 0.5)

ax.legend()
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)





d1, d2 =     DateTime("2023-01-01"), DateTime("2023-8-1")

pltname = "stem_flow"
varname ="stem_flow_avg"
run_sel
series = ThirtyMinSeries
list_stemflow= get_multi_file_slice(run_sel, varname, 
Fluxnetdata, series,
0.1, 0.9, slice_dates, d1, d2);

df_obs_sapflow_slice = get_single_file_slice(df_sap_flow_2023, "J0.5", series, 0.1, 0.9, slice_dates, d1, d2)  
df_obs_sapflow_slice[!,:mean_norm]= df_obs_sapflow_slice[!,:mean]/ maximum(df_obs_sapflow_slice[!,:mean])
   
fig = PyPlot.figure(figsize=(8, 6), layout="constrained")

ax = fig.add_subplot(1,1,1)
for i in 1:length(list_stemflow)
    #smax = maximum(list_stemflow[i][!,:mean])
    #ax.plot(list_stemflow[i][!,:DateTime], list_stemflow[i][!,:mean]/smax, label=selids[i], alpha= 0.5)

    ax.plot(list_stemflow[i][!,:DateTime], list_stemflow[i][!,:mean], label=selids[i], alpha= 0.5)
end
#ax.plot(df_obs_sapflow_slice[!,:DateTime], df_obs_sapflow_slice[!,:mean_norm], label = "obs", color = "black", alpha= 0.5)

ax.legend()
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)
maximum(list_stemflow[1][!,:mean])
maximum(list_stemflow[2][!,:mean])

list_stemflow[1]




list_stemflow




d1, d2 =     DateTime("2023-01-01"), DateTime("2023-8-1")
varname ="transpiration_avg"
pltname = varname
run_sel
series = ThirtyMinSeries
list_stemflow= get_multi_file_slice(run_sel, varname, 
Fluxnetdata, series,
0.1, 0.9, slice_dates, d1, d2);

   
fig = PyPlot.figure(figsize=(8, 6), layout="constrained")

ax = fig.add_subplot(1,1,1)
for i in 1:length(list_stemflow)
    #smax = maximum(list_stemflow[i][!,:mean])
    #ax.plot(list_stemflow[i][!,:DateTime], list_stemflow[i][!,:mean]/smax, label=selids[i], alpha= 0.5)

    ax.plot(list_stemflow[i][!,:DateTime], list_stemflow[i][!,:mean], label=selids[i], alpha= 0.5)
end
#ax.plot(df_obs_sapflow_slice[!,:DateTime], df_obs_sapflow_slice[!,:mean_norm], label = "obs", color = "black", alpha= 0.5)

ax.legend()
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)




pltname = "psi_leaf"
varname ="psi_leaf_avg"
series = ThirtyMinSeries
list_psi_stem = get_multi_file_slice(run_sel, varname, 
Fluxnetdata, series,
0.1, 0.9, slice_dates, d1, d2);

   
fig = PyPlot.figure(figsize=(8, 6), layout="constrained")

ax = fig.add_subplot(1,1,1)
for i in 1:length(list_psi_stem)
    ax.plot(list_psi_stem[i][!,:DateTime], list_psi_stem[i][!,:mean], label=selids[i], alpha= 0.5)
end

ax.legend()
PyPlot.savefig(joinpath(plt_dir,"$pltname.png"))
PyPlot.close(fig)