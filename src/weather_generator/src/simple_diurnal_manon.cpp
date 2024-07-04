//
// Created by Phillip on 06.06.24.
//
#include <numeric>
#include <iostream>
#include <algorithm>

#include "simple_diurnal_manon.h"

Simple_Diurnal_Manon_Weather_Generator::Simple_Diurnal_Manon_Weather_Generator(const Gridcell &gridcell):gridcell(gridcell), generator(42) {

    std::iota (HOURS,HOURS + 48,0);
    for (int i = 0; i < 48; ++i) {
        HOURS[i] *= 0.5;
    }
}




double Simple_Diurnal_Manon_Weather_Generator::day_angle(double day_of_year) {
    return 2.0 * PI * (day_of_year - 1) / 365.0;
}

double Simple_Diurnal_Manon_Weather_Generator::calculate_solar_declination(double day_of_year) {
    return -23.4 * (PI / 180.) * std::cos(2. * PI * (day_of_year + 10) / 365.);
}

double Simple_Diurnal_Manon_Weather_Generator::calculate_eqn_of_time(double gamma) {
    return (0.017 + 0.4281 * std::cos(gamma) - 7.351 * std::sin(gamma) - 3.349 *
                                                               std::cos(2. * gamma) - 9.731 * std::sin(gamma));
}

double Simple_Diurnal_Manon_Weather_Generator::calculate_solar_noon(double et) {
    double Ls = round(gridcell.lon / 15.) * 15;
    return 12. + (4. * (Ls - gridcell.lon) - et) / 60.;
}

double Simple_Diurnal_Manon_Weather_Generator::calculate_hour_angle(double t, double t0) {
    return PI * (t - t0) / 12.;
}

std::vector<double> Simple_Diurnal_Manon_Weather_Generator::calculate_solar_geometry(double day_of_year) {
    std::vector<double> cos_zenith(48);

    const double rlat = gridcell.lat * PI / 180.;


    for (int i = 1; i < 48 + 1; ++i) {

        const double hod = i / 2.0;

        const double gamma = day_angle(day_of_year);
        const double dec = calculate_solar_declination(day_of_year);
        const double et = calculate_eqn_of_time(gamma);
        const double t0 = calculate_solar_noon(et);
        const double h = calculate_hour_angle(hod, t0);

        const double sin_beta = std::sin(rlat) * std::sin(dec) + std::cos(rlat) * std::cos(dec) * std::cos(h);
        cos_zenith[i-1] = sin_beta;

        cos_zenith[i-1] = std::min(cos_zenith[i-1], 1.0);
        cos_zenith[i-1] = std::max(cos_zenith[i-1], 0.0);

    }

    return cos_zenith;
}

double Simple_Diurnal_Manon_Weather_Generator::calc_extra_terrestrial_rad(double cos_zen, double day_of_year) {
    const double Sc = 1362.0;
    if (cos_zen > 0.0)
        return Sc * (1. + 0.033 * std::cos(day_of_year / 365. * 2. * PI)) * cos_zen;
    return 0.0;
}

double Simple_Diurnal_Manon_Weather_Generator::spitters(double par_day, std::vector<double> cos_zenith, double day_of_year) {

    double S0 = 0.0;

    for (int i = 0; i < 48; ++i) {
        S0 += (calc_extra_terrestrial_rad(cos_zenith[i], day_of_year)
               * SEC_2_HLFHR * J_TO_MJ);
    }

    // atmospheric transmisivity
    const double tau = (par_day / SW_2_PAR_MJ) / S0;

    if (tau < 0.07)
        return 1.0;
    else if( tau < 0.36)
        return 1.0 - 2.3 * (tau - 0.07) * (tau - 0.07);
    else if( tau < 0.75)
        return 1.33 - 1.46 * tau;
    else
        return 0.23;

}

std::vector<double> Simple_Diurnal_Manon_Weather_Generator::estimate_diurnal_par(double par_day, double day_of_year) {
    std::vector<double> cos_bm(48);
    std::vector<double> cos_df(48);
    std::vector<double> par(48);

    const double tau = 0.76;

    // available light?

    const std::vector<double> cos_zenith = calculate_solar_geometry(day_of_year);
    const double diffuse_frac = spitters(par_day, cos_zenith, day_of_year);
    const double direct_frac = 1.0 - diffuse_frac;

    const double  beam_rad = par_day * direct_frac;
    const double  diffuse_rad = par_day * diffuse_frac;

    double sum_bm = 0.0;
    double sum_df = 0.0;

    for (int i = 0; i < 48; ++i) {

        if(cos_zenith[i] > 0.0){


            double zenith = std::acos(cos_zenith[i]);

            if (zenith < 80.0 * PI / 180.0){
                cos_bm[i] = cos_zenith[i] * std::pow(tau, 1.0/cos_zenith[i]);
            }
            else{
                cos_bm[i] = 0.0;
            }

            cos_df[i] = cos_zenith[i];
            sum_bm += cos_bm[i];
            sum_df += cos_df[i];

        }
    }


    for (int i = 0; i < 48; ++i) {

        double rdbm = 0.0;
        double rddf;

        if(sum_bm > 0.0){
            rdbm = beam_rad * cos_bm[i]/sum_bm;
        }
        else{
            rdbm = 0.0;
        }

        if (sum_df > 0.0){
            rddf = diffuse_rad * cos_df[i]/sum_df;
        }

        par[i] = (rddf + rdbm);  // umol m-2 s-1
    }

    return par;
}

double Simple_Diurnal_Manon_Weather_Generator::calc_day_length(double day_of_year) {

    const double deg2rad = PI/180.0;
    const double rlat = gridcell.lat * deg2rad;

    const double sindec = -std::sin(23.5 * deg2rad) * std::cos(2. * PI * (day_of_year + 10.) / 365.0);
    const double a = std::sin(rlat) * sindec;
    const double b = std::cos(rlat) * std::cos(std::asin(sindec));

    return 12. * (1. + (2. / PI) * std::asin(a / b));
}

std::vector<double> Simple_Diurnal_Manon_Weather_Generator::estimate_diurnal_temp(double tmin, double tmax, double day_of_year) {

    std::vector<double> tday(48);

    // 1.5 m air temperature from Parton & Logan (1981), table 1
    const double a = 1.86;
    const double b = 2.2  ;// nighttime coeffcient
    const double c = -0.17  ;// lag of the min temp from the time of runrisef

    const double day_length = calc_day_length(day_of_year);
    const double night_length = 24 - day_length;
    const double sunrise = 12. - day_length / 2. + c;
    const double sunset = 12. + day_length / 2.;

    // temperature at sunset
    double m = sunset - sunrise + c;
    const double tset = (tmax - tmin) * std::sin(PI * m / (day_length + 2. * a)) + tmin;


    for (int i = 1; i < 48 + 1; ++i) {

        const double hour = i / 2.0;

        m = hour - sunrise + c;

        if ((hour >= sunrise) && (hour <= sunset)){

            double x = tmin + (tmax - tmin) * std::sin(PI * m / (day_length + 2.0 * a));
            tday[i-1] = x;
        }

        else if (hour > sunset){
            double n = hour - sunset;
            double d = (tset - tmin) / (std::exp(b) - 1.);

            tday[i-1] = ((tmin - d) + (tset - tmin - d) *
                                      std::exp(-b * n / (night_length + c)));
        }

        else if (hour < sunrise){
            double n = (24. + hour) - sunset;
            double d = (tset - tmin) / (std::exp(b) - 1.);
            tday[i-1] = ((tmin - d) + (tset - tmin - d) *
                                      std::exp(-b * n / (night_length + c)));

        }
    }

    return tday;
}

std::vector<double> Simple_Diurnal_Manon_Weather_Generator::disaggregate_rainfall(double rain_day) {


    std::uniform_int_distribution< >  uniform48(0, 47);

    std::vector<double> rain(48);

    if (rain_day < 0.0001) {
        return rain;
    }

    else if(rain_day < 1.5){
        int hour_index = uniform48(generator);
        rain[hour_index] = rain_day;
    }

    else if(rain_day > 200){

        for (int i = 0; i < 48; ++i) {
            rain[i] = rain_day/48.0;
        }
    }

    else{

        int num_hrs_with_rain = static_cast<int>(rain_day);
        double rate = rain_day / num_hrs_with_rain;

        for (int i = 0; i < num_hrs_with_rain; ++i) {
            int hour_index = uniform48(generator);
            rain[hour_index] += rate;
        }
    }

    for (int i = 0; i < 48; ++i) {
        rain[i] *= 48.0;
    }

    return rain;
}

std::vector<double>
Simple_Diurnal_Manon_Weather_Generator::estimate_diurnal_vpd(std::vector<double> tair,  double rh) {

    std::vector<double> vpd(48);
    for (int i = 0; i < 48; ++i) {
        double es = 0.61078 * std::exp(17.27 * tair[i] / (tair[i] + 237.3));
        vpd[i] = es * (1.0 - rh)  ; // kPa
    }
    return vpd;
}

std::vector<double> Simple_Diurnal_Manon_Weather_Generator::estimate_diurnal_windspeed(double u0, double day_of_year) {


    std::uniform_real_distribution<>  uniform(0,1);


    std::vector<double> windspeed(48);


    double umid = 0.0;
    double usunset = 0.0;

    double day_length = calc_day_length(day_of_year);
    double sunrise = 12. - day_length / 2.;
    double sunset = 12. + day_length / 2.;

    double value = (uniform)(generator);

    bool increase = value < 0.5 ? true: false;

    if(increase){
        umid =  3.9* u0 * (uniform)(generator)  + 1.1 * u0 ;
        usunset = 0.8* umid * (uniform)(generator)  + 0.1 * umid ;
    }
    else{
        umid =  0.4* u0 * (uniform)(generator)  + 0.1 * u0 ;
        usunset = 1.9* umid * (uniform)(generator)  + 1.1 * umid ;
    }

    for (int i =1; i < 48 + 1; ++i) {

        double hour = i/2.0;
        double du = 0.25 * (uniform)(generator);

        if (i == 1){
            windspeed[i-1] = u0;
        }
        else if( (hour > sunrise) && (hour <= 12.0)){

            if(increase){
                windspeed[i-1] = std::min(umid, windspeed[i-2] + du);
            }
            else{
                windspeed[i-1] = std::max(umid, windspeed[i-2] - du);
            }
        }

        else if( (hour <= sunset) && (hour > 12.0)){

            if(increase){
                windspeed[i-1] = std::max(usunset, windspeed[i-2] - du);
            }
            else{
                windspeed[i-1] = std::min(usunset, windspeed[i-2] + du);
            }
        }
        else{
            windspeed[i-1]  = windspeed[i-2];
        }
    }


    return windspeed;
}

double Simple_Diurnal_Manon_Weather_Generator::estimate_mean_relative_humidity(double tair_mean, double pressure,
                                                                               double specific_humidity) {

    double rh = 0.263 * pressure* specific_humidity / (std::exp(17.67 * tair_mean / (tair_mean + 243.5))) / 100.0;
    if (rh > 1.0)
        return 1.0;

    if (rh < 0.0)
        return 0.0;

    return rh;
}

std::vector<double>
Simple_Diurnal_Manon_Weather_Generator::estimate_diurnal_specific_humidity(std::vector<double> tair, double pressure,
                                                                           double relative_humidiy) {
    std::vector<double> qs(48);
    for (int i = 0; i < 48; ++i) {
        double q = relative_humidiy / 0.263 / pressure * 100.0 * std::exp(17.67 * tair[i] / (tair[i]+ 243.5));

        if (q < 0.0)
            q = 0.0;
        if (q > 1.0)
            q = 1.0;

        qs[i] = q;
    }
    return qs;

}

std::vector<double>
Simple_Diurnal_Manon_Weather_Generator::estimate_diurnal_sw_down(double sw_day, std::vector<double> par_diurnal) {

    std::vector<double> sw_down(48);
    double par_avg = std::accumulate(par_diurnal.begin(), par_diurnal.end(), 0) / 48.0;
    for (int i = 0; i < 48; ++i) {
        sw_down[i] = sw_day * par_diurnal[i]/par_avg;
    }
    return sw_down;
}

std::vector<double>
Simple_Diurnal_Manon_Weather_Generator::estimate_diurnal_lw_down(double lw_day_min, double lw_day_max, double lw_day_mean,
                                                                 std::vector<double> tair) {
    std::vector<double> lw_down(48);

    double tmin = *std::min_element(tair.begin(), tair.end());
    double tmax = *std::max_element(tair.begin(), tair.end());
    double m = (lw_day_max-lw_day_min)/(tmax - tmin);
    double b = -(lw_day_max*tmin-lw_day_min*tmax)/(tmax - tmin);

    for (int i = 0; i < 48; ++i) {
        lw_down[i] = m *  tair[i] + b;
    }

    // Rescale lw_down to match mean
    double lw_down_rvg_avg = std::accumulate(lw_down.begin(), lw_down.end(), 0) / 48.0;

    for (int i = 0; i < 48; ++i) {
        lw_down[i] *= lw_day_mean/lw_down_rvg_avg;
    }

    return lw_down;
}

std::vector<Sudaily_Forcing> Simple_Diurnal_Manon_Weather_Generator::Generate_subdaily_forcing(std::vector<Daily_Forcing> daily_forcings) {

    std::vector<Sudaily_Forcing> subdaily_forcings(daily_forcings.size());

    for (int i = 0; i < daily_forcings.size(); ++i) {

        Daily_Forcing df = daily_forcings[i];
        Sudaily_Forcing& s_df = subdaily_forcings[i];

        s_df.year = df.year;
        s_df.day_of_year = df.day_of_year;

        double day_of_year = df.day_of_year;
        double d_par = df.d_sw_rad * SW_2_PAR;

        std::vector<double> par_du = estimate_diurnal_par(d_par, day_of_year);
        s_df.sd_wind = estimate_diurnal_windspeed(df.d_wind, day_of_year);
        s_df.sd_temp = estimate_diurnal_temp(df.d_tmin, df.d_tmax, day_of_year);
        s_df.sd_rain = disaggregate_rainfall(df.d_rain);

        double rh = estimate_mean_relative_humidity(df.d_tmean, df.d_pressure, df.d_sph);
        s_df.sd_sph = estimate_diurnal_specific_humidity(s_df.sd_temp, df.d_pressure, rh);
        s_df.sd_sw_rad = estimate_diurnal_sw_down(df.d_sw_rad, par_du);
        s_df.sd_lw_rad = estimate_diurnal_lw_down(df.d_lw_rad_min, df.d_lw_rad_max, df.d_lw_rad_mean, s_df.sd_temp);

        s_df.sd_pressure = std::vector<double> (48,df.d_pressure);
    }

    return subdaily_forcings;
}
