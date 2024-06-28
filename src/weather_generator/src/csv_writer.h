//
// Created by Phillip on 10.06.24.
//

#pragma once
#include <fstream>
#include <string>
#include "vars.h"
#include "gridcell.h"

class CSV_Writer {

    public:
        CSV_Writer(std::string filename, Gridcell gridcell);
        void Export(std::vector<Sudaily_Forcing> forcing);


    private:
        std::string filename;
        int min_year;

};

