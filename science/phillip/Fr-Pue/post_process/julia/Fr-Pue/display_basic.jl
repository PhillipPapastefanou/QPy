using NCDatasets
using CSV
using DataFrames
using Dates
using Statistics
using Plots
using CFTime

rt_path = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/PUE/01_run_transient_fix"

df = CSV.read(joinpath(rt_path, "merged_params_sliced.csv"), DataFrame)


df_filtered = filter(row -> 
    -3.0 <= row.avg_psi_midday_aug <= -2.7 && 
    row.std_veg > 1400, 
    df
)

vscodedisplay(df_filtered)



# 1. Define the indices you want to compare
target_indices = [4393, 4117] # Added your second index here
years = 2002:2016
plot_list = []

# Pre-allocate a dictionary to store data for all indices
data_map = Dict()

# 2. Load data for both indices
for idx in target_indices
    file_path = joinpath(rt_path, "output", string(idx), "PHYD_fluxnetdata_timestep.nc")
    
    if isfile(file_path)
        Dataset(file_path, "r") do ds
            data_map[idx] = (
                psi = ds["psi_leaf_avg"][:],
                times = ds["time"][:]
            )
        end
    else
        @warn "File not found for index $idx: $file_path"
    end
end

# 3. Create the plots
for yr in years
    p = plot(title = "Year $yr", 
             titlefontsize = 9,
             xticks = :none, 
             lw = 0.7, 
             grid = :y,
             legend = (yr == years[1] ? :bottomleft : false)) # Legend only on first plot

    found_data = false
    
    for (i, idx) in enumerate(target_indices)
        if !haskey(data_map, idx) continue end
        
        raw_times = data_map[idx].times
        raw_psi = data_map[idx].psi
        
        mask = year.(raw_times) .== yr
        
        if any(mask)
            yr_times = [DateTime(year(t), month(t), day(t), hour(t), minute(t)) 
                        for t in raw_times[mask]]
            yr_psi = raw_psi[mask]
            
            # Add line to existing subplot
            plot!(p, yr_times, yr_psi, label = "Index $idx", alpha = 0.7)
            found_data = true
        end
    end

    if !found_data
        push!(plot_list, plot(title="No Data $yr", grid=false, xaxis=false, yaxis=false))
    else
        push!(plot_list, p)
    end
end

# 4. Assemble the 4x4 layout
if !isempty(plot_list)
    final_plot = plot(plot_list..., 
                      layout = (4, 4), 
                      size = (1400, 1000), 
                      plot_title = "Leaf Water Potential Comparison: $target_indices",
                      left_margin = 5Plots.mm,
                      bottom_margin = 5Plots.mm)
    
    display(final_plot)
end



# 1. Identify the index where your target column starts
all_cols = names(df_filtered)
start_idx = findfirst(x -> x == "soil_pyhs_ret", all_cols)

if start_idx !== nothing && start_idx < length(all_cols)
    # 2. Select columns after "soil_phys_ret"
    target_cols = all_cols[start_idx+1:end]
    
    # 3. Generate a list of histogram plots
    # We filter out NaNs to ensure the histogram renders correctly
    hist_list = [histogram(filter(!isnan, df_filtered[!, col]), 
                           title = string(col), 
                           legend = false, 
                           xlabel = "Value", 
                           ylabel = "Frequency",
                           bins = :auto,
                           fillcolor = :viridis,
                           alpha = 0.7) for col in target_cols]

    # 4. Create a grid layout
    # We calculate rows/cols based on how many histograms we have
    n = length(hist_list)
    cols_layout = Int(ceil(sqrt(n)))
    rows_layout = Int(ceil(n / cols_layout))

    final_plot = plot(hist_list..., 
                      layout = (rows_layout, cols_layout), 
                      size = (400 * cols_layout, 300 * rows_layout),
                      margin = 5Plots.mm)

    display(final_plot)
else
    @error "Column 'soil_phys_ret' not found or no columns follow it."
end