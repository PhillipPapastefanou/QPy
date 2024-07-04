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
#include "../src/gridcell_setting_reader.h"
#include "../src/gridcell.h"

int main(int argc, char* argv[]) {


    std::string monthly_input_file = "/Users/pp/Documents/Repos/QPy/app/-60.25_-3.25/monthly_forcing.csv";
    std::string input_setting_file = "/Users/pp/Documents/Repos/QPy/app/-60.25_-3.25/site_data.csv";
    std::string  output_file = "/Users/pp/Documents/Repos/QPy/app/-60.25_-3.25/climate_pres.dat";

    Gridcell gridcell;
    gridcell.min_year = 1981;
    gridcell.max_year = 2022;
    gridcell.lon = -60.25;
    gridcell.lat = -3.25;

    // Get information to generate forcing for that particular gridcell
    GridcellSettingReader setting_reader(input_setting_file);
    //Gridcell gridcell = setting_reader.ParseInput();

    ForcingReader reader(monthly_input_file);

    std::vector<Yearly_Forcing> forcing = reader.ParseInput();

    double pu = 0.0;
    for (int i = 0; i < forcing.size(); ++i) {
        for (int j = 0; j < 12; ++j) {
            pu += forcing[i].monthly_forcings[0].m_rain;
        }

    }
    pu/= 42.0;

    Simple_Daily_LPJ_Weather_Generator daily_generator = Simple_Daily_LPJ_Weather_Generator(gridcell);

    std::vector<Daily_Forcing> daily_forcing = daily_generator.Generate(forcing);

    double p = 0.0;
    for (int i = 0; i < daily_forcing.size(); ++i) {

        p+= daily_forcing[i].d_rain;
    }
    p/= 42.0;



    Simple_Diurnal_Manon_Weather_Generator subdaily_generator = Simple_Diurnal_Manon_Weather_Generator(gridcell);

    std::vector<Sudaily_Forcing> subdaily_forcings  = subdaily_generator.Generate_subdaily_forcing(daily_forcing);

    double px= 0.0;
    for (int i = 0; i < subdaily_forcings.size(); ++i) {
        for (int j = 0; j < 48; ++j) {


            px += subdaily_forcings[i].sd_rain[j];}
        }

    px/= 42.0 * 48.0;
    std::cout << px << std::endl;
    CSV_Writer writer(output_file, gridcell);

    writer.Export(subdaily_forcings);

}
