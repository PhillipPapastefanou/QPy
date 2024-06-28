//
// Created by Phillip on 09.06.24.
//
#pragma once
#include <vector>




struct Monthly_Forcing{
    // Atmospheric pressure [Pa]
    double m_pressure;
    // Mean temperature [C]
    double m_tmean;
    // Minimum temperature [C]
    double m_tmin;
    // Maximum temperature [C]
    double m_tmax;
    // Shortwave radiation [W m-2]
    double m_sw_rad;
    // Longwave radiation mean [W m-2]
    double m_lw_rad_mean;
    // Longwave radiation min [W m-2]
    double m_lw_rad_min;
    // Longwave radiation max [W m-2]
    double m_lw_rad_max;
    // Wetdays [1]
    int m_wetdays;
    // Rainfall [mm d-1]
    double m_rain;
//    // Relative humidity [0-1]
//    double m_rh;
    // Specific humidity [g g-1]
    double m_sph;
    // Wind speed [m s-1]
    double m_wind;
};

struct Yearly_Forcing{
    Yearly_Forcing(){
        monthly_forcings.resize(12);
    }
    std::vector<Monthly_Forcing> monthly_forcings;
};



struct Daily_Forcing{

    int year;
    // Day of the calendrical year 0-365 [d]
    int day_of_year;
    // Atmospheric pressure [Pa]
    double d_pressure;
    // Mean temperature [C]
    double d_tmean;
    // Minimum temperature [C]
    double d_tmin;
    // Maximum temperature [C]
    double d_tmax;
    // Shortwave radiation [W m-2]
    double d_sw_rad;
    // Longwave radiation mean [W m-2]
    double d_lw_rad_mean;
    // Longwave radiation min [W m-2]
    double d_lw_rad_min;
    // Longwave radiation max [W m-2]
    double d_lw_rad_max;
    // Rainfall [mm d-1]
    double d_rain;
//    // Relative humidity [0-1]
//    double d_rh;
    // Specific humidity [g g-1]
    double d_sph;
    // Wind speed [m s-1]
    double d_wind;
};


struct Sudaily_Forcing{

public:
    Sudaily_Forcing(){
        sd_pressure.resize(NTIMESTEPS_PERDAY);
        sd_sw_rad.resize(NTIMESTEPS_PERDAY);
        sd_lw_rad.resize(NTIMESTEPS_PERDAY);
        sd_temp.resize(NTIMESTEPS_PERDAY);
        sd_rain.resize(NTIMESTEPS_PERDAY);
        sd_sph.resize(NTIMESTEPS_PERDAY);
        sd_wind.resize(NTIMESTEPS_PERDAY);
    }

    int year;
    // Day of the calendrical year 0-365 [d]
    int day_of_year;
    // Atmospheric pressure [Pa]
    // Atmospheric pressure [Pa]
    std::vector<double> sd_pressure;
    // Mean temperature [C]
    std::vector<double> sd_temp;
    // Shortwave radiation [W m-2]
    std::vector<double> sd_sw_rad;
    // Longwave radiation [W m-2]
    std::vector<double> sd_lw_rad;
    // Rainfall [mm d-1]
    std::vector<double> sd_rain;
    // Specific humidity [g g-1]
    std::vector<double> sd_sph;
    // Wind speed [m s-1]
    std::vector<double> sd_wind;

    const int NTIMESTEPS_PERDAY = 48;

};