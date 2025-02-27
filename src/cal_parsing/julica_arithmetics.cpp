//
// Created by Phillip on 18.01.23.
//

#include "julica_arithmetics.h"

JulianDate::JulianDate(int year, int month, int day, int hour, int min, int sec) :
year(year), month(month), day(day), hour(hour), min(min), sec(sec)

{
    //Todo check for a valid configuration
    day_in_year  = day - 1;
    if (month > 1){
        day_in_year  += ACC_DAYS_IN_MONTH[month - 2];
    }
    day_in_year += static_cast<double>(hour*3600 + min*60 + sec)/SECONDS_IN_DAY;
}

JulianDate JulianDate::AddSeconds(long long  seconds) {


    long long seconds_now = year * SECCONDS_IN_YEAR;

    if(month > 1){
        seconds_now += ACC_DAYS_IN_MONTH[month - 2] * SECONDS_IN_DAY;
    }
    seconds_now += (day - 1)*SECONDS_IN_DAY;
    seconds_now += hour * 3600;
    seconds_now += min *60;
    seconds_now += sec;

    long long seconds_left = seconds + seconds_now;

    int new_year = seconds_left/SECCONDS_IN_YEAR;
    seconds_left -= new_year * SECCONDS_IN_YEAR;

    int new_day = seconds_left/SECONDS_IN_DAY;
    seconds_left -= new_day * SECONDS_IN_DAY;

    //To find the actual day of the month we have to add 1
    new_day ++;

    int new_month = 0;

    for (int i = 0; i < 12; ++i) {
        if(ACC_DAYS_IN_MONTH[i] >= new_day){
            new_month = i + 1;


            if(i != 0){
                new_day -= ACC_DAYS_IN_MONTH[i-1];
            }
            else {
                new_day; //Nothing to do here
            }
            break;
        }
    }


    int new_hours = seconds_left/60/60;
    seconds_left -= 60*60*new_hours;


    int new_min = seconds_left/60;
    seconds_left -= 60*new_min;

    int new_seconds = seconds_left;

    return JulianDate(new_year, new_month, new_day, new_hours, new_min, new_seconds);
}

JulianDate::JulianDate() :year(0), month(0), day(0), hour(0), min(0), sec(0) {

}
