using NCDatasets
using Plots
using Statistics
using Dates


path = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/ismip_selection_63_res_df_psi_stem_leaf_stem_flow_ind/ukesm1-0/ssp370/output/71"
# 1. Open the NetCDF file
filename = joinpath(path,"PHYD_fluxnetdata_timestep.nc")
ds = NCDataset(filename, "r")

# 2. Read the variables
# NCDatasets automatically decodes the time into DateTimeNoLeap objects
time_decoded  = ds["time"][:] 
transpiration = ds["G_avg"][:]
sap_flow      = ds["stem_flow_avg"][:]
res_flow      = ds["res_flow_avg"][:]

close(ds)

# 3. Convert time to "Hour of the Day"
# Extract the hour and minute from the datetime objects to get a decimal hour (e.g., 14:30 -> 14.5)
hour_of_day = [hour(t) + minute(t) / 60.0 for t in time_decoded]

# 4. Calculate the mean diurnal cycle (48 half-hour bins per day)
hours_unique = 0.0:0.5:23.5

mean_transpiration = Float64[]
mean_sap_flow      = Float64[]
mean_res_flow      = Float64[]

for h in hours_unique
    # Find all indices across the entire dataset that match this half-hour
    idx = findall(x -> isapprox(x, h, atol=0.1), hour_of_day)
    
    # Calculate the mean for this half-hour, skipping any missing data points
    push!(mean_transpiration, mean(skipmissing(transpiration[idx])))
    push!(mean_sap_flow, mean(skipmissing(sap_flow[idx])))
    push!(mean_res_flow, mean(skipmissing(res_flow[idx])))
end

# 5. Create the subplots
p1 = plot(hours_unique, mean_transpiration, 
          label="Transpiration (G_avg)", 
          ylabel="kg m⁻² s⁻¹", 
          linewidth=2, color=:forestgreen,
          title="Mean 24h Diurnal Cycle")

p2 = plot(hours_unique, mean_sap_flow, 
          label="Sap Flow (stem_flow_avg)", 
          ylabel="kg m⁻² s⁻¹", 
          linewidth=2, color=:royalblue)

p3 = plot(hours_unique, mean_res_flow, 
          label="Res Flow (res_flow_avg)", 
          xlabel="Hour of Day", 
          ylabel="kg m⁻² s⁻¹", 
          linewidth=2, color=:firebrick)

# 6. Combine them into a single 3x1 layout
final_plot = plot(p1, p2, p3, 
                  layout=(3,1), 
                  size=(800, 800), 
                  legend=:topleft, 
                  link=:x,           
                  xlims=(0, 24),     
                  xticks=0:2:24)     

# Display the plot
display(final_plot)

# Optional: Save to file
savefig(final_plot, "diurnal_cycle_subplots.png")