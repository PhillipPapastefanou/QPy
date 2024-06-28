//
// Created by Phillip on 21.06.24.
//
#pragma once
#include "csv_reader.h"
#include "vars.h"
#include "gridcell.h"

using namespace io;

class GridcellSettingReader{

public:
    GridcellSettingReader(std::string filename);
    io::CSV_Reader reader;
    Gridcell ParseInput();
};

