#include <ctime>
#include <iostream>
#include <iomanip>
#include <string>
#include <sstream>
#include "../src/gridcell.h"
#include "../src/simple_daily_lpj.h"
#include "../src/forcing_reader.h"
#include "../src/vars.h"
#include "../src/simple_diurnal_manon.h"
#include "../src/csv_writer.h"

int main(int argc, char* argv[]) {


    std::string monthly_input_file = "/Users/pp/Documents/Repos/QPy/src/gui/generator/14.25_48.75/monhtly_forcing.csv";
    std::string input_setting_file = "/Users/pp/Documents/Repos/QPy/src/gui/generator/14.25_48.75/site_data.csv";
    std::string  output_file = "/Users/pp/Documents/Repos/QPy/src/gui/generator/14.25_48.75/climate_pre.dat";

    Gridcell gridcell;
    gridcell.min_year = 1981;
    gridcell.max_year = 2022;
    gridcell.lon = -23.1;
    gridcell.lat = 12.0;

    ForcingReader reader("/Users/pp/Documents/Repos/QPy/src/input/MonthlyForcing.csv");

    std::vector<Yearly_Forcing> forcing = reader.ParseInput();

    Simple_Daily_LPJ_Weather_Generator daily_generator = Simple_Daily_LPJ_Weather_Generator(gridcell);

    std::vector<Daily_Forcing> daily_forcing = daily_generator.Generate(forcing);

    Simple_Diurnal_Manon_Weather_Generator subdaily_generator = Simple_Diurnal_Manon_Weather_Generator(gridcell);

    std::vector<Sudaily_Forcing> subdaily_forcings  = subdaily_generator.Generate_subdaily_forcing(daily_forcing);

    CSV_Writer writer("climate.dat.temp", gridcell);

    writer.Export(subdaily_forcings);


}
