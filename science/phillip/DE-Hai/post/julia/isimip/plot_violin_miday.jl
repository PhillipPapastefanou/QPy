include("../../../../src/postprocessing/julia/core/qcomparer.jl")

using CairoMakie
using Dates
using DataFrames
using Makie
using CSV
using Base.Iterators

vars = ["beta_gs", "gc_avg", "transpiration_avg", "gpp_avg", "psi_leaf_avg", "total_veg_c", "LAI", "psi_leaf_avg", "psi_stem_avg"]


function seasonal_yearly(df)
    df_season = filter(r -> 
            month(r.DateTime) in 4:10 && 
            hour(r.DateTime) in 12:14, 
        df)
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
rt_path_out_new = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/on27_df_psi_stem_stem_flow_03_18"
path_selected_new = joinpath(rt_path_in, "post", "ismip_selection_27_df_psi_stem_stem_flow_03_18.csv")

rt_path_in = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/28_run_transient_slurn_array_constrained"
rt_path_out_old = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/on28_all_f"
path_selected_old = joinpath(rt_path_in, "post", "ismip_selection_28.csv")

df_selected_old  = CSV.read(path_selected_old, DataFrame)
indexes_old = df_selected_old[!,:fid]

df_selected_new  = CSV.read(path_selected_new, DataFrame)
indexes_new = df_selected_new[!,:fid]


plt_dir = joinpath(rt_path_out_new,"post", "plots")
if !isdir(plt_dir)
    mkpath(plt_dir)
end

function get_august_means(df_vector)
    means = Float32[]
    for df in df_vector
        # 1. Filter for August (month == 8)
        august_data = df[month.(df.DateTime) .== 8, :mean]
        
        # 2. Calculate the single mean value for this DataFrame
        push!(means, mean(august_data))
    end
    return means # Returns a vector of 10 numbers
end



SSPS = [ "ssp126", "ssp370", "ssp585"]
#ssps = [ "ssp370"]

MODELS = ["mri-esm2-0","mpi-esm1-2", "ipsl-cm6a", "gfdl-esm4" ,"ukesm1-0"]


combinations = vec(collect(product(MODELS, SSPS)))

Threads.@threads for (model, ssp) in combinations
    # Your simulation logic here
    println("Thread $(Threads.threadid()) processing $model - $ssp")

        # model = MODELS[1]
        # ssp = ssps[1]

        start_time = time()
        last_report = start_time


        first_index = true
        qoutput = nothing
        cats = nothing
        sim_type_times=nothing
        run_collections_old = QMultiRunCollections(QOutputCollection[], String[])

        for i in indexes_old
            i_str = string(i)
            folder = "$rt_path_out_old/$model/$ssp/output/$i_str"

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
            folder = "$rt_path_out_new/$model/$ssp/output/$i_str"

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
            last_report = progress_report(i, indexes_new[end], start_time, last_report)
        end


for var in vars


        # Define your time steps
start_years = 2020:10:2090

# --- Setup Plotting Arrays ---
# These will grow as we loop through the years
all_xs = Int[]
all_ys = Float32[]
all_dodges = Int[]
x_labels = String[]


# --- The Loop: Load -> Process -> Repeat ---
for (i, start_y) in enumerate(start_years)
    end_y = start_y + 10
    
    # 1. Define the Date Range for this specific slice
    d1 = DateTime(start_y, 1, 1)
    d2 = DateTime(end_y, 12, 31) # Ensure we cover the full end year
    
    println("Processing window: $start_y - $end_y")
    push!(x_labels, "$start_y-$end_y")

    # 2. LOAD DATA (User's specific loading function)
    # We load only the small slice needed for this loop
    df_vec_old = get_multi_file_slice(run_collections_old, var, Fluxnetdata, ThirtyMinSeries, 0.1, 0.9, slice_dates, d1, d2)
    df_vec_new = get_multi_file_slice(run_collections_new, var, Fluxnetdata, ThirtyMinSeries, 0.1, 0.9, slice_dates, d1, d2)


    means_old = get_august_means(df_vec_old)
    means_new = get_august_means(df_vec_new)

    # 4. Append to Master Arrays for Plotting
    # -- Old Data (Dodge 1) --
    append!(all_ys, means_old)
    append!(all_xs, fill(i, length(means_old))) 
    append!(all_dodges, fill(1, length(means_old)))
    
    # -- New Data (Dodge 2) --
    append!(all_ys, means_new)
    append!(all_xs, fill(i, length(means_new)))
    append!(all_dodges, fill(2, length(means_new)))

end


my_blue = "#4E91C5"
my_red  = "#D9797A"

color_vector = [d == 1 ? my_blue : my_red for d in all_dodges]

unit =  get_unit(run_collections_old.output[1], var)

fig = Figure(size = (800, 500))
ax = Axis(fig[1, 1], 
    #title = "August Means Evolution (2021-2100)",
    ylabel = "$(var) [$unit]",
    xticks = (1:length(x_labels), x_labels),
    xticklabelrotation = pi/4,
    ylabelsize = 18
)

violin!(ax, all_xs, all_ys, 
    dodge = all_dodges, 
    color = color_vector, 
    width = 0.8,scale = :width
)

# Legend
elem_old = PolyElement(polycolor = my_blue)
elem_new = PolyElement(polycolor = my_red)
axislegend(ax, 
    [elem_old, elem_new],       # The colored symbols
    ["hyd unconst", "hyd const"], # The text label               # The legend title (optional)
    position = :rb,             # :rb = Right Bottom
    orientation = :vertical     # Stack items vertically
)


save(joinpath(plt_dir,"violin_aug_$(model)_$(ssp)_$var.png"), fig)
end
end



        #     d1, d2 = DateTime("2020-01-01"), DateTime("2101-01-01")
        #     #@time df = get_multi_file_slice_avg(run_collections, "total_veg_c", Fluxnetdata, YearlySeries, 0.05, 0.95, slice_dates, d1, d2 )
        #     @time df_old = get_multi_file_slice_avg(run_collections_old, var, Fluxnetdata, ThirtyMinSeries, 0.1, 0.9, slice_dates, d1, d2 )
        #     @time df_new = get_multi_file_slice_avg(run_collections_new, var, Fluxnetdata, ThirtyMinSeries, 0.1, 0.9, slice_dates, d1, d2 )
        
        #     df_yearly_old = seasonal_yearly(df_old)
        #     df_yearly_new = seasonal_yearly(df_new)
            
        #     #CSV.write(joinpath("$rt_path_out_new", "post", "$(ssp)_$var.csv"), df_yearly_new)
            
        #     # 1. Prepare data
        #     x_old = datetime2unix.(DateTime.(df_yearly_old.DateTime))
        #     x_new = datetime2unix.(DateTime.(df_yearly_new.DateTime))

        #     # 2. Prepare specific ticks
        #     # Adjust the range (2020:20:2100) to match the span of your data
        #     tick_years = 2020:20:2100 
        #     tick_values = datetime2unix.(DateTime.(Date.(tick_years, 1, 1)))

        #     fig = Figure(size = (1200, 500))

        #     ax_old = Axis(
        #         fig[1, 1],
        #         xlabel = "Year",
        #         ylabel = "Value",
        #         title  = "Old: $ssp-$var",
        #         xticks = (tick_values, string.(tick_years))
        #     )

        #     ax_new = Axis(
        #         fig[1, 2],
        #         xlabel = "Year",
        #         title  = "New: $ssp-$var",
        #         xticks = (tick_values, string.(tick_years))
        #     )

        #     linkyaxes!(ax_old, ax_new)

        #     band!(
        #         ax_old,
        #         x_old,
        #         df_yearly_old.qlow,
        #         df_yearly_old.qup,
        #         color = (:steelblue, 0.25)
        #     )

        #     lines!(
        #         ax_old,
        #         x_old,
        #         df_yearly_old.median,
        #         color = :black,
        #         linestyle = :dash,
        #         linewidth = 2,
        #         label = "Median"
        #     )


        #     band!(
        #         ax_new,
        #         x_new,
        #         df_yearly_new.qlow,
        #         df_yearly_new.qup,
        #         color = (:firebrick, 0.25)
        #     )

        #     lines!(
        #         ax_new,
        #         x_new,
        #         df_yearly_new.median,
        #         color = :black,
        #         linestyle = :dash,
        #         linewidth = 2
        #     )

        #     #axislegend(ax_new, position = :lt)
        #     #save(joinpath(plt_dir,"midday_$(model)_$(ssp)_$var.png"), fig)
        # end
    # end
# end


# @time df = get_multi_file_slice_avg(run_collections, "gpp_avg", Fluxnetdata, DailySeries, 0.05, 0.95, slice_dates, d1, d2 )


