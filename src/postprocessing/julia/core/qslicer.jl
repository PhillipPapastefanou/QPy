include("qoutput.jl")
include("qtypes.jl")
include("qsite_reader.jl")

using Statistics, VectorizedStatistics
using DataFrames
using Dates

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

"""
    summarize_value(gdf; q_low, q_up)

Given a grouped DataFrame whose groups contain column `:Value`,
compute standard summary stats.
"""
function summarize_value(gdf; q_low, q_up)
    combine(
        gdf,
        :Value => mean   => :mean,
        :Value => std    => :std,
        :Value => median => :median,
        :Value => (x -> quantile(x, q_low)) => :qlow,
        :Value => (x -> quantile(x, q_up))  => :qup,
    )
end

"""
    summarize_value_no_std(gdf; q_low, q_up)

Same as `summarize_value` but without std if you want a slightly
lighter result. Only used where you really don't need :std.
"""
function summarize_value_no_std(gdf; q_low, q_up)
    combine(
        gdf,
        :Value => mean   => :mean,
        :Value => median => :median,
        :Value => (x -> quantile(x, q_low)) => :qlow,
        :Value => (x -> quantile(x, q_up))  => :qup,
    )
end


# ----------------------------------------------------------------------
# Time reduction
# ----------------------------------------------------------------------

function reduce_time(df_slice::DataFrame,
                     reduction_type::QTimeReductionType,
                     q_low,
                     q_up)

    # Make sure we are not accidentally changing caller's DataFrame
    df_slice = copy(df_slice)

    if reduction_type == ThirtyMinSeries
        rename!(df_slice, :Value => :mean)
        return df_slice

    elseif reduction_type == HourlySeries
        # Example implementation: aggregate to hourly series.
        # If your expected behaviour is different, adjust here.
        df_slice.Hour = DateTime.(Date.(df_slice.DateTime),
                                  Hour.(df_slice.DateTime))
        df_hour = summarize_value(groupby(df_slice, :Hour);
                                  q_low=q_low, q_up=q_up)
        rename!(df_hour, :Hour => :DateTime)
        return df_hour

    elseif reduction_type == DailySeries
        df_slice.Date = Date.(df_slice.DateTime)
        df_avg = summarize_value(groupby(df_slice, :Date);
                                 q_low=q_low, q_up=q_up)
        rename!(df_avg, :Date => :DateTime)
        return df_avg

    elseif reduction_type == MonthlySeries
        df_slice.YearMonth = Date.(year.(df_slice.DateTime),
                                   month.(df_slice.DateTime),
                                   1)
        df_avg = summarize_value(groupby(df_slice, :YearMonth);
                                 q_low=q_low, q_up=q_up)
        rename!(df_avg, :YearMonth => :DateTime)
        return df_avg

    elseif reduction_type == YearlySeries
        df_slice.Year = Date.(year.(df_slice.DateTime), 1, 1)
        df_avg = summarize_value(groupby(df_slice, :Year);
                                 q_low=q_low, q_up=q_up)
        rename!(df_avg, :Year => :DateTime)
        return df_avg

    elseif reduction_type == ThiryMinAvg  # note: typo preserved from enum
        df_slice.HourMin = Time.(hour.(df_slice.DateTime),
                                 minute.(df_slice.DateTime),
                                 0)
        df_avg = summarize_value(groupby(df_slice, :HourMin);
                                 q_low=q_low, q_up=q_up)
        rename!(df_avg, :HourMin => :DateTime)

        fixed_date = DateTime(2001, 1, 1)
        # Convert Time-of-day to half-hour index by total minutes ÷ 30
        idx = (Dates.minute.(df_avg.DateTime) .+
               60 .* Dates.hour.(df_avg.DateTime)) ./ 30
        df_avg.DateTime .= fixed_date .+ Hour.(idx ./ 2)  # keep as dummy timeline
        return df_avg

    elseif reduction_type == HourlyAvg
        df_slice.Hour = hour.(df_slice.DateTime)
        df_avg = summarize_value(groupby(df_slice, :Hour);
                                 q_low=q_low, q_up=q_up)
        rename!(df_avg, :Hour => :DateTime)

        fixed_date = DateTime(2001, 1, 1)
        df_avg.DateTime .= fixed_date .+ Hour.(df_avg.DateTime)
        return df_avg

    elseif reduction_type == DailyAvg
        df_slice.DayOfYear = dayofyear.(df_slice.DateTime)
        df_avg = summarize_value(groupby(df_slice, :DayOfYear);
                                 q_low=q_low, q_up=q_up)
        rename!(df_avg, :DayOfYear => :DateTime)

        fixed_date = DateTime(2001, 1, 1)
        df_avg.DateTime .= fixed_date .+ Day.(df_avg.DateTime .- 1)
        return df_avg

    elseif reduction_type == MonthlyAvg
        df_slice.Month = month.(df_slice.DateTime)
        df_avg = summarize_value(groupby(df_slice, :Month);
                                 q_low=q_low, q_up=q_up)
        rename!(df_avg, :Month => :DateTime)

        fixed_date = Date(2001, 1, 1)
        df_avg.DateTime .= fixed_date .+ Month.(df_avg.DateTime .- 1)
        return df_avg

    else
        error("Invalid time reduction type: $reduction_type")
    end
end

# ----------------------------------------------------------------------
# Slicing helpers
# ----------------------------------------------------------------------

slice_years(year_begin::Integer, year_end::Integer) =
    (DateTime(string(year_begin), "yyyy"),
     DateTime(string(year_end),   "yyyy"))

# NOTE: second argument was called `month_being` and `day_end` but used as month.
# I renamed them to make the intention clearer but kept same behaviour.
slice_years_months(year_begin::Integer, month_begin::Integer,
                   year_end::Integer,   month_end::Integer) =
    (DateTime("$year_begin-$month_begin", "yyyy-mm"),
     DateTime("$year_end-$month_end",     "yyyy-mm"))

slice_dates(dt1::DateTime, dt2::DateTime) = (dt1, dt2)

# ----------------------------------------------------------------------
# Single-file helpers (DataFrame)
# ----------------------------------------------------------------------

function get_single_file_slice(df::DataFrame,
                               varname::AbstractString,
                               reduction_type::QTimeReductionType,
                               q_low, q_up,
                               slice_time::Function,
                               dts...)
    dfh = DataFrame(
        DateTime = df.DateTime,
        Value    = df[!, varname],
    )
    dt1, dt2 = slice_time(dts...)
    df_slice = dfh[(dfh.DateTime .>= dt1) .& (dfh.DateTime .< dt2), :]
    return reduce_time(df_slice, reduction_type, q_low, q_up)
end

function get_single_file_slice(df::DataFrame,
                               varname::AbstractString,
                               reduction_type::QTimeReductionType,
                               q_low, q_up)
    dfh = DataFrame(
        DateTime = df.DateTime,
        Value    = df[!, varname],
    )
    return reduce_time(dfh, reduction_type, q_low, q_up)
end

# ----------------------------------------------------------------------
# Single-file helpers (QOutputCollection)
# ----------------------------------------------------------------------

function get_single_file_slice(sim::QOutputCollection,
                               varname::AbstractString,
                               output_type::QOutputSimulationType,
                               reduction_type::QTimeReductionType,
                               q_low, q_up,
                               slice_time::Function,
                               dts...)
    data = get_data(sim, varname, output_type)
    df = DataFrame(DateTime = data[1], Value = data[2])
    dt1, dt2 = slice_time(dts...)
    df_slice = df[(df.DateTime .>= dt1) .& (df.DateTime .< dt2), :]
    return reduce_time(df_slice, reduction_type, q_low, q_up)
end

function get_single_file_slice(sim::QOutputCollection,
                               varname::AbstractString,
                               output_type::QOutputSimulationType,
                               reduction_type::QTimeReductionType,
                               q_low, q_up)
    data = get_data(sim, varname, output_type)
    df = DataFrame(DateTime = data[1], Value = data[2])
    return reduce_time(df, reduction_type, q_low, q_up)
end

# ----------------------------------------------------------------------
# Multi-file helpers
# ----------------------------------------------------------------------

function _slice_and_reduce(sim::QOutputCollection,
                           varname::AbstractString,
                           output_type::QOutputSimulationType,
                           reduction_type::QTimeReductionType,
                           q_low, q_up,
                           dt1::DateTime, dt2::DateTime;
                           layer::Union{Nothing,Int}=nothing)

    data = get_data(sim, varname, output_type)
    if layer === nothing
        df = DataFrame(DateTime = data[1], Value = data[2])
    else
        df = DataFrame(DateTime = data[1], Value = data[2][layer, :])
    end

    df_slice = df[(df.DateTime .>= dt1) .& (df.DateTime .< dt2), :]
    return reduce_time(df_slice, reduction_type, q_low, q_up)
end

function get_multi_file_slice(run_collection::QMultiRunCollections,
                              varname::AbstractString,
                              output_type::QOutputSimulationType,
                              reduction_type::QTimeReductionType,
                              q_low, q_up,
                              slice_time::Function,
                              dts...)

    n = length(run_collection.output)
    df_arr = Vector{DataFrame}(undef, n)

    dt1, dt2 = slice_time(dts...)
    start_time = time()
    last_report = start_time

    for (i, sim) in enumerate(run_collection.output)
        df_slice = _slice_and_reduce(sim, varname, output_type,
                                     reduction_type, q_low, q_up,
                                     dt1, dt2)
        df_arr[i] = df_slice
        last_report = progress_report(i, n, start_time, last_report)
    end
    return df_arr
end

function get_multi_file_slice_layered(run_collection::QMultiRunCollections,
                                      varname::AbstractString,
                                      output_type::QOutputSimulationType,
                                      reduction_type::QTimeReductionType,
                                      q_low, q_up,
                                      layer::Int,
                                      slice_time::Function,
                                      dts...)

    n = length(run_collection.output)
    df_arr = Vector{DataFrame}(undef, n)

    dt1, dt2 = slice_time(dts...)

    # first simulation
    first_df = _slice_and_reduce(run_collection.output[1],
                                 varname, output_type,
                                 reduction_type, q_low, q_up,
                                 dt1, dt2;
                                 layer=layer)
    dates = copy(first_df.DateTime)
    df_arr[1] = first_df

    start_time = time()
    last_report = start_time

    # remaining simulations (FIXED LOOP)
    for i in 2:n
        sim = run_collection.output[i]
        df_arr[i] = _slice_and_reduce(sim, varname, output_type,
                                      reduction_type, q_low, q_up,
                                      dt1, dt2;
                                      layer=layer)
        last_report = progress_report(i, n, start_time, last_report)
    end

    return dates, df_arr
end

function get_multi_file_slice_layered_avg(run_collection::QMultiRunCollections,
                                          varname::AbstractString,
                                          output_type::QOutputSimulationType,
                                          reduction_type::QTimeReductionType,
                                          q_low, q_up,
                                          layer::Int,
                                          slice_time::Function,
                                          dts...)

    dates, df_arr = get_multi_file_slice_layered(run_collection,
                                                 varname, output_type,
                                                 reduction_type, q_low, q_up,
                                                 layer,
                                                 slice_time, dts...)

    arr = reduce(hcat, (df.mean for df in df_arr))
    dmean   = vec(mean(arr,   dims=2))
    dmedian = vec(median(arr, dims=2))
    dqlow   = vec(vquantile!(copy(arr), q_low, dims=2))
    dqup    = vec(vquantile!(copy(arr), q_up,  dims=2))

    return DataFrame(
        DateTime = dates,
        mean     = dmean,
        median   = dmedian,
        qlow     = dqlow,
        qup      = dqup,
    )
end

function get_multi_file_slice_avg(run_collection::QMultiRunCollections,
                                  varname::AbstractString,
                                  output_type::QOutputSimulationType,
                                  reduction_type::QTimeReductionType,
                                  q_low, q_up,
                                  slice_time::Function,
                                  dts...)

    n = length(run_collection.output)
    df_arr = Vector{DataFrame}(undef, n)

    dt1, dt2 = slice_time(dts...)

    # first simulation
    first_df = _slice_and_reduce(run_collection.output[1],
                                 varname, output_type,
                                 reduction_type, q_low, q_up,
                                 dt1, dt2)
    dates = copy(first_df.DateTime)
    df_arr[1] = first_df

    # remaining simulations (FIXED LOOP)
    for i in 2:n
        sim = run_collection.output[i]
        df_arr[i] = _slice_and_reduce(sim, varname, output_type,
                                      reduction_type, q_low, q_up,
                                      dt1, dt2)
    end

    arr     = reduce(hcat, (df.mean for df in df_arr))
    dmean   = vec(mean(arr,   dims=2))
    dmedian = vec(median(arr, dims=2))
    dqlow   = vec(vquantile!(copy(arr), q_low, dims=2))
    dqup    = vec(vquantile!(copy(arr), q_up,  dims=2))

    return DataFrame(
        DateTime = dates,
        mean     = dmean,
        median   = dmedian,
        qlow     = dqlow,
        qup      = dqup,
    )
end

# ----------------------------------------------------------------------
# Progress reporting
# ----------------------------------------------------------------------
using Printf

# helper to format seconds as hh:mm:ss
function format_hms(t::Real)
    t = max(0, round(Int, t))  # avoid negatives & make it an Int
    h = t ÷ 3600
    m = (t % 3600) ÷ 60
    s = t % 60
    return @sprintf("%02d:%02d:%02d", h, m, s)
end


function progress_report(i, n, start_time, last_report; interval=5.0)
    now = time()
    if now - last_report >= interval
        elapsed   = now - start_time
        frac_done = i / n
        est_total = elapsed / max(frac_done, eps()) # avoid div-by-zero
        remaining = est_total - elapsed

        elapsed_str   = format_hms(elapsed)
        remaining_str = format_hms(remaining)

        @info "Progress $(round(100 * frac_done, digits=1))% | " *
              "step $i/$n | " *
              "elapsed $elapsed_str | " *
              "remaining ≈ $remaining_str"

        return now
    end
    return last_report
end