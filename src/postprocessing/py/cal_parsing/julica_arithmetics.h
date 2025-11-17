//
// Created by Phillip on 18.01.23.
//

#ifndef CALCULATOR_JULICA_ARITHMETICS_H
#define CALCULATOR_JULICA_ARITHMETICS_H


class JulianDate {

public:
    JulianDate();
    JulianDate(int year, int month, int day, int hour, int min, int sec);
    JulianDate AddSeconds( long long seconds);

    int year;
    int month;
    int day;
    int hour;
    int min;
    int sec;

    double day_in_year;

private:

    static constexpr long SECONDS_IN_DAY = 86400;
    static constexpr long ACC_DAYS_IN_MONTH[12] = {31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365};
    static constexpr long DAYS_IN_MONTH[12] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    static constexpr long SECCONDS_IN_YEAR = 31536000;



};


#endif //CALCULATOR_JULICA_ARITHMETICS_H
