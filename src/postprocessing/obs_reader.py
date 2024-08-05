import pandas as pd
import xarray as xr
import numpy as np
from netCDF4 import Dataset,num2date
import itertools

class QNC_obs_reader:
    def __init__(self, output_path):
        self.output_path = output_path
        self.root_filname = "obs.nc"


    def parse_env_and_variables(self, pandas_time = False):

        if pandas_time == False:
            print("The obs parser can only be run with the pandas time format (ns).")
            exit(-1)

        self.file_obs = xr.open_dataset(self.output_path + self.root_filname, decode_times=True)
        self.file_obs = self.file_obs.squeeze(['longitude', 'latitude'])

    def check_variables(self, target_variables):

        self.vars_avail = self.file_obs.keys()
        grp_var_target_found = []


        for grp in target_variables:
            var_target_found = []
            for var in grp:
                if var in self.vars_avail:
                    var_target_found.append(True)
                else:
                    var_target_found.append(False)
                    print(f"Could not find {var}... in {self.root_filname}...Skipping!")
            grp_var_target_found.append(var_target_found)

        return grp_var_target_found




    def read_data(self, var_name):

        varnames = ['time']
        varnames.append(var_name)

        df = self.file_obs[varnames].to_dataframe().drop(columns= ['longitude','latitude'])

        # Remove leap years
        df = df.drop(df[(df.index.day == 29)&(df.index.month == 2)].index)

        df.index= pd.to_datetime(df.index + pd.to_timedelta(-1800.0, unit='s'))
        return df



