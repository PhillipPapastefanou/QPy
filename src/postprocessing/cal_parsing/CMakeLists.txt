cmake_minimum_required(VERSION 3.4)
project(jcalendar)

find_package(pybind11 CONFIG REQUIRED)
message(STATUS "Found pybind11 v${pybind11_VERSION}: ${pybind11_INCLUDE_DIRS}")

pybind11_add_module(jcalendar julian_date_parsing.cpp julica_arithmetics.h julica_arithmetics.cpp)


