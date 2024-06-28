//
// Created by Phillip on 05.06.24.
//
#pragma once

#include "gridcell.h"
#include <random>
#include "auxil.h"
#include "vars.h"

class Simple_Daily_LPJ_Weather_Generator{


public:
    Simple_Daily_LPJ_Weather_Generator(const Gridcell& gridcell);

    std::vector<Daily_Forcing> Generate(std::vector<Yearly_Forcing>);

private:


    const Gridcell& gridcell;
    std::vector<double> rain_daily(std::vector<double> m_prec, std::vector<double> m_wetdays);


    std::vector<double> interp_monthly_means_conserve(const std::vector<double>&  mvals, double minimum = -std::numeric_limits<double>::max(),
                                                      double maximum = std::numeric_limits<double>::max());

    std::vector<double> interp_single_month(double preceding_mean,
                             double this_mean,
                             double succeeding_mean,
                             int time_steps,
                             double minimum = -std::numeric_limits<double>::max(),
                             double maximum = std::numeric_limits<double>::max()) ;


    const std::vector<int> ndaysmonth = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    const int nmonthsinyear = ndaysmonth.size();
    const int NDAYSPERYEAR = 365;

};

