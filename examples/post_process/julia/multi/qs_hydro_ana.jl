include("../../../../src/postprocessing/julia/core/qcomparer.jl")

using CairoMakie
using Dates
using DataFrames
using Makie

rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/14_transient_slurm_array"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/20_transient_slurm_array_krtos"

rmse_data_path = joinpath(rt_path_hyd, "post", "params_rmse.csv")

df = CSV.read(rmse_data_path, DataFrame)
df = df[:, .!map(col -> all(x -> ismissing(x) || (x isa Number && isnan(x)), col),
                 eachcol(df))]

df = df[.!isnan.(df.psi_stem_rmse_23), :]


# print(names(df))
dh = filter(row -> (row.psi_stem_rmse_23 < 0.1) & (row.stem_flow_rmse_23 < 0.25), df);
print(size(dh))
dh = filter(row -> (row.psi_stem_rmse_23 < 0.1) & (row.stem_flow_rmse_23 < 0.30) & (row.gpp_rmse_23 < 3.2), df);
print(size(dh))
dh = filter(row -> (row.psi_stem_rmse_23 < 0.1) & (row.stem_flow_rmse_23 < 0.30) & (row.le_rmse_23 < 35), df);
print(size(dh))
dh = filter(row -> (row.psi_stem_rmse_23 < 0.12) & (row.stem_flow_rmse_23 < 0.30)&(row.le_rmse_23 < 34) , df);
print(size(dh))
dh = filter(row -> (row.psi_stem_rmse_23 < 0.1) & (row.stem_flow_rmse_23 < 0.28)&(row.le_rmse_full < 35)&(row.gpp_rmse_full < 3.4) , df);
print(size(dh))
dh = filter(row -> (row.psi_stem_rmse_23 < 0.1) & (row.stem_flow_rmse_23 < 0.28) & (row.le_rmse_18 < 33)&(row.gpp_rmse_18 < 3.5) , df);
print(size(dh))
dh = filter(row -> (row.
psi_stem_rmse_23 < 0.1) & (row.stem_flow_rmse_23 < 0.28) & (row.le_rmse_03 < 40)&(row.gpp_rmse_03 < 3.9) , df);
print(size(dh))  

fids = [string(s) for s in dh[!,:fid]]

function run_prep(full_dir_paths, short_dir_paths )

    run_collections = QMultiRunCollections(QOutputCollection[], String[])
    start_time = time()
    last_report = start_time

    qoutput = nothing
    cats = nothing
    sim_type_times=nothing

    for (i, (full, short)) in enumerate(zip(full_dir_paths, short_dir_paths))

        if i == 1 
            qoutput = read_quincy_site_output(full)
            cats = qoutput.cats
            sim_type_times = qoutput.sim_type_times
        else
                qoutput = deepcopy(qoutput)
            #We need to override the file paths
            for sim_type_t in sim_type_times
                for cat in cats
                    filename = joinpath(full, cat*"_"*sim_type_t*".nc")
                            qoutput.data[sim_type_t][cat].filename = filename      
                end
            end
        end
        push!(run_collections.idstr, short);
        push!(run_collections.output, qoutput);
        last_report = progress_report(i, length(full_dir_paths), start_time, last_report)
    end
    return run_collections
end

hainich_obs = init_hainich_obs();
df_fnet_22 = hainich_obs.df_fnet_22
df_fnet_24 = hainich_obs.df_fnet_24
df_psi_stem_obs = hainich_obs.df_psi_stem_obs
df_sap_flow_2023 = hainich_obs.df_sap_flow_2023


full_dir_paths = filter(isdir, readdir("$rt_path_hyd/output", join=true))
short_dir_paths = basename.(full_dir_paths)
postdir = joinpath(rt_path_hyd, "post")
plt_dir = postdir

run_collections = run_prep(full_dir_paths, short_dir_paths);
run_sel = run_collections[fids];



date_ranges = [
("23", DateTime("2023-07-01"), DateTime("2023-10-30"), DailySeries),
("full", DateTime("2000-01-01"), DateTime("2024-12-31"), DailyAvg),
("03", DateTime("2003-05-01"), DateTime("2003-10-30"), DailySeries),
("18", DateTime("2018-06-01"), DateTime("2018-10-30"), DailySeries),
("19", DateTime("2019-04-01"), DateTime("2019-08-31"), DailySeries)
]



for (ystr, d1, d2, series) in date_ranges

    pltname = "fluxes"
    monthfmt = DateFormat("u")   # "Jan", "Feb", ...

    # --- Extract model & obs data ---
    varname = "gpp_avg"
    list_gpp = get_multi_file_slice(
        run_sel, varname,
        Fluxnetdata, series,
        0.1, 0.9, slice_dates, d1, d2
    )

    varname = "qle_avg"
    list_le = get_multi_file_slice(
        run_sel, varname,
        Fluxnetdata, series,
        0.1, 0.9, slice_dates, d1, d2
    )

    if year(d1) < 2023
        df_obs_gpp_slice = get_single_file_slice(
            df_fnet_22, "GPP", series, 0.05, 0.95,
            slice_dates, d1, d2
        )
        df_obs_le_slice  = get_single_file_slice(
            df_fnet_22, "LE", series, 0.05, 0.95,
            slice_dates, d1, d2
        )
    else
        df_obs_gpp_slice = get_single_file_slice(
            df_fnet_24, "GPP", series, 0.05, 0.95,
            slice_dates, d1, d2
        )
        df_obs_le_slice  = get_single_file_slice(
            df_fnet_24, "LE", series, 0.05, 0.95,
            slice_dates, d1, d2
        )
    end

    # ============================================================
    #  Figure + axes
    # ============================================================

    fig = Figure(resolution = (1200, 800))

    ax1 = Axis(fig[1, 1],
        ylabel = "GPP [μmol C m⁻² s⁻¹]"
    )

    ax2 = Axis(fig[2, 1],
        ylabel = "LE [W m⁻²]",
        xlabel = "Time"
    )

    # ============================================================
    #  GPP PANEL
    # ============================================================

    for i in 1:length(list_gpp)
        df_join = innerjoin(list_gpp[i], df_obs_gpp_slice,
                            on = :DateTime, makeunique = true)
        rmse = sqrt(mean((df_join.mean .- df_join.mean_1).^2))
        rmse = round(rmse, sigdigits = 2)

        lines!(
            ax1,
            list_gpp[i].DateTime,
            list_gpp[i].mean,
            label = "$i RMSE: $rmse"
        )
    end

    # obs in black
    lines!(
        ax1,
        df_obs_gpp_slice.DateTime,
        df_obs_gpp_slice.mean,
        color = :black,
        label = "obs"
    )

    Makie.ylims!(ax1, 0, 16)

    # ============================================================
    #  LE PANEL
    # ============================================================

    for i in 1:length(list_le)
        df_join = innerjoin(list_le[i], df_obs_le_slice,
                            on = :DateTime, makeunique = true)
        rmse = sqrt(mean((abs.(df_join.mean) .- abs.(df_join.mean_1)).^2))
        rmse = round(rmse, sigdigits = 2)

        lines!(
            ax2,
            list_le[i].DateTime,
            -list_le[i].mean,
            label = "$i RMSE: $rmse"
        )
    end

    # obs in black
    lines!(
        ax2,
        df_obs_le_slice.DateTime,
        df_obs_le_slice.mean,
        color = :black,
        label = "obs"
    )

    Makie.ylims!(ax2, 0, 160)

    # ============================================================
    #  Month ticks (for "full")
    # ============================================================

    if ystr == "full"
        # Use GPP obs dates as reference for ticks
        dates = DateTime.(df_obs_gpp_slice.DateTime)

        month_starts = unique(DateTime.(year.(dates), month.(dates), 1))
        month_starts = sort(month_starts)
        month_labels = Dates.format.(month_starts, monthfmt)

        ax1.xticks = (month_starts, month_labels)
        ax2.xticks = (month_starts, month_labels)
    end

    # legends
    axislegend(ax1, position = :rt)
    axislegend(ax2, position = :rt)

    # ============================================================
    #  Save
    # ============================================================

    save(
        joinpath(plt_dir, "$(pltname)_$ystr.png"),
        fig
    )
end


# --------------------------------------------------------------
# Inputs
# --------------------------------------------------------------
d1, d2 = DateTime("2023-07-09"), DateTime("2023-07-27")

pltname = "psi_stem"
varname = "psi_stem_avg"
series = ThirtyMinSeries

# --------------------------------------------------------------
# Load model & obs data
# --------------------------------------------------------------
list_psi_stem = get_multi_file_slice(
    run_sel, varname, Fluxnetdata, series,
    0.1, 0.9, slice_dates, d1, d2
)

df_obs_psi_stem_slice = get_single_file_slice(
    df_psi_stem_obs, "FAG", series, 0.25, 0.75,
    slice_dates, d1, d2
)

# --------------------------------------------------------------
# Figure + Axis
# --------------------------------------------------------------
fig = Figure(resolution = (1200, 800));
ax = Axis(fig[1, 1],
    ylabel = "ψ_stem (units?)",
    xlabel = "Date"
)

# --------------------------------------------------------------
# Plot model runs
# --------------------------------------------------------------
for i in 1:length(list_psi_stem)
    df_join = innerjoin(
        list_psi_stem[i],
        df_obs_psi_stem_slice,
        on = :DateTime,
        makeunique = true
    )

    rmse = sqrt(mean((df_join.mean .- df_join.mean_1).^2))
    rmse = round(rmse, sigdigits = 2)

    lines!(
        ax,
        list_psi_stem[i].DateTime,
        list_psi_stem[i].mean,
        label = "$(fids[i]) RMSE: $rmse",
        transparency = true,
        alpha = 0.7
    )
end

# --------------------------------------------------------------
# Plot observations (black)
# --------------------------------------------------------------
lines!(
    ax,
    df_obs_psi_stem_slice.DateTime,
    df_obs_psi_stem_slice.mean,
    color = :black,
    label = "obs",
    transparency = true,
    alpha = 0.7
)

# --------------------------------------------------------------
# Legend + save
# --------------------------------------------------------------
axislegend(ax, position = :rt)
save(joinpath(plt_dir, "$pltname.png"), fig)





d1, d2 = DateTime("2023-05-01"), DateTime("2023-08-01")

pltname = "stem_flow"
varname = "stem_flow_avg"
series  = DailySeries

# --------------------------------------------------------------
# Load model & obs data
# --------------------------------------------------------------
list_stemflow = get_multi_file_slice(
    run_sel, varname,
    Fluxnetdata, series,
    0.1, 0.9, slice_dates, d1, d2
)

df_obs_sapflow_slice = get_single_file_slice(
    df_sap_flow_2023, "J0.5",
    series, 0.1, 0.9, slice_dates, d1, d2
)

# normalize obs
df_obs_sapflow_slice.mean_norm =
    df_obs_sapflow_slice.mean ./ maximum(df_obs_sapflow_slice.mean)

# --------------------------------------------------------------
# Figure + Axis
# --------------------------------------------------------------
fig = Figure(resolution = (1200, 800));

ax = Axis(fig[1, 1],
    ylabel = "normalized stem flow (-)",
    xlabel = "Date"
)

# --------------------------------------------------------------
# Plot model runs (normalized per run)
# --------------------------------------------------------------
for i in 1:length(list_stemflow)
    smax = maximum(list_stemflow[i].mean)

    # join for RMSE on normalized values
    df_join = innerjoin(
        list_stemflow[i],
        df_obs_sapflow_slice,
        on = :DateTime,
        makeunique = true
    )

    rmse = sqrt(mean((df_join.mean ./ smax .- df_join.mean_norm).^2))
    rmse = round(rmse, sigdigits = 2)

    lines!(
        ax,
        list_stemflow[i].DateTime,
        list_stemflow[i].mean ./ smax,
        label = "$(fids[i]) RMSE: $rmse",
        transparency = true,
        alpha = 0.7
    )
end

# --------------------------------------------------------------
# Plot observations (black, normalized)
# --------------------------------------------------------------
lines!(
    ax,
    df_obs_sapflow_slice.DateTime,
    df_obs_sapflow_slice.mean_norm,
    color = :black,
    label = "obs",
    transparency = true,
    alpha = 0.7
)

# Legend + save
axislegend(ax, position = :rt)

save(joinpath(plt_dir, "$pltname.png"), fig)


function plot_mod_output(varnames, date_ranges)
    for (ystr, d1, d2, series) in date_ranges
        for varname in varnames
            println(varname)
            pltname = varname

            list_mod = get_multi_file_slice(
                run_sel, varname,
                Fluxnetdata, series,
                0.1, 0.9, slice_dates, d1, d2
            )

            # figure & axis (roughly like size=(800, 600))
            fig = Figure(size = (800, 600))
            ax = Axis(fig[1, 1],
                xlabel = "Date",
                ylabel = string(varname),
                title  = "$(varname) ($ystr)"
            )

            # plot each model member
            for i in 1:length(list_mod)
                lines!(
                    ax,
                    list_mod[i].DateTime,
                    list_mod[i].mean,
                    label = string(i),
                    transparency = true,
                    alpha = 0.7,
                )
            end

            axislegend(ax, position = :rt)

            save(joinpath(plt_dir, "$(pltname)_$(ystr).png"), fig)
        end
    end
end

varnames = ["beta_gs", "stem_flow_avg", "LAI", "psi_leaf_avg", "psi_stem_avg",
 "water_potential_soil", "frac_cav_xylem", "total_veg_c", "height", "npp_avg", "het_respiration_avg"]
date_ranges = [
("23", DateTime("2023-07-01"), DateTime("2023-10-30"), DailySeries),
("full", DateTime("2000-01-01"), DateTime("2024-12-31"), DailyAvg),
("03", DateTime("2003-05-01"), DateTime("2003-10-30"), DailySeries),
("18", DateTime("2018-06-01"), DateTime("2018-10-30"), DailySeries),
("19", DateTime("2019-04-01"), DateTime("2019-08-31"), DailySeries)
]


plot_mod_output(varnames, date_ranges)



for (ystr, d1, d2, series) in date_ranges

    if year(d1) < 2023
        df_obs_nee_slice = get_single_file_slice(
            df_fnet_22, "NEE", series, 0.05, 0.95,
            slice_dates, d1, d2
        )
    else
        df_obs_nee_slice = get_single_file_slice(
            df_fnet_24, "NEE", series, 0.05, 0.95,
            slice_dates, d1, d2
        )
    end



    list_mod_npp = get_multi_file_slice(
                    run_sel, "npp_avg",
                    Fluxnetdata, series,
                    0.1, 0.9, slice_dates, d1, d2
                )

    list_mod_het = get_multi_file_slice(
                    run_sel, "het_respiration_avg",
                    Fluxnetdata, series,
                    0.1, 0.9, slice_dates, d1, d2
                )

    # figure & axis (roughly like size=(800, 600))
    fig = Figure(size = (800, 600))
    ax = Axis(fig[1, 1],
        xlabel = "Date",
        ylabel = "NEE",
        title  = "NEE ($ystr)"
    )

    lines!(
        ax,
        df_obs_nee_slice.DateTime,
        df_obs_nee_slice.mean,
        color = :black,
        label = "obs"
    )

    # plot each model member
    for i in 1:length(list_mod_npp)
        lines!(
            ax,
            list_mod_npp[i].DateTime,
            -list_mod_npp[i].mean + list_mod_het[i].mean,
            label = string(i),
            transparency = true,
            alpha = 0.7,
        )
    end

    axislegend(ax, position = :rt)

    save(joinpath(plt_dir, "NEE_$(ystr).png"), fig)
end
