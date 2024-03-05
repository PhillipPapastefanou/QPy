//
// Created by Phillip on 18.01.23.
//

#include "julica_arithmetics.h"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <cmath>
#include <random>
#include <vector>


namespace py = pybind11;
using std::vector;


vector<JulianDate> GetJulianDates(int year, int month, int day, int hour, int min, int sec, vector<long> offsets){
    vector<JulianDate> dates(offsets.size());
    JulianDate date_zero(year,month,day,hour,min,sec);

    for (int i = 0; i < offsets.size(); ++i) {
        dates[i] = date_zero.AddSeconds(offsets[i]);
    }

    return dates;
}
PYBIND11_MODULE(jcalendar, handle){
    py::class_<JulianDate>(handle, "JulianDate").
            def_readwrite("year", &JulianDate::year).
            def_readwrite("month", &JulianDate::month).
            def_readwrite("day", &JulianDate::day).
            def_readwrite("hour", &JulianDate::hour).
            def_readwrite("min", &JulianDate::min).
            def_readwrite("sec", &JulianDate::sec).
            def_readwrite("day_of_year", &JulianDate::day_in_year).
            def(py::init<>());

    handle.doc() = "Julian calendard arithmetics";
    handle.def("GetJulianDates", &GetJulianDates);
}

