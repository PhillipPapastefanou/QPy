import pandas as pd
import numpy as np
from enum import Enum
import jcalendar


class TimeUnit(Enum):
    Seconds = 1,
    Days = 2

class JulianDate:
    def __init__(self):
        self.year = 0
        self.month = 1
        self.day = 1
        self.hour = 0
        self.min = 0
        self.sec = 0

    def to_dict(self):
        return {
            'year': self.year,
            'month': self.month,
            'day': self.day,
            'hour': self.hour,
            'min': self.min,
            'sec': self.sec
        }
    def AddSeconds(self, seconds):

        SECONDS_IN_DAY = 86400
        ACC_DAYS_IN_MONTHS= [31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]
        SECONDS_IN_YEAR = 31536000

        total_Seconds = 0
        total_Seconds  += self.year * SECONDS_IN_YEAR

        seconds_left = seconds

        new_year = np.floor(seconds/SECONDS_IN_YEAR).astype(int)
        seconds_left -= new_year*SECONDS_IN_YEAR

        new_day = np.floor(seconds_left/SECONDS_IN_DAY).astype(int)
        seconds_left -= new_day * SECONDS_IN_DAY

        #To find the actual day of the month we have to add 1
        new_day +=1
        #new_day -= 1
        #nyears = int(sumdays / 365)
        #sum_days_rem = sumdays % 365 + 1

        for i in range(12):
            if ACC_DAYS_IN_MONTHS[i] >= new_day :
                new_month = i + 1

                if i != 0:
                    new_day -= ACC_DAYS_IN_MONTHS[i - 1]
                else:
                    new_day += 0
                break


        new_hours = np.floor(seconds_left/60/60).astype(int)
        seconds_left -= 60*60*new_hours

        new_min = np.floor(seconds_left/60).astype(int)
        seconds_left -= 60*new_min

        new_seconds = seconds_left.astype(int)

        jd = JulianDate()
        jd.year = new_year
        jd.month = new_month
        jd.day = new_day
        jd.hour = new_hours
        jd.min = new_min
        jd.sec = new_seconds

        return jd

        print(seconds_left)


class JulianCalendarParse:

    def __init__(self):
        x = 0

    def GetStartDateFromNetCDFUnitString(self, string):
        timeStringData = str.split(string, ' since ')
        timeTokenStr = timeStringData[0]

        if timeTokenStr == 'seconds':
            self.time_unit = TimeUnit.Seconds
        else:
            print(f"Unsuported time unit: {timeTokenStr}")
            exit(-1)

        beginDateStr = timeStringData[1]
        beginDateData = str.split(beginDateStr, ' ')

        year_month_day_string = beginDateData[0]
        clockstring = beginDateData[1]

        year_month_day_arr = str.split(year_month_day_string, '-')

        year = int(year_month_day_arr[0])
        month = int(year_month_day_arr[1])
        day = int(year_month_day_arr[2])

        clockstring_list = str.split(clockstring, ':')

        ## We have a time without seconds, e.g. 08:45
        if len(clockstring_list) == 2:
            hour = int(clockstring_list[0])
            min = int(clockstring_list[1])
            sec = 0
        elif(len(clockstring_list)==3):
            hour = int(clockstring_list[0])
            min = int(clockstring_list[1])
            sec = int(clockstring_list[2])
        else:
            print(f"Unsupported clock time: {clockstring}")
            exit(-1)

        self.DateOffset = JulianDate()
        self.DateOffset.year = year
        self.DateOffset.month = month
        self.DateOffset.day = day
        self.DateOffset.hour = hour
        self.DateOffset.min = min
        self.DateOffset.sec = sec

    def ParseDates(self, time_offsets):

        jds = []
        for time_offset in time_offsets:
            jds.append(self.DateOffset.AddSeconds(time_offset))
        return pd.DataFrame.from_records([s.to_dict() for s in jds])

    def ParseDatesC(self, times_offsets):
        jdc  = jcalendar.GetJulianDates(self.DateOffset.year,
                                        self.DateOffset.month,
                                        self.DateOffset.day,
                                        self.DateOffset.hour,
                                        self.DateOffset.min,
                                        self.DateOffset.sec,
                                        times_offsets)

        jds = [0] * times_offsets.shape[0]
        for i in range(0, len(jds)):
            jds[i] = [jdc[i].year,
                      jdc[i].month,
                      jdc[i].day,
                      jdc[i].hour,
                      jdc[i].min,
                      jdc[i].sec,
                      jdc[i].day_of_year
                      ]
        return pd.DataFrame(jds, columns=['year', 'month', 'day', 'hour', 'min', 'sec', 'day_of_year'])









