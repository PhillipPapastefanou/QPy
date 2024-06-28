///////////////////////////////////////////////////////////////////////////////////////
/// \file weathergen.h
/// \brief Global Weather GENerator 
///
/// \author Lars Nieradzik
/// $Date: 2017-11-24 15:04:09 +0200 (Fri, 24 Nov 2017) $
///
///////////////////////////////////////////////////////////////////////////////////////
#ifndef WEATHERGEN_H
#define WEATHERGEN_H
#include <vector>

class WeatherGenState {

public:
    /// Random state variable q
    int q[10];
    /// Random state variable carry
    int carry;
    /// Random state variable xcng
    int xcng;
    /// Random state variable xs
    unsigned int xs;
    /// Random state variable indx
    int indx;
    /// Random state variable have
    bool have;
    /// Random state gamma
    double gamma_vals[2];
    /// Indicator for whether the recent two days were rein-days
    bool pday[2];
    /// Random state's residuals
    double resid[4];

    WeatherGenState() {
        for (int i = 0; i<10; i++) q[i] = 0;
        carry = 0;
        xcng = 0;
        xs = 0;
        indx = 0;
        have = false;
        for (int i = 0; i<2; i++) gamma_vals[i] = 0.0;
        for (int i = 0; i<2; i++) pday[i] = false;
        for (int i = 0; i<4; i++) resid[i] = 0.0;
    }
};




/// GWGen - Global Weather GENerator
/** 
 * A weathergenerator for the use with e.g. BLAZE when wind and/or rel. 
 * humidity is needed. 
 */
//void weathergen_get_met(Gridcell& gridcell, std::vector<double> in_mtemp, std::vector<double> in_mprec, std::vector<double> in_mwetd,
//                        std::vector<double> in_msol, std::vector<double> in_mdtr, std::vector<double> in_mwind, std::vector<double> in_mrhum,
//                        std::vector<double>& out_dtemp, std::vector<double>&  out_dprec, std::vector<double>&  out_dsol, std::vector<double>&  out_ddtr,
//                        std::vector<double>&  out_dwind, std::vector<double>&  out_drhum);
	
#endif
