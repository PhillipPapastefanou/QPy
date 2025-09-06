import numpy as np
import pandas as pd
import string
import netCDF4
import os

class Fluxnet2022_Jake:

    def __init__(self, rtpath, sitename):
        self.rtpath = rtpath
        self.sitename = sitename
        self.fname_path_meteo = f"{rtpath}/{sitename}_meteo.nc"
        self.fname_path_rs = f"{rtpath}/{sitename}_rs.nc"


    def connect_to_remote(self, sftp):
        try:
            sftp.get(self.fname_path_meteo, f"{self.sitename}_meteo.nc")
            #self.fname_path = sftp.open(self.fname_path)
            self.fname_path_meteo = f"{self.sitename}_meteo.nc"
            self.found = True
        except:
            self.found = False



    def Read_And_Parse_Time(self):
        ds = netCDF4.Dataset(self.fname_path_meteo)
        time_var = ds['time']
        nc4times = netCDF4.num2date(time_var[:], time_var.units, only_use_python_datetimes=True)
        pdtimes = [pd.to_datetime(np.datetime64(nc4times[i])) for i in range(0, time_var[:].shape[0])]

        self.Lon = ds['longitude'][0, 0]
        self.Lat = ds['latitude'][0, 0]

        self.units = {}
        self.df = pd.DataFrame()
        self.df['date'] = pdtimes
        self.df.set_index('date')

        self.Year_min = self.df['date'].dt.year.min()
        self.Year_max = self.df['date'].dt.year.max()


    def Read_forcing_variables(self, variables):
        ds = netCDF4.Dataset(self.fname_path_meteo)
        for var in variables:
            self.df[var] = ds[var][:, 0, 0]
            self.units[var] = ds[var].units
        ds.close()

    def clean(self):
        if os.path.exists(f"{self.sitename}_meteo.nc"):
            os.remove(f"{self.sitename}_meteo.nc")