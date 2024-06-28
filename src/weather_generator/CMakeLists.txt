cmake_minimum_required(VERSION 3.12)

#set(CMAKE_C_COMPILER "gcc")
#set(CMAKE_CXX_COMPILER "g++")
#set(USE_PYBIND11 ON)
#set(PYTHON_EXECUTABLE /Users/pp/anaconda3/envs/PHS-post/bin/python)
#find_package(pybind11 CONFIG REQUIRED)
#message(STATUS "Found pybind11 v${pybind11_VERSION}: ${pybind11_INCLUDE_DIRS}")

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

project(weater_generator)

if(APPLE)
    message("Using Mac")
elseif (UNIX)
    link_libraries(stdc++fs)
    message("Using Unix")
else()
    message("Using Win")
endif()


set(CMAKE_MODULE_PATH ${PROJECT_SOURCE_DIR}/cmake ${CMAKE_MODULE_PATH})
add_subdirectory(src)
project(generator)
add_executable(generator ${sources} src/main.cpp)

project(generator_tests)
add_executable(generator_tests ${sources} tests/main_tests.cpp)

