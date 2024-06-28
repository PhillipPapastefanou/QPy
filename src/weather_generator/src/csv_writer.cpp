//
// Created by Phillip on 10.06.24.
//

#include "csv_writer.h"
#include <iostream>

CSV_Writer::CSV_Writer(std::string filename, Gridcell gridcell): filename(filename), min_year(gridcell.min_year){

}

void CSV_Writer::Export(std::vector<Sudaily_Forcing> forcing) {

    std::ofstream myfile;
    myfile.open (filename);
    myfile << "year day hour ";
    myfile << "swvis_srf_down lw_srf_down t_air ";
    myfile << "q_air press_srf rain snow wind_air\n";
    myfile << "- - - ";
    myfile << "W/m2 W/m2 K";
    myfile << "g/kg hPa mm/day mm/day m/s\n";

    for (int d = 0; d < forcing.size(); ++d) {

        Sudaily_Forcing& sdf = forcing[d];

        for (int h = 0; h < 48; ++h) {
            myfile << min_year + sdf.year << " ";
            myfile << sdf.day_of_year + 1 << " ";
            myfile << h * 0.5 << " ";
            myfile << sdf.sd_sw_rad[h] << " ";
            myfile << sdf.sd_lw_rad[h] << " ";
            myfile << sdf.sd_temp[h] << " ";
            myfile << sdf.sd_sph[h] * 1000.0 << " ";
            myfile << sdf.sd_pressure[h] / 100.0 << " ";
            myfile << sdf.sd_rain[h] << " ";
            myfile << 0.0 << " ";
            myfile << sdf.sd_wind[h] << "\n";
        }

    }

    myfile.close();

}
