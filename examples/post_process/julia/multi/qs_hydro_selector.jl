include("../../../../src/postprocessing/julia/core/qcomparer.jl")


using CSV
using DataFrames
using Dates
using CairoMakie
using StatsBase  

rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/14_transient_slurm_array"
rt_path_hyd = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/22_transient_slurm_array_krtos"

rmse_data_path = joinpath(rt_path_hyd, "post", "params_rmse.csv")
ana_path = joinpath(rt_path_hyd, "post", "ana")

if !isdir(ana_path)
    mkdir(ana_path)
end

df = CSV.read(rmse_data_path, DataFrame)
df = df[:, .!map(col -> all(x -> ismissing(x) || (x isa Number && isnan(x)), col),
                 eachcol(df))]
df = df[.!isnan.(df.psi_stem_rmse_23), :]


psi_stem_err_ref = 0.13 
stem_flow_err_ref = 0.23 


# Psi_stem constrain
df_psi_stem = filter(row -> (row.psi_stem_rmse_23 < psi_stem_err_ref), df);
print(size(df_psi_stem))

# Psi_stem and stem flow constrain
df_psi_stem_stem_flow = filter(row -> (row.psi_stem_rmse_23 < psi_stem_err_ref) & (row.stem_flow_rmse_23 < stem_flow_err_ref), df);
print(size(df_psi_stem_stem_flow))

# Psi_stem and stem flow with gpp and le constrain
df_psi_stem_stem_flow_23 = filter(row -> (row.psi_stem_rmse_23 < psi_stem_err_ref) & 
    (row.stem_flow_rmse_23 < stem_flow_err_ref) &
    (row.gpp_rmse_23 < 3.3) & (row.le_rmse_23 < 34) , df);
print(size(df_psi_stem_stem_flow_23))

# Psi_stem and stem flow with gpp and le constrain
df_psi_stem_stem_flow_full = filter(row -> (row.psi_stem_rmse_23 < psi_stem_err_ref) & 
    (row.stem_flow_rmse_23 < stem_flow_err_ref) &
    (row.gpp_rmse_full < 3.3) & (row.le_rmse_full < 34) , df);
print(size(df_psi_stem_stem_flow_full))

# Psi_stem and stem flow with gpp and le constrain
df_psi_stem_stem_flow_18 = filter(row -> (row.psi_stem_rmse_23 < psi_stem_err_ref) & 
    (row.stem_flow_rmse_23 < stem_flow_err_ref) &
    (row.gpp_rmse_18 < 3.4) & (row.le_rmse_18 < 34) , df);
print(size(df_psi_stem_stem_flow_18))

# Psi_stem and stem flow with gpp and le constrain
df_psi_stem_stem_flow_03 = filter(row -> (row.psi_stem_rmse_23 < psi_stem_err_ref) & 
    (row.stem_flow_rmse_23 < stem_flow_err_ref) &
    (row.gpp_rmse_03 < 4.0) & (row.le_rmse_03 < 39) , df);
print(size(df_psi_stem_stem_flow_03))


# Psi_stem and stem flow with gpp and le constrain
df_psi_stem_stem_flow_03_18 = filter(row -> (row.psi_stem_rmse_23 < psi_stem_err_ref) & 
    (row.stem_flow_rmse_23 < stem_flow_err_ref) &
    (row.gpp_rmse_18 < 3.5) & (row.le_rmse_18 < 35) &
    (row.gpp_rmse_03 < 4.0) & (row.le_rmse_03 < 40) , df);
print(size(df_psi_stem_stem_flow_03_18))

vscodedisplay(df_psi_stem_stem_flow_03_18) 

# gpp only
gpp_full = filter(row -> (row.gpp_rmse_full < 3.3) , df);
print(size(gpp_full))

# le only
le_full = filter(row -> (row.le_rmse_full < 34) , df);
print(size(le_full))

# gpp only
gpp_le_full = filter(row -> (row.gpp_rmse_full < 3.3) & (row.le_rmse_full < 34), df);
print(size(gpp_le_full))



# 1. Select columns that do NOT contain "RMSE" 
cols = names(dh) .|> String

exclude = ["RMSE", "ID", "FID", "USE_JSB_PHYSICS"]   # patterns to exclude (uppercase for matching)

cols_no_rmse = filter(col -> all(p -> !occursin(p, uppercase(col)), exclude), cols)
cols_rmse = filter(col -> occursin("RMSE", uppercase(col)), cols)

cols_no_rmse

# 2. Grid size (example: 4×4)
rows, ncols = 5, 4
nplots = length(cols_no_rmse)


function plot_histograms(df::DataFrame, cols)

    fig = Figure(size = (1200, 1000));

    for (i, col) in enumerate(cols)
        row   = div(i - 1, ncols) + 1
        colix = mod(i - 1, ncols) + 1

        ax = Axis(fig[row, colix], title = string(col))

        # data column (DataFrame `dh`)
        colsym = Symbol(col)
        data   = df[!, colsym]

        # remove missings
        nonmissing = collect(skipmissing(data))
        isempty(nonmissing) && continue  # nothing to plot

        T = eltype(nonmissing)

        if T <: Number
            # numeric -> ordinary histogram
            hist!(ax, nonmissing; bins = 30)
        else
            # non-numeric (strings, etc.) -> barplot of category counts
            counts = countmap(string.(nonmissing))      # Dict(label => count)
            labels = collect(keys(counts))
            vals   = collect(values(counts))

            # optional: sort by label
            p = sortperm(labels)
            labels = labels[p]
            vals   = vals[p]

            xs = 1:length(labels)
            barplot!(ax, xs, vals)
            ax.xticks = (xs, labels)
        end
    end

    return fig
end
function correlation_heatmap(df::DataFrame, cols)
    # --------------------------------------------------------------
    # 1. Keep only numeric columns from the requested list
    # --------------------------------------------------------------
    numeric_cols = [
        col for col in cols
        if eltype(skipmissing(df[!, col])) <: Number
    ]

    if isempty(numeric_cols)
        error("No numeric columns among: $(cols)")
    end

    # --------------------------------------------------------------
    # 2. Prepare a numeric-only DataFrame
    # --------------------------------------------------------------
    sub = select(df, numeric_cols)
    clean = dropmissing(sub)              # drop rows with missing

    # --------------------------------------------------------------
    # 3. Compute correlation matrix
    # --------------------------------------------------------------
    M = Matrix(clean)                     # convert to numeric matrix
    C = corspearman(M)                            # NxN correlation matrix
    n = length(numeric_cols)

    # --------------------------------------------------------------
    # 4. Makie heatmap
    # --------------------------------------------------------------
    fig = Figure(size = (900, 900))

    ax = Axis(fig[1, 1],
        title = "Correlation matrix",
        xticks = (1:n, string.(numeric_cols)),
        yticks = (1:n, string.(numeric_cols)),
        xlabel = "",
        ylabel = "",
    )

    my_rwb = cgrad(
        [RGBf(1,0,0), RGBf(1,1,1), RGBf(0,0,1)],   # colors
        [0, 0.5, 1];                                # positions
        categorical = false
    )

    hm = heatmap!(
        ax,
        1:n, 1:n, C;
        colormap = my_rwb,
        colorrange = (-0.6, 0.6)
    )
    Colorbar(fig[1, 2], hm, label = "correlation")

    ax.xticklabelrotation = π/4

        # --------------------------------------------------------------
    # 5. Overlay correlation numbers on top of tiles
    # --------------------------------------------------------------
    for i in 1:n
        for j in 1:n
            val = C[i, j]
            # Rounded text label
            txt = @sprintf("%.2f", val)

            # Choose readable text color:
            # tiles near 0 are light (white), tiles near ±1 are darker
            # This heuristic works well:
            textcolor = abs(val) > 0.5 ? :white : :black

            text!(
                ax,
                j, i,                # x, y positions
                text = txt,
                align = (:center, :center),
                color = textcolor,
                fontsize = 14
            )
        end
    end

    return fig
end
function std_out_display(name, df, cols)
    fig = plot_histograms(df, cols)
    save(joinpath(ana_path, "hist_$(name).png"), fig)
    fig = correlation_heatmap(df, cols)
    save(joinpath(ana_path, "corr_$(name).png"), fig)
end


std_out_display("psi_stem", df_psi_stem, cols_no_rmse)
std_out_display("psi_stem_flow", df_psi_stem_stem_flow, cols_no_rmse)
std_out_display("psi_stem_stem_flow_23", df_psi_stem_stem_flow_23, cols_no_rmse)
std_out_display("psi_stem_stem_flow_full", df_psi_stem_stem_flow_full, cols_no_rmse)
std_out_display("psi_stem_stem_flow_18", df_psi_stem_stem_flow_full, cols_no_rmse)
std_out_display("psi_stem_stem_flow_03", df_psi_stem_stem_flow_03, cols_no_rmse)
std_out_display("gpp_full", gpp_full, cols_no_rmse)
std_out_display("le_full", le_full, cols_no_rmse)
std_out_display("gpp_le_full", gpp_le_full, cols_no_rmse)