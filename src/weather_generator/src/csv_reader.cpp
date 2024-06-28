//
// Created by Phillip on 11.07.23.
//
#include "csv_reader.h"
#include <sstream>
#include <iostream>
#include <memory>


io::CSV_Reader::CSV_Reader(string filename, bool has_header, char delimiter) {

    this->filename = filename;
    this->delimiter = delimiter;
    this->has_header = has_header;
    vector<vector<string> > data;
    vector<string> row;
    string line, word;


    std::fstream file(filename,  std::ios::in);

    if(file.is_open()){
        if(has_header){
            getline(file, line);
            std::stringstream str(line);
            while(getline(str, word, delimiter))
                header.push_back(word);
        }

    }
    else{
        std::cout<<"Could not open the file ";
        std::cout<<filename << std::endl;
        exit(99);
    }

    if(file.is_open()){
        file.close();
    }


}

io::CSV_Reader::~CSV_Reader() {

}

int io::CSV_Reader::GetColumnID(std::string column_header) {
    int dist = std::distance(header.begin(),std::find(header.begin(), header.end(), column_header));
    if (dist == header.size()){
        std::cout << "Could not find " << column_header << " in columns" << std::endl;
        exit(99);
        return -1;
    }
    return dist;
}



