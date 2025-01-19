import pandas as pd
import numpy as np
import datetime
from enum import Enum


class TimeUnit(Enum):
    Seconds = 1,
    Days = 2

class JulianDate:
    def __init__(self):
        self.year = 0
        self.month = 1
        self.day = 1
        self.hour = 0
        self.minute = 0
        self.sec = 0

    def to_dict(self):
        return {
            'year': self.year,
            'month': self.month,
            'day': self.day,
            'hour': self.hour,
            'min': self.minute,
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
        jd.minute = new_min
        jd.sec = new_seconds

        return jd

        print(seconds_left)


class JulianCalendarParser:

    def __init__(self, output_time_res, output_identifier):
        self.output_time_res = output_time_res
        self.output_identifier = output_identifier

    def getStartDateFromNetCDFUnitString(self, date_string):
        timeStringData = str.split(date_string, ' since ')
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
            minute = int(clockstring_list[1])
            sec = 0
        elif(len(clockstring_list) == 3):
            hour = int(clockstring_list[0])
            minute = int(clockstring_list[1])
            sec = int(clockstring_list[2])
        else:
            print(f"Unsupported clock time: {clockstring}")
            exit(-1)


        self.DateOffset = JulianDate()
        self.DateOffset.year = year
        self.DateOffset.month = month
        self.DateOffset.day = day
        self.DateOffset.hour = hour
        self.DateOffset.minute = minute
        self.DateOffset.sec = sec
        self.DateOffsetString = f"{str(year).zfill(4)}-{str(month).zfill(2)}-{str(day).zfill(2)} {str(hour).zfill(2)}:{str(minute).zfill(2)}:{str(sec).zfill(2)}"


    def ParseDates(self, time_calendar_string, time_offsets):

        self.getStartDateFromNetCDFUnitString(time_calendar_string)

        self.IsDateTimePandas = False
        self.IsDateTimeNumpy = False
        self.IsDateTimeInteger = False

        # If we have no time data return empty dataframe
        if time_offsets.shape[0] == 0:
            return pd.DataFrame()

        if self.time_unit == TimeUnit.Seconds:
            dt_offset = datetime.datetime.fromisoformat(self.DateOffsetString)
            time_deltas = pd.to_timedelta(np.array(time_offsets, dtype='timedelta64[s]'))
            time_diff_beginning = time_deltas[1]-time_deltas[0]


            # Check if we daily or subdaily resolution
            # Because than we have to take leap years into account and ignore the 29 of feb
            if time_diff_beginning.days <= 1:
                time_diffs_all = np.diff(time_deltas)
                time_series = []
                current_time = dt_offset
                time_series.append(current_time)
                for diff in time_diffs_all:
                    next_time = current_time + datetime.timedelta(seconds= (diff/np.timedelta64(1, 's') ))

                    if next_time.month == 2 and next_time.day == 29:
                        next_time = next_time.replace(month=3, day=1)

                    time_series.append(next_time)
                    current_time = next_time
                iso_dates = np.array(time_series)

            # For monthly or yearly resolution this does not matter
            else:
                iso_dates = dt_offset + time_deltas


            # Check if we can use pandas
            if (iso_dates[0].year > pd.Timestamp.min.year + 1) & (iso_dates[-1].year < pd.Timestamp.max.year - 1):
                self.IsDateTimePandas = True
                return pd.DataFrame({'date': pd.to_datetime(iso_dates)})

            # Matplotlib only takes dates between 1 and 9999
            if iso_dates[0].year > 0:
                self.IsDateTimeNumpy = True
                return pd.DataFrame({'date': iso_dates})

            # if you are ouside of that range we will only pass the years as integer array:
            else:
                self.IsDateTimeInteger = True
                years = np.arange(iso_dates[0].year, iso_dates[0].year + time_offsets.shape[0])
                return pd.DataFrame({'date': years})


        else:
            print("The NetCDF time unit is not in second.")
            print("This routine currently only supports seconds, e.g. seconds since 1998-01-23")
            exit(-1)











        # DO we even need this
        # try:
        #     import jcalendar
        #     print("Using C accelerated library")
        #     return self.parseDatesC(time_offsets)
        # except:
        #     print("Using the python library")
        # return self.parseDatesPy(time_offsets)


    def parseDatesPy(self, time_offsets):

        str0 = "1500-01-01"

        import datetime


        dates = [f"{str(y).zfill(4)}-01-01" for y in range(-10000, 1900)]
        julian_dates = [Time(d, format='iso', scale='utc') for d in dates]
        df = pd.DataFrame({'date': julian_dates})

        return df

        # jds = []
        # for time_offset in time_offsets:
        #     jds.append(self.DateOffset.AddSeconds(time_offset))
        # return pd.DataFrame.from_records([s.to_dict() for s in jds])

    def parseDatesC(self, times_offsets):

        import jcalendar
        jdc  = jcalendar.GetJulianDates(self.DateOffset.year,
                                        self.DateOffset.month,
                                        self.DateOffset.day,
                                        self.DateOffset.hour,
                                        self.DateOffset.minute,
                                        self.DateOffset.sec,
                                        times_offsets)

        jds = [0] * times_offsets.shape[0]
        for i in range(0, len(jds)):
            jds[i] = [jdc[i].year,
                      jdc[i].month,
                      jdc[i].day,
                      jdc[i].hour,
                      jdc[i].minute,
                      jdc[i].sec,
                      jdc[i].day_of_year
                      ]
        return pd.DataFrame(jds, columns=['year', 'month', 'day', 'hour', 'min', 'sec', 'day_of_year'])









