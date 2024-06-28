//
// Created by Phillip on 06.06.24.
//
#pragma  once
#include "gridcell.h"
#include <random>
#include <memory>
#include "vars.h"


class Simple_Diurnal_Manon_Weather_Generator {


public:
    Simple_Diurnal_Manon_Weather_Generator(const Gridcell& gridcell);
    std::vector<Sudaily_Forcing>  Generate_subdaily_forcing(std::vector<Daily_Forcing> daily_forcings);

private:

    std::default_random_engine generator;
    const Gridcell& gridcell;

    // Functions
    double day_angle(double day_of_year);

    double calculate_solar_declination(double day_of_year);
    double calculate_eqn_of_time(double gamma);
    double calculate_solar_noon(double et);
    double calculate_hour_angle(double t, double t0);
    std::vector<double> calculate_solar_geometry(double day_of_year);
    double calc_extra_terrestrial_rad(double cos_zen, double day_of_year);
    double spitters(double par_day, std::vector<double> cos_zenith, double day_of_year);

    std::vector<double> estimate_diurnal_par(double par_day, double day_of_year);
    double calc_day_length(double day_of_year);
    std::vector<double> estimate_diurnal_temp(double tmin, double tmax, double day_of_year);
    std::vector<double> disaggregate_rainfall(double rain_day);
    std::vector<double> estimate_diurnal_vpd(std::vector<double> tair, double rh );
    double estimate_mean_relative_humidity(double tair_mean, double pressure, double specific_humidity);
    std::vector<double> estimate_diurnal_specific_humidity(std::vector<double> tair, double pressure, double relative_humidiy);
    std::vector<double> estimate_diurnal_windspeed(double u0, double day_of_year);

    std::vector<double> estimate_diurnal_sw_down(double sw_day, std::vector<double> par_diurnal);
    std::vector<double> estimate_diurnal_lw_down(double lw_day_min, double lw_day_max, double lw_day_mean, std::vector<double> tair);


    // Constants
    const double SW_2_PAR = 4.57 * 0.5;  // SW (W m-2) to PAR (umol m-2 d-1)
    const double PAR_2_SW = 1. / SW_2_PAR;
    const double SW_2_PAR_MJ = 0.5  ;// SW (MJ m-2 d-1) to PAR (umol m-2 d-1)
    const double J_TO_MJ = 1E-6;
    const double SEC_2_DAY = 86400.;
    const double MJ_TO_J = 1E6;
    const double DAY_2_SEC = 1. / SEC_2_DAY;
    const double SEC_2_HLFHR = 1800.;
    const double HLFHR_2_SEC = 1. / SEC_2_HLFHR;
    const double J_TO_UMOL = 4.57;
    const double UMOL_TO_J = 1. / J_TO_UMOL;
    const double UMOLPERJ = 4.57;  //# Conversion from J to umol quanta
    const double PI = 3.14159265358979323846;

    double HOURS[48];

};


