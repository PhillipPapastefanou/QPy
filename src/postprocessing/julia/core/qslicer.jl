include("qoutput.jl")
include("qtypes.jl")
include("qsite_reader.jl")

using Statistics, VectorizedStatistics
using DataFrames
using Dates

function reduce_time(df_slice, reduction_type::QTimeReductionType, q_low, q_up)

    if reduction_type == ThirtyMinSeries
        rename!(df_slice, :Value => :mean)
        return df_slice
    elseif reduction_type == HourlySeries
        #Todo fix
        #df.HourMin = Dates.Time.(hour.(df.DateTime), minute.(df.DateTime), 1);

    elseif reduction_type == DailySeries
        df_slice.DateTime = map(d -> Date(d), df_slice.DateTime)
        df_avg = combine(groupby(df_slice, :DateTime),
             :Value => mean => :mean,
             :Value => std => :std,
             :Value => median => :median,
             :Value => (x -> quantile(x, q_low)) => :qlow,
             :Value => (x -> quantile(x, q_up)) => :qup)
        return df_avg

    elseif reduction_type == MonthlySeries
        df_slice.YearMonth = Dates.Date.(year.(df_slice.DateTime), month.(df_slice.DateTime), 1);
        df_avg = combine(groupby(df_slice, :YearMonth), 
             :Value => mean => :mean,
             :Value => std => :std,
             :Value => median => :median,
             :Value => (x -> quantile(x, q_low)) => :qlow,
             :Value => (x -> quantile(x, q_up)) => :qup)
        rename!(df_avg, :YearMonth => :DateTime)
        return df_avg

    elseif reduction_type == YearlySeries
        df_slice.Year = Dates.Date.(year.(df_slice.DateTime));
        df_avg = combine(groupby(df_slice, :Year),
            :Value => mean => :mean,
            :Value => median => :median,
            :Value => std => :std,
            :Value => (x -> quantile(x, q_low)) => :qlow,
            :Value => (x -> quantile(x, q_up)) => :qup)
        rename!(df_avg, :Year => :DateTime)
        return df_avg

    elseif reduction_type == ThiryMinAvg
        df_slice.HourMin = Dates.Time.(hour.(df_slice.DateTime), minute.(df_slice.DateTime), 1);
        df_avg = combine(groupby(df_slice, :HourMin), 
            :Value => mean => :mean,
            :Value => median => :median,
            :Value => std => :std,
            :Value => (x -> quantile(x, q_low)) => :qlow,
            :Value => (x -> quantile(x, q_up)) => :qup)
        rename!(df_avg, :HourMin => :DateTime)

        fixed_date = DateTime(2001, 1, 1)
        df_avg[!,"DateTime"] = fixed_date .+ Dates.Hour.(df_avg[:,"DateTime"]/2.0)
        return df_avg

    elseif reduction_type == HourlyAvg
        df_slice.HourMin = Dates.Time.(hour.(df_slice.DateTime));
        df_avg = combine(groupby(df_slice, :HourMin),             
            :Value => mean => :mean,
            :Value => median => :median,
            :Value => std => :std,
            :Value => (x -> quantile(x, q_low)) => :qlow,
            :Value => (x -> quantile(x, q_up)) => :qup)
        rename!(df_avg, :HourMin => :DateTime)
        fixed_date = DateTime(2001, 1, 1)
        df_avg[!,"DateTime"] = fixed_date .+ Dates.Hour.(df_avg[:,"DateTime"])
        return df_avg

    elseif reduction_type == DailyAvg
        df_slice.DayOfYear = map(d -> Dates.dayofyear(d), df_slice.DateTime)
        df_avg = combine(groupby(df_slice, :DayOfYear),
            :Value => mean => :mean,
            :Value => median => :median,
            :Value => std => :std,
            :Value => (x -> quantile(x, q_low)) => :qlow,
            :Value => (x -> quantile(x, q_up)) => :qup)
        rename!(df_avg, :DayOfYear => :DateTime)

        fixed_date = DateTime(2001, 1, 1)
        df_avg[!,"DateTime"] = fixed_date + Dates.Day.(df_avg[:,"DateTime"].-1)
        return df_avg

    elseif reduction_type == MonthlyAvg
        df_slice.Month = map(d -> Dates.month(d), df_slice.DateTime)
        df_avg = combine(groupby(df_slice, :Month),              
            :Value => mean => :mean,
            :Value => median => :median,
            :Value => std => :std,
            :Value => (x -> quantile(x, q_low)) => :qlow,
            :Value => (x -> quantile(x, q_up)) => :qup)
        rename!(df_avg, :Month => :DateTime)

        fixed_date = Date(2001, 1, 1)
        df_avg[!,"DateTime"] = fixed_date + Dates.Month.(df_avg[:,"DateTime"].-1)
        return df_avg
    else
        println("Invalid time reduction type")
    end
end

function slice_years(year_begin::Integer, year_end::Integer)
    dt1 = DateTime(string(year_begin), "yyyy")
    dt2 = DateTime(string(year_end), "yyyy")
    return [dt1, dt2]
end

function slice_years_months(year_begin::Integer, month_being::Integer,
                            year_end::Integer, day_end::Integer)
    dt1 = DateTime("$year_begin-$month_being", "yyyy-mm")
    dt2 = DateTime("$year_end-$day_end", "yyyy-mm")
    return [dt1, dt2]
end

function slice_dates(dt1::DateTime, dt2::DateTime)
    return [dt1, dt2]
end

function get_single_file_slice(df::DataFrame, varname::String, 
                            reduction_type::QTimeReductionType, q_low, q_up,
                            slice_time::Function, dts...)
    dfh = DataFrame(DateTime = df[:,"DateTime"], Value = df[:, varname]);
    dt1, dt2 = slice_time(dts...);
    df_slice = dfh[(dfh.DateTime .>= dt1) .& (dfh.DateTime .< dt2) , :];
    df_slice = reduce_time(df_slice, reduction_type, q_low, q_up);
    return df_slice
end


function get_single_file_slice(df::DataFrame, varname::String, 
                            reduction_type::QTimeReductionType, q_low, q_up)
    dfh = DataFrame(DateTime = df[:, "DateTime"], Value = df[:, varname]);
    df_slice = reduce_time(dfh, reduction_type, q_low, q_up);
    return df_slice
end

function get_single_file_slice(sim::QOutputCollection, varname::String, output_type::QOutputSimulationType, 
                            reduction_type::QTimeReductionType, q_low, q_up,
                            slice_time::Function, dts...)

    data = get_data(sim, varname, output_type);
    df = DataFrame(DateTime = data[1], Value = data[2]);
    dt1, dt2 = slice_time(dts...);
    df_slice = df[(df.DateTime .>= dt1) .& (df.DateTime .< dt2) , :];
    df_slice = reduce_time(df_slice, reduction_type, q_low, q_up);
    return df_slice
end


function get_multi_file_slice(run_collection::QMultiRunCollections, varname::String, output_type::QOutputSimulationType, 
                            reduction_type::QTimeReductionType, q_low, q_up,
                            slice_time::Function, dts...)

    df_arr = Vector{DataFrame}(undef, size(run_collection.output))
    dates = Vector{DateTime}(undef, size(run_collection.output))


    start_time = time()
    last_report = start_time    
    i = 1
    n  = size(run_collection.output)
    for sim in run_collection.output  

        data = get_data(sim, varname, output_type);
        df = DataFrame(DateTime = data[1], Value = data[2]);
        dt1, dt2 = slice_time(dts...);
        df_slice = df[(df.DateTime .>= dt1) .& (df.DateTime .< dt2) , :];
        df_slice = reduce_time(df_slice, reduction_type, q_low, q_up);

        if i == 1
            dates =  df_slice[:,"DateTime"]
        end
        df_arr[i] = df_slice
        i += 1

        last_report = progress_report(i, n, start_time, last_report)

    end
    return df_arr
end


function get_multi_file_slice_layered(run_collection::QMultiRunCollections, varname::String, output_type::QOutputSimulationType, 
                            reduction_type::QTimeReductionType, q_low, q_up, layer,
                            slice_time::Function, dts...)
    df_arr = Vector{DataFrame}(undef, size(run_collection.output))
    dates = Vector{DateTime}(undef, size(run_collection.output))
    i = 1
    for sim in run_collection.output  
        data = get_data(sim, varname, output_type);
        df = DataFrame(DateTime = data[1], Value = data[2][layer,:]);
        dt1, dt2 = slice_time(dts...);
        df_slice = df[(df.DateTime .>= dt1) .& (df.DateTime .< dt2) , :];
        df_slice = reduce_time(df_slice, reduction_type, q_low, q_up);
        if i == 1
            dates =  df_slice[:,"DateTime"]
        end
        df_arr[i] = df_slice
        i += 1
    end
    return dates, df_arr
end



function get_multi_file_slice_layered_avg(run_collection::QMultiRunCollections, varname::String, output_type::QOutputSimulationType, 
                            reduction_type::QTimeReductionType, q_low, q_up, layer,
                            slice_time::Function, dts...)



    dates, df_arr = get_multi_file_slice_layered(run_collection, varname, output_type, 
                            reduction_type, q_low, q_up, layer,
                            slice_time, dts...)


    arr = reduce(hcat, (df.mean for df in df_arr))
    dmean = vec(mean(arr, dims = 2))
    dmedian = vec(median(arr, dims = 2))
    dqlow = vec(vquantile!(arr, q_low, dims = 2))
    dqup= vec(vquantile!(arr, q_up,  dims = 2))

    df_avg = DataFrame(DateTime = dates,
                    mean = dmean,
                    median = dmedian, 
                    qlow = dqlow, 
                    qup = dqup
                    )
    return df_avg

end



function get_multi_file_slice_avg(run_collection::QMultiRunCollections, varname::String, output_type::QOutputSimulationType, 
                            reduction_type::QTimeReductionType, q_low, q_up,
                            slice_time::Function, dts...)

    df_arr = Vector{DataFrame}(undef, size(run_collection.output))
    dates = Vector{DateTime}(undef, size(run_collection.output))
    i = 1
    for sim in run_collection.output  


        data = get_data(sim, varname, output_type);

        df = DataFrame(DateTime = data[1], Value = data[2]);
        dt1, dt2 = slice_time(dts...);
        df_slice = df[(df.DateTime .>= dt1) .& (df.DateTime .< dt2) , :];
        df_slice = reduce_time(df_slice, reduction_type, q_low, q_up);

        if i == 1
            dates =  df_slice[:,"DateTime"]
        end
        df_arr[i] = df_slice
        i += 1
    end

    arr = reduce(hcat, (df.mean for df in df_arr))
    dmean = vec(mean(arr, dims = 2))
    dmedian = vec(median(arr, dims = 2))
    dqlow = vec(vquantile!(arr, q_low, dims = 2))
    dqup= vec(vquantile!(arr, q_up,  dims = 2))

    df_avg = DataFrame(DateTime = dates,
                    mean = dmean,
                    median = dmedian, 
                    qlow = dqlow, 
                    qup = dqup
                    )
    return df_avg
end



function get_single_file_slice(sim::QOutputCollection, varname::String, output_type::QOutputSimulationType,
                            reduction_type::QTimeReductionType, q_low, q_up)

    data = get_data(sim, varname, output_type);
    df = DataFrame(DateTime = data[1], Value = data[2]); 
    df_slice = reduce_time(df, reduction_type, q_low, q_up);       
    return df_slice
end




function progress_report(i, n, start_time, last_report; interval=5.0)
    now = time()
    if now - last_report ≥ interval
        elapsed = now - start_time
        frac_done = i / n
        est_total = elapsed / frac_done
        remaining = est_total - elapsed

        @info "Progress $(round(100*frac_done, digits=1))% | " *
              "step $i/$n | remaining ≈ $(round(remaining, digits=1)) s"

        return now   # update last_report
    end
    return last_report
end