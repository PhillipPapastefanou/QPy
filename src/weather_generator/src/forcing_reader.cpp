//
// Created by Phillip on 10.06.24.
//

#include "forcing_reader.h"
#include <numeric>
#include <string>

ForcingReader::ForcingReader(std::string filename): reader(filename, true, ','){

}


std::vector<Yearly_Forcing> ForcingReader::ParseInput() {

    std::vector<int> indexes(10);
    for (int i = 0; i < 10; ++i) {
        indexes[i] = i + 1;
    }

    std::vector<std::string> header_str = reader.header;
    std::vector<std::vector<double> > data = reader.Get<double>(indexes);

    int tmp_avg_index = std::distance(header_str.begin(),std::find(header_str.begin(), header_str.end(), "tmp"));
    int rain_avg_index = std::distance(header_str.begin(),std::find(header_str.begin(), header_str.end(), "pre"));
    int pres_avg_index = std::distance(header_str.begin(),std::find(header_str.begin(), header_str.end(), "pres"));
    int sph_avg_index = std::distance(header_str.begin(),std::find(header_str.begin(), header_str.end(), "spfh"));
    int tmax_avg_index = std::distance(header_str.begin(),std::find(header_str.begin(), header_str.end(), "tmax"));
    int tmin_avg_index = std::distance(header_str.begin(),std::find(header_str.begin(), header_str.end(), "tmin"));
    int wetdays_avg_index = std::distance(header_str.begin(),std::find(header_str.begin(), header_str.end(), "wetdays"));
    int swdown_avg_index = std::distance(header_str.begin(),std::find(header_str.begin(), header_str.end(), "tswrf"));
    int lwdown_avg_index = std::distance(header_str.begin(),std::find(header_str.begin(), header_str.end(), "dlwrf"));
    int wind_avg_index = std::distance(header_str.begin(),std::find(header_str.begin(), header_str.end(), "wind"));

    std::vector<Yearly_Forcing> yearly_forcings;

    int nmonth = data.size();
    int i = 0;

    while(i < nmonth){

        Yearly_Forcing y_forcing;

        for (int m = 0; m < 12; ++m) {
            y_forcing.monthly_forcings[m].m_tmean = data[i][tmp_avg_index - 1];
            y_forcing.monthly_forcings[m].m_tmin = data[i][tmin_avg_index - 1];
            y_forcing.monthly_forcings[m].m_tmax = data[i][tmax_avg_index - 1];
            y_forcing.monthly_forcings[m].m_rain = data[i][rain_avg_index - 1];
            y_forcing.monthly_forcings[m].m_pressure = data[i][pres_avg_index - 1];
            y_forcing.monthly_forcings[m].m_wetdays = std::round(data[i][wetdays_avg_index - 1]);
            y_forcing.monthly_forcings[m].m_sph = data[i][sph_avg_index - 1];
            y_forcing.monthly_forcings[m].m_sw_rad = data[i][swdown_avg_index - 1];
            y_forcing.monthly_forcings[m].m_lw_rad_mean = data[i][lwdown_avg_index - 1];
            y_forcing.monthly_forcings[m].m_wind  = data[i][wind_avg_index - 1];
            i++;
        }
        yearly_forcings.push_back(y_forcing);
    }


    return yearly_forcings;

}
