using NCDatasets
using CSV
using DataFrames
using Dates
using Statistics
using Plots
using CFTime

rt_path = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/PUE/00_run_transient"

# 1. Initialize DataFrame with both columns
df_results = DataFrame(
    index = Int[], 
    std_veg = Float32[], 
    avg_psi_midday_aug = Float32[]
)

for i in 0:10239
    # Construct paths
    folder_name = string(i)
    file_path_veg = joinpath(rt_path, "output", folder_name, "VEG_spinup_yearly.nc")
    file_path_hyd = joinpath(rt_path, "output", folder_name, "PHYD_fluxnetdata_timestep.nc") 

    # Temporary variables to hold values for this specific 'i'
    current_veg = NaN32
    current_psi = NaN32

    if isfile(file_path_veg)
        try
            Dataset(file_path_veg, "r") do ds
                current_veg = ds["total_veg_c"][end]
            end
        catch e
            @warn "Error reading VEG in folder $i: $e"
        end
    end

    if isfile(file_path_hyd)
        try
            Dataset(file_path_hyd, "r") do ds
                psi_vals = ds["psi_leaf_avg"][:]
                raw_times = ds["time"][:]
                
                # Filter for August (8) at 2 PM (14:00)
                mask = (month.(raw_times) .== 8) .& (hour.(raw_times) .== 14)
                aug_midday_vals = psi_vals[mask]
                
                # Clean NaNs and average
                clean_vals = filter(!isnan, aug_midday_vals)
                if !isempty(clean_vals)
                    current_psi = mean(clean_vals)
                end
            end
        catch e
            @warn "Error reading HYD in folder $i: $e"
        end
    end


    push!(df_results, (
        index = i, 
        std_veg = current_veg, 
        avg_psi_midday_aug = current_psi
    ))

    # Optional: Progress tracker every 100 iterations
    if i % 100 == 0
        println("Processed index: $i")
    end
end

file_params =joinpath(rt_path,"parameters.csv")
df_params = CSV.read(file_params, DataFrame)
df_merged = innerjoin(df_params, df_results, on = :fid => :index)

sort!(df_merged, :fid)

CSV.write(joinpath(rt_path,"merged_params.csv"), df_merged)



#vscodedisplay(df_merged)

# 1. Select the index you want to inspect
target_index = 6027  # Change this to any number between 0 and 10239
file_path_hyd = joinpath(rt_path, "output", string(target_index), "PHYD_fluxnetdata_timestep.nc")

# 1. Define the 16-year range ending in 2021
years = 2006:2021
plot_list = []

if isfile(file_path_hyd)
    Dataset(file_path_hyd, "r") do ds
        raw_psi = ds["psi_leaf_avg"][:]
        raw_times = ds["time"][:]
        
        # Optional: Find global min/max for consistent y-axis scaling
        # y_min = floor(minimum(filter(!isnan, raw_psi)))
        # y_max = 0.0
        
        for yr in years
            mask = year.(raw_times) .== yr
            
            # Skip if year doesn't exist in file
            if !any(mask)
                push!(plot_list, plot(title="No Data $yr", grid=false, xaxis=false, yaxis=false))
                continue
            end

            # Convert times and extract data
            yr_times = [DateTime(year(t), month(t), day(t), hour(t), minute(t)) 
                        for t in raw_times[mask]]
            yr_psi = raw_psi[mask]
            
            # Create subplot
            p = plot(yr_times, yr_psi, 
                     title = "Year $yr", 
                     titlefontsize = 9,
                     xticks = :none, 
                     # ylims = (y_min, y_max), # Uncomment to force same scale
                     lw = 0.7, 
                     linecolor = :steelblue,
                     grid = :y,
                     legend = false)
            
            push!(plot_list, p)
        end
    end

    # 2. Assemble the 4x4 layout
    final_plot = plot(plot_list..., 
                      layout = (4, 4), 
                      size = (1400, 1000), 
                      plot_title = "Leaf Water Potential (Index $target_index): 2006-2021",
                      left_margin = 5Plots.mm,
                      bottom_margin = 5Plots.mm)
    
    display(final_plot)
else
    @error "File not found: $file_path_hyd"
end



df_filtered = filter(row -> 
    -4.0 <= row.avg_psi_midday_aug <= -2.3 && 
    row.std_veg > 1400, 
    df_merged
)

vscodedisplay(df_filtered)