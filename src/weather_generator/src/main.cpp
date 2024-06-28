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

int main(int argc, char* argv[]) {

    std::string monthly_input_file;
    std::string input_setting_file;
    std::string output_file;


    if ( argc != 4) {
        std::cout<<"(1)input forcing, (2) input setting file, and (3) outputfile must be specified" << std::endl;
        return 99;
    }
    else {
            monthly_input_file = argv[1];
            input_setting_file = argv[2];
            output_file = argv[3];
        }

    // Get information to generate forcing for that particular gridcell
    GridcellSettingReader setting_reader(input_setting_file);
    Gridcell gridcell = setting_reader.ParseInput();

    ForcingReader reader(monthly_input_file);

    std::vector<Yearly_Forcing> forcing = reader.ParseInput();

    Simple_Daily_LPJ_Weather_Generator daily_generator = Simple_Daily_LPJ_Weather_Generator(gridcell);

    std::vector<Daily_Forcing> daily_forcing = daily_generator.Generate(forcing);

    Simple_Diurnal_Manon_Weather_Generator subdaily_generator = Simple_Diurnal_Manon_Weather_Generator(gridcell);

    std::vector<Sudaily_Forcing> subdaily_forcings  = subdaily_generator.Generate_subdaily_forcing(daily_forcing);

    CSV_Writer writer(output_file, gridcell);

    writer.Export(subdaily_forcings);


}
