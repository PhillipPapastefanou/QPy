//
// Created by Phillip on 10.06.24.
//
#pragma once
#include "csv_reader.h"
#include "vars.h"

using namespace io;

class ForcingReader {


public:
    ForcingReader(std::string filename);

    io::CSV_Reader reader;

    std::vector<Yearly_Forcing> ParseInput();

};