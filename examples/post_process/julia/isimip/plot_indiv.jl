include("../../../../src/postprocessing/julia/core/qcomparer.jl")

using CairoMakie
using Dates
using DataFrames
using Makie
using CSV

vars = ["beta_gs", "gc_avg", "transpiration_avg", "gpp_avg", "psi_leaf_avg", "total_veg_c", "LAI", "psi_leaf_avg", "psi_stem_avg"]


function seasonal_yearly(df)
    df_season = filter(r -> month(r.DateTime) in 5:9, df)
    df_season.year = year.(df_season.DateTime)

    df_yearly = combine(
        groupby(df_season, :year),
        :median => mean => :median,
        :qlow   => mean => :qlow,
        :qup    => mean => :qup
    )

    df_yearly.DateTime = Date.(df_yearly.year, 1, 1)
    return df_yearly
end

rt_path_in = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/27_transient_slurm_array_dyn_roots_off"
rt_path_out_new = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/on27_ruf"
path_selected_new = joinpath(rt_path_in, "post", "ismip_selection_27.csv")

rt_path_in = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/28_run_transient_slurn_array_constrained"
rt_path_out_old = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/on28_ruf"
path_selected_old = joinpath(rt_path_in, "post", "ismip_selection_28.csv")

df_selected_old  = CSV.read(path_selected_old, DataFrame)
indexes_old = df_selected_old[1:5,:fid]

df_selected_new  = CSV.read(path_selected_new, DataFrame)
indexes_new = df_selected_new[!,:fid]


plt_dir = joinpath(rt_path_out_new,"post", "plots")
if !isdir(plt_dir)
    mkpath(plt_dir)
end
ssps = [ "ssp126", "ssp370", "ssp585"]
ssp = "ssp370"



    start_time = time()
    last_report = start_time


    first_index = true
    qoutput = nothing
    cats = nothing
    sim_type_times=nothing
    run_collections_old = QMultiRunCollections(QOutputCollection[], String[])

    for i in indexes_old
        i_str = string(i)
        folder = "$rt_path_out_old/$ssp/output/$i_str"

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
        push!(run_collections_old.idstr, i_str);
        push!(run_collections_old.output, qoutput);
        last_report = progress_report(i, indexes_old[end], start_time, last_report)
    end



    first_index = true
    qoutput = nothing
    cats = nothing
    sim_type_times=nothing
    run_collections_new = QMultiRunCollections(QOutputCollection[], String[])

    for i in indexes_new
        i_str = string(i)
        folder = "$rt_path_out_new/$ssp/output/$i_str"

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
        push!(run_collections_new.idstr, i_str);
        push!(run_collections_new.output, qoutput);
        last_report = progress_report(i, indexes_old[end], start_time, last_report)
    end

df_selected_new
run_collections_new

run_collections_new.idstr


# @time df = get_multi_file_slice_avg(run_collections, "gpp_avg", Fluxnetdata, DailySeries, 0.05, 0.95, slice_dates, d1, d2 )


        var = "gpp_avg"

        d1, d2 = DateTime("2020-01-01"), DateTime("2101-01-01")
        #@time df = get_multi_file_slice_avg(run_collections, "total_veg_c", Fluxnetdata, YearlySeries, 0.05, 0.95, slice_dates, d1, d2 )
        @time vec_df_old = get_multi_file_slice(run_collections_old, var, Fluxnetdata, YearlySeries, 0.1, 0.9, slice_dates, d1, d2 )
        @time vec_df_new = get_multi_file_slice(run_collections_new, var, Fluxnetdata, YearlySeries, 0.1, 0.9, slice_dates, d1, d2 )
      

        df_new[1]

        x = []
        for i in 1:size(df_new)[1]
            push!(x,vec_df_new[i][1,:mean] )
        end
       
        x
        
        df_selected_new[!,"gpp"] = x

        df_selected_new

        CSV.write(joinpath(plt_dir,"$(ssp)_$var.csv"), df_selected_new)



         df_selected_new
        # 1. Prepare data
        x_old = datetime2unix.(DateTime.(df_yearly_old.DateTime))
        x_new = datetime2unix.(DateTime.( df_new[1].DateTime))

        # 2. Prepare specific ticks
        # Adjust the range (2020:20:2100) to match the span of your data
        tick_years = 2020:20:2100 
        tick_values = datetime2unix.(DateTime.(Date.(tick_years, 1, 1)))

        fig = Figure(size = (1200, 500))


        

        ax_old = Axis(
            fig[1, 1],
            xlabel = "Year",
            ylabel = "Value",
            title  = "Old: $ssp-$var",
            xticks = (tick_values, string.(tick_years))
        )

        ax_new = Axis(
            fig[1, 2],
            xlabel = "Year",
            title  = "New: $ssp-$var",
            xticks = (tick_values, string.(tick_years))
        )

        linkyaxes!(ax_old, ax_new)

        for i in 1:size(df_new)[1]
            lines!(
                ax_new,
                x_new,
                df_new[i].median,
                color = :black,
                alpha = 0.2,
                linewidth = 1
            )
        end

        axislegend(ax, position = :lt)
        fig
