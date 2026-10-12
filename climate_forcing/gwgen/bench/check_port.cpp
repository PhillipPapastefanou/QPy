// Compares the QUINCY cpp_port GWGEN (quincy/gwgen.hpp, with LPJ-GUESS year
// boundaries) against LPJ-GUESS modules/weathergen.cpp compiled unchanged
// against shim/guess.h, on the bench points. Every daily value must be
// bit-identical. Usage: check_port <points.csv>
#include "guess.h"
#include "weathergen.h"
#include "quincy/gwgen.hpp"
#include <array>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <map>
#include <string>
#include <vector>
using namespace std;
namespace gw = quincy::climate_forcing::gwgen;
constexpr double K2C = 273.15, WETDAY_INTENSITY = 5.0;
struct Pt { double lat, lon; vector<array<double, 5>> m; };  // tmin tmax prec_rate sw wind

int main(int argc, char** argv) {
  ifstream f(argv[1]);
  string line;
  getline(f, line);
  map<int, Pt> pts;
  int p, y, mo;
  double la, lo;
  array<double, 5> v;
  while (getline(f, line)) {
    if (sscanf(line.c_str(), "%d %lf %lf %d %d %lf %lf %lf %lf %lf", &p, &la, &lo, &y, &mo, &v[0], &v[1], &v[2],
               &v[3], &v[4]) != 10) {
      v[2] = NAN;
      sscanf(line.c_str(), "%d %lf %lf %d %d", &p, &la, &lo, &y, &mo);
    }
    auto& P = pts[p];
    P.lat = la;
    P.lon = lo;
    P.m.push_back(v);
  }
  const int ndm[12] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
  long n_cellyears = 0, n_skipped = 0, n_values = 0, n_mismatch = 0, n_points_bad = 0;
  double t_lpj = 0, t_port = 0, max_abs = 0;
  for (auto& [id, P] : pts) {
    bool bad = false;
    for (auto& r : P.m)
      for (double x : r)
        if (!isfinite(x)) bad = true;
    if (bad) {
      n_skipped++;
      continue;
    }
    Gridcell gc;
    gc.lat = P.lat;
    gc.lon = P.lon;
    gw::Options opt;
    opt.continuous_year_boundaries = false;
    gw::WeatherGenerator port(P.lat, P.lon, opt);
    bool point_bad = false;
    for (int yr = 0; yr < int(P.m.size() / 12); ++yr) {
      double mtemp[12], mprec[12], mwet[12], msol[12], mdtr[12], mwind[12], mrhum[12];
      gw::MonthlyInput in;
      for (int m = 0; m < 12; ++m) {
        auto& r = P.m[yr * 12 + m];
        const double tmin = r[0] - K2C, tmax = r[1] - K2C;
        mtemp[m] = in.tmean[m] = 0.5 * (tmin + tmax);
        mdtr[m] = in.dtr[m] = max(0.0, tmax - tmin);
        mprec[m] = in.prec[m] = max(0.0, r[2]) * ndm[m];
        mwet[m] = in.wet_days[m] = clamp(mprec[m] / WETDAY_INTENSITY, 1.0, double(ndm[m]));
        msol[m] = in.sw[m] = r[3];
        mwind[m] = in.wind[m] = max(0.1, r[4]);
        mrhum[m] = in.rhum[m] = -1;
      }
      double dtemp[366], dprec[366], dsol[366], ddtr[366], dwind[366], drh[366];
      date.year = yr;
      date.day = 0;
      auto t0 = chrono::steady_clock::now();
      weathergen_get_met(gc, mtemp, mprec, mwet, msol, mdtr, mwind, mrhum, dtemp, dprec, dsol, ddtr, dwind, drh);
      auto t1 = chrono::steady_clock::now();
      const gw::DailyOutput o = port.generate_year(in);
      auto t2 = chrono::steady_clock::now();
      t_lpj += chrono::duration<double>(t1 - t0).count();
      t_port += chrono::duration<double>(t2 - t1).count();
      n_cellyears++;
      const double* ref[6] = {dtemp, dprec, dsol, ddtr, dwind, drh};
      const double* got[6] = {o.tmean.data(), o.prec.data(), o.sw.data(), o.dtr.data(), o.wind.data(), o.rhum.data()};
      for (int k = 0; k < 6; ++k) {
        for (int d = 0; d < 365; ++d) {
          n_values++;
          if (memcmp(&ref[k][d], &got[k][d], sizeof(double)) != 0) {
            n_mismatch++;
            point_bad = true;
            max_abs = max(max_abs, fabs(ref[k][d] - got[k][d]));
          }
        }
      }
    }
    n_points_bad += point_bad;
  }
  printf("points used %zu (skipped %ld with NaN), cell-years %ld\n", pts.size() - n_skipped, n_skipped, n_cellyears);
  printf("daily values compared %ld, not bit-identical %ld (points affected %ld, max |diff| %.3g)\n", n_values,
         n_mismatch, n_points_bad, max_abs);
  printf("time per cell-year: LPJ-GUESS %.1f us, port %.1f us\n", 1e6 * t_lpj / n_cellyears,
         1e6 * t_port / n_cellyears);
  return n_mismatch == 0 ? 0 : 1;
}
