//
// Created by Phillip on 21.06.24.
//

#include "gridcell_setting_reader.h"

GridcellSettingReader::GridcellSettingReader(std::string filename): reader(filename, true, ','){

}

Gridcell GridcellSettingReader::ParseInput() {



    std::vector<std::string> header_str = reader.header;

    std::vector<int> indexes(4);
    for (int i = 0; i < 4; ++i) {
        indexes[i] = i;
    }

    std::vector<std::vector<std::string> > data = reader.Get<std::string>(indexes);

    int lon_index = reader.GetColumnID("lon");
    int lat_index = reader.GetColumnID("lat");
    int min_year_index = reader.GetColumnID("min_year");
    int max_year_index = reader.GetColumnID("max_year");


    Gridcell gridcell;
    gridcell.lon = std::stod(data[0][lon_index]);
    gridcell.lat = std::stod(data[0][lat_index]);
    gridcell.min_year = std::stoi(data[0][min_year_index]);
    gridcell.max_year = std::stoi(data[0][max_year_index]);

    return gridcell;
}
