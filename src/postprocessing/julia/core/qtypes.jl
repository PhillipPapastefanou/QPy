@enum QOutputTimeDim Timestep Daily Weekly Monthly Yearly

@enum QOutputSimulationType Static Transient Spinup Fluxnetdata

@enum QTimeReductionType ThirtyMinSeries HourlySeries DailySeries MonthlySeries YearlySeries ThiryMinAvg HourlyAvg DailyAvg MonthlyAvg

function convert_to_output_time_dim(str)
    if str == "timestep"
        return Timestep
    elseif str == "daily"
        return Daily
    elseif str == "weekly"
        return Weekly
    elseif str == "monthly"
        return Monthly
    elseif str == "yearly"
        return Yearly
    else
        error("Invalid or unsupported time type: " *str)
    end
end

function convert_to_output_simumation_type(str)
    if str == "static"
        return Static
    elseif str == "transient"
        return Transient
    elseif str == "spinup"
        return Spinup
    elseif str == "fluxnetdata"
        return Fluxnetdata
    else
        error("Invalid or unsupported simulation type: " *str)
    end
end