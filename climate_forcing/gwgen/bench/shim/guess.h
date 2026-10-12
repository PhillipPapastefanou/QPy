// Minimal stand-in for the LPJ-GUESS framework, just enough for weathergen.cpp.
#pragma once
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <algorithm>
#include <stdexcept>
using std::min; using std::max;
struct Date { int day = 0, year = 0; int ndaymonth[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
              int year_length() const { return 365; } };
inline Date date;
inline bool restart = false;
inline int state_year = 0;
inline void fail(const char* fmt, ...) { throw std::runtime_error(fmt); }
inline double roundoff(double dval, int limit) {
  bool neg = dval < 0; int ival = int((std::fabs(dval) * std::pow(10.0, limit)) + 0.5);
  dval = double(ival) / std::pow(10.0, limit); return neg ? -dval : dval; }
class WeatherGenState { public:
  int q[10] = {}; int carry = 0; int xcng = 0; unsigned int xs = 0; int indx = 0; bool have = false;
  double gamma_vals[2] = {}; bool pday[2] = {}; double resid[4] = {}; };
struct Climate { WeatherGenState weathergenstate; };
struct Gridcell { double lat = 0, lon = 0; Climate climate;
  double get_lat() const { return lat; } double get_lon() const { return lon; } };
