#include "guess.h"
#include "weathergen.h"
#include "m2d.cpp"   // pulls the current QUINCY port's internals into this TU
#include <chrono>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <vector>
using namespace std;
namespace qcf = quincy::climate_forcing;
constexpr double K2C = 273.15, WETDAY_INTENSITY = 5.0;
struct Pt { double lat, lon; vector<array<double,5>> m; };  // tmin tmax prec_rate sw wind

int main(int argc, char** argv) {
  ifstream f(argv[1]); string line; getline(f, line);
  map<int, Pt> pts;
  int p, y, mo; double la, lo; array<double,5> v;
  while (getline(f, line)) {
    if (sscanf(line.c_str(), "%d %lf %lf %d %d %lf %lf %lf %lf %lf", &p, &la, &lo, &y, &mo,
               &v[0], &v[1], &v[2], &v[3], &v[4]) != 10) { v[2] = NAN; sscanf(line.c_str(), "%d %lf %lf %d %d", &p, &la, &lo, &y, &mo); }
    auto& P = pts[p]; P.lat = la; P.lon = lo; P.m.push_back(v); }
  const int ndm[12] = {31,28,31,30,31,30,31,31,30,31,30,31};

  double t_gw = 0, t_simple = 0; long n_cellyears = 0, n_skipped = 0;
  double max_terr = 0, max_perr_rel = 0, max_swerr_rel = 0;
  long gw_wet = 0, simple_wet = 0, days = 0;
  double gw_tmax_dsd = 0, simple_tmax_dsd = 0; long n_months = 0;

  for (auto& [id, P] : pts) {
    bool bad = false; for (auto& r : P.m) for (double x : r) if (!isfinite(x)) bad = true;
    if (bad) { n_skipped++; continue; }
    int ny = P.m.size() / 12;
    Gridcell gc; gc.lat = P.lat; gc.lon = P.lon;
    mt19937 gen(42);
    for (int yr = 0; yr < ny; ++yr) {
      double mtemp[12], mprec[12], mwet[12], msol[12], mdtr[12], mwind[12], mrhum[12];
      array<double,12> tmin, tmax, ptot, wd;
      for (int m = 0; m < 12; ++m) {
        auto& r = P.m[yr*12+m];
        tmin[m] = r[0]-K2C; tmax[m] = r[1]-K2C;
        mtemp[m] = 0.5*(tmin[m]+tmax[m]); mdtr[m] = max(0.0, tmax[m]-tmin[m]);
        mprec[m] = ptot[m] = max(0.0, r[2]) * ndm[m];
        mwet[m] = wd[m] = clamp(ptot[m]/WETDAY_INTENSITY, 1.0, double(ndm[m]));
        msol[m] = r[3]; mwind[m] = max(0.1, r[4]); mrhum[m] = -1;
      }
      double dtemp[366], dprec[366], dsol[366], ddtr[366], dwind[366], drh[366];
      date.year = yr; date.day = 0;
      auto t0 = chrono::steady_clock::now();
      weathergen_get_met(gc, mtemp, mprec, mwet, msol, mdtr, mwind, mrhum, dtemp, dprec, dsol, ddtr, dwind, drh);
      auto t1 = chrono::steady_clock::now();
      auto s_tmin = qcf::interp_monthly_means_conserve(tmin);
      auto s_tmax = qcf::interp_monthly_means_conserve(tmax);
      array<double,12> sw, wnd; for (int m=0;m<12;++m){sw[m]=msol[m];wnd[m]=mwind[m];}
      auto s_sw = qcf::interp_monthly_means_conserve(sw, 0.0);
      auto s_w = qcf::interp_monthly_means_conserve(wnd, 0.0);
      auto s_p = qcf::rain_daily(ptot, wd, gen);
      auto t2 = chrono::steady_clock::now();
      t_gw += chrono::duration<double>(t1-t0).count(); t_simple += chrono::duration<double>(t2-t1).count();
      n_cellyears++;
      // monthly conservation + daily variability stats
      int d0 = 0;
      for (int m = 0; m < 12; ++m) {
        double st = 0, sp = 0, ss = 0, sx = 0, sxx = 0, qx = 0, qxx = 0;
        for (int d = d0; d < d0+ndm[m]; ++d) {
          double tx = dtemp[d] + 0.5*ddtr[d];
          st += dtemp[d]; sp += dprec[d]; ss += dsol[d]; sx += tx; sxx += tx*tx;
          qx += s_tmax[d]; qxx += s_tmax[d]*s_tmax[d];
          gw_wet += dprec[d] > 0.1; simple_wet += s_p[d] > 0.1; days++;
        }
        int n = ndm[m];
        max_terr = max(max_terr, fabs(st/n - mtemp[m]));
        if (mprec[m] > 1) max_perr_rel = max(max_perr_rel, fabs(sp - mprec[m]) / mprec[m]);
        if (msol[m] > 5) max_swerr_rel = max(max_swerr_rel, fabs(ss/n - msol[m]) / msol[m]);
        gw_tmax_dsd += sqrt(max(0.0, sxx/n - (sx/n)*(sx/n)));
        simple_tmax_dsd += sqrt(max(0.0, qxx/n - (qx/n)*(qx/n)));
        n_months++; d0 += n;
      }
    }
  }
  printf("points used %zu (skipped %ld with NaN), cell-years %ld\n", pts.size()-n_skipped, n_skipped, n_cellyears);
  printf("GWGEN : %.3f s total, %.1f us per cell-year\n", t_gw, 1e6*t_gw/n_cellyears);
  printf("simple: %.3f s total, %.1f us per cell-year  (GWGEN/simple = %.1fx)\n", t_simple, 1e6*t_simple/n_cellyears, t_gw/t_simple);
  printf("GWGEN conservation: max |Tmean err| %.3g K, max rel precip err %.3g, max rel SW err %.3g\n", max_terr, max_perr_rel, max_swerr_rel);
  printf("wet-day fraction (>0.1mm): GWGEN %.3f, simple %.3f\n", double(gw_wet)/days, double(simple_wet)/days);
  printf("mean within-month SD of daily Tmax: GWGEN %.2f K, simple %.2f K\n", gw_tmax_dsd/n_months, simple_tmax_dsd/n_months);
}
