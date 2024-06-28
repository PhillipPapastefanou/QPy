//
// Created by Phillip on 05.06.24.
//

#include "simple_daily_lpj.h"
#include <iostream>
#include <algorithm>
#include <random>

Simple_Daily_LPJ_Weather_Generator::Simple_Daily_LPJ_Weather_Generator(const Gridcell &gridcell): gridcell(gridcell){



}

std::vector<Daily_Forcing>  Simple_Daily_LPJ_Weather_Generator::Generate(std::vector<Yearly_Forcing> yearly_forcing) {

    std::vector<Daily_Forcing> daily_forcings(yearly_forcing.size() * NDAYSPERYEAR);

    int u = 0;

    for (int yi = 0; yi < yearly_forcing.size(); ++yi) {

        const std::vector<Monthly_Forcing>& monthly_forcings = yearly_forcing[yi].monthly_forcings;

        std::vector<double> m_rain(nmonthsinyear);
        std::vector<double> m_pressure(nmonthsinyear);
        std::vector<double> m_wetdays(nmonthsinyear);
        std::vector<double> m_tmean(nmonthsinyear);
        std::vector<double> m_tmin(nmonthsinyear);
        std::vector<double> m_tmax(nmonthsinyear);
        std::vector<double> m_sph(nmonthsinyear);
        std::vector<double> m_sw_down(nmonthsinyear);
        std::vector<double> m_lw_down(nmonthsinyear);
        std::vector<double> m_wind(nmonthsinyear);

        for (int m = 0; m < nmonthsinyear; ++m)
        {
            m_rain[m] = monthly_forcings[m].m_rain;
            m_pressure[m] = monthly_forcings[m].m_pressure;
            m_wetdays[m] = monthly_forcings[m].m_wetdays;
            m_tmean[m] = monthly_forcings[m].m_tmean;
            m_tmin[m] = monthly_forcings[m].m_tmin;
            m_tmax[m] = monthly_forcings[m].m_tmax;
            m_sw_down[m] = monthly_forcings[m].m_sw_rad;
            m_lw_down[m] = monthly_forcings[m].m_lw_rad_mean;
            m_sph[m] = monthly_forcings[m].m_sph;
            m_wind[m] = monthly_forcings[m].m_wind;
        }

        auto d_rain = rain_daily(m_rain, m_wetdays);
        auto d_tmean= interp_monthly_means_conserve(m_tmean);
        auto d_tmin = interp_monthly_means_conserve(m_tmin);
        auto d_tmax = interp_monthly_means_conserve(m_tmax);
        auto d_sw_down = interp_monthly_means_conserve(m_sw_down);
        auto d_lw_down = interp_monthly_means_conserve(m_lw_down);
        auto d_sph = interp_monthly_means_conserve(m_sph);
        auto d_wind = interp_monthly_means_conserve(m_wind);
        auto d_pressure = interp_monthly_means_conserve(m_pressure);

        for (int d = 0; d < NDAYSPERYEAR; ++d) {

            Daily_Forcing& df = daily_forcings[u];

            df.year = yi;
            df.day_of_year = d;
            df.d_sw_rad  = d_sw_down[d];
            df.d_lw_rad_mean  = d_lw_down[d];
            df.d_rain     = d_rain[d];
            df.d_tmean     = d_tmean[d];
            df.d_tmin     = d_tmin[d];
            df.d_tmax     = d_tmax[d];
            df.d_sph     = d_sph[d];
            df.d_wind     = d_wind[d];
            df.d_pressure     = d_pressure[d];


            df.d_lw_rad_min = d_lw_down[d] * 0.8;
            df.d_lw_rad_max= d_lw_down[d] * 1.2;

            u++;
        }
    }

    return daily_forcings;
}

std::vector<double> Simple_Daily_LPJ_Weather_Generator::rain_daily(std::vector<double> m_prec, std::vector<double> m_wetdays) {

    std::random_device rd;  // Will be used to obtain a seed for the random number engine
    std::mt19937 gen(42); // Standard mersenne_twister_engine seeded with rd()
    std::uniform_real_distribution<> dis(0, 1);

    //  Distribution of monthly precipitation totals to quasi-daily values
    //  (From Dieter Gerten 021121)

    const double c1 = 1.0; // normalising coefficient for exponential distribution
    const double c2 = 1.2; // power for exponential distribution

    int m, d, dy, dyy, dy_hold;
    int daysum;
    double prob_rain; // daily probability of rain for this month
    double mprec; // average rainfall per rain day for this month
    double mprec_sum; // cumulative sum of rainfall for this month
    // (= mprecip in Dieter's code)
    double prob;

    dy = 0;
    daysum = 0;

    std::vector<double> d_prec(NDAYSPERYEAR);

    for (m=0; m<12; m++) {

        if (m_prec[m] < 0.1) {

            // Special case if no rainfall expected for month
            for (d=0; d<ndaysmonth[m]; d++) {
                d_prec[dy] = 0.0;
                dy++;
            }
        }
        else {

            mprec_sum = 0.0;

            m_wetdays[m] = std::max (m_wetdays[m], 1.0);
            // force at least one rain day per month

            // rain on wet days (should be at least 0.1)
            mprec = std::max(m_prec[m]/m_wetdays[m], 0.1);
            m_wetdays[m] = m_prec[m] / mprec;

            prob_rain = m_wetdays[m] / (double)ndaysmonth[m];

            dy_hold = dy;

            while (std::abs(mprec_sum) < 1E-10) {

                dy = dy_hold;

                for (d=0; d<ndaysmonth[m]; d++) {

                    // Transitional probabilities (Geng et al 1986)

                    if (dy == 0) { // first day of year only
                        prob = 0.75 * prob_rain;
                    }
                    else {
                        if (d_prec[dy-1] < 0.1)
                            prob = 0.75 * prob_rain;
                        else
                            prob = 0.25 + (0.75 * prob_rain);
                    }

                    // Determine wet days randomly and use Krysanova/Cramer estimates of
                    // parameter values (c1,c2) for an exponential distribution
                    if (dis(gen) > prob)
                        d_prec[dy] = 0.0;
                    else {
                        double x=dis(gen) ;
                        d_prec[dy] = pow(-log(x), c2) * mprec * c1;
                        if (d_prec[dy] < 0.1) d_prec[dy] = 0.0;
                    }
                    mprec_sum += d_prec[dy];
                    dy++;
                }

                // Normalise generated precipitation by prescribed monthly totals

                if (std::abs(mprec_sum) > 1E-10) {
                    for (d=0; d<ndaysmonth[m]; d++) {
                        dyy = daysum + d;
                        d_prec[dyy] *= m_prec[m] / mprec_sum;
                        //if (truncate && d_prec[dyy] < 0.1) d_prec[dyy] = 0.0;
                    }
                }
            }
        }

        daysum += ndaysmonth[m];
    }

    return d_prec;
}



std::vector<double>
Simple_Daily_LPJ_Weather_Generator::interp_single_month(double preceding_mean, double this_mean, double succeeding_mean,
                                                        int time_steps, double minimum, double maximum) {

    std::vector<double> result(time_steps);

    // The values for the beginning and the end of the month are determined
    // from the average of the two adjacent monthly means
    const double first_value = mean(this_mean, preceding_mean);
    const double last_value = mean(this_mean, succeeding_mean);

    // The mid-point value is computed as offset from the mean, so that the
    // average deviation from the mean of first_value and last_value
    // is compensated for.
    // E.g., if the two values at beginning and end of the month are on average
    // 2 degrees cooler than the monthly mean, the mid-monthly value is
    // determined as monthly mean + 2 degrees, so that the monthly mean is
    // conserved.
    const double average_deviation =
            mean(first_value-this_mean, last_value-this_mean);

    const double middle_value = this_mean-average_deviation;
    const double half_time = time_steps/2.0;

    const double first_slope = (middle_value-first_value)/half_time;
    const double second_slope = (last_value-middle_value)/half_time;

    double sum = 0;
    int i = 0;

    // Interpolate the first half
    for (; i < time_steps/2; ++i) {
        double current_time = i+0.5; // middle of day i
        result[i] = first_value + first_slope*current_time;
        sum += result[i];
    }

    // Special case for dealing with the middle day if time_steps is odd
    if (time_steps%2 == 1) {
        // In this case we can't use the value corresponding to the middle
        // of the day. We'll simply skip it and calculate it based on
        // whatever the other days sum up to.
        ++i;
    }

    // Interpolate the other half
    for (; i < time_steps; ++i) {
        double current_time = i+0.5; // middle of day i
        result[i] = middle_value + second_slope*(current_time-half_time);
        sum += result[i];
    }

    if (time_steps%2 == 1) {
        // Go back and set the middle value to whatever is needed to
        // conserve the mean
        result[time_steps/2] = time_steps*this_mean-sum;
    }

    // Go through all values and make sure they're all above the minimum
    double added = 0;
    double sum_above = 0;

    for (int i = 0; i < time_steps; ++i) {
        if (result[i] < minimum) {
            added += minimum - result[i];
            result[i] = minimum;
        }
        else {
            sum_above += result[i] - minimum;
        }
    }

    double fraction_to_remove = sum_above > 0 ? added / sum_above : 0;

    for (int i = 0; i < time_steps; ++i) {
        if (result[i] > minimum) {
            result[i] -= fraction_to_remove * (result[i] - minimum);

            // Needed (only) due to limited precision in floating point arithmetic
            result[i] = std::max(result[i], minimum);
        }
    }

    // Go through all values and make sure they're all below the maximum
    double removed = 0;
    double sum_below = 0;

    for (int i = 0; i < time_steps; ++i) {
        if (result[i] > maximum) {
            removed += result[i] - maximum;
            result[i] = maximum;
        }
        else {
            sum_below += maximum - result[i];
        }
    }

    double fraction_to_add = sum_below > 0 ? removed / sum_below : 0;

    for (int i = 0; i < time_steps; ++i) {
        if (result[i] < maximum) {
            result[i] += fraction_to_add * (maximum - result[i]);

            // Needed (only) due to limited precision in floating point arithmetic
            result[i] = std::min(result[i], maximum);
        }
    }
    return result;
}

std::vector<double>
Simple_Daily_LPJ_Weather_Generator::interp_monthly_means_conserve(const std::vector<double>& mvals, double minimum,
                                                                  double maximum) {
    std::vector<double> dvals(NDAYSPERYEAR);
    int start_of_month = 0;
    for (int m = 0; m < 12; m++) {

        // Index of previous and next month, with wrap-around
        int next = (m+1)%12;
        int prev = (m+11)%12;

        // If a monthly mean value is outside of the allowed limits for daily
        // values (for instance negative radiation), we'll fail to make sure
        // the user knows the forcing data is broken.
        if (mvals[m] < minimum || mvals[m] > maximum) {
            std::cout << "interp_monthly_means_conserve: Invalid monthly value given (%g), min = %g, max = %g",
                 mvals[m];
            exit(99);
        }

        std::vector<double> dvals_of_month  = interp_single_month(mvals[prev], mvals[m], mvals[next],
                            ndaysmonth[m],
                            minimum, maximum);

        for (int d = 0; d < ndaysmonth[m]; ++d) {
            dvals[start_of_month + d] = dvals_of_month[d];
        }
        start_of_month += ndaysmonth[m];
    }

    return dvals;
}


