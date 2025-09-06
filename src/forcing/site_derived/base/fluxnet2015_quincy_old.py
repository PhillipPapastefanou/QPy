import numpy as np
import pandas as pd
import string
import netCDF4
import os


class Fluxnet2015_Quincy_old:

    def __init__(self, rtpath, sitename):
        self.rtpath = rtpath
        self.sitename = sitename

        files = os.listdir(rtpath)
        found_q = [sitename in files[i] for i in range(0, len(files))]
        positions = np.where(found_q)[0]

        if len(positions) == 1:
            self.found = True
            self.fname = files[positions[0]]
            self.fname_path = f"{rtpath}/{self.fname}"
        else:
            self.found = False

    def connect_to_remote(self, sftp):
        self.fname_path = sftp.open(self.fname_path)
        raise Exception("Could not conenct to remote connection")


    def Read_variables(self, variables):

        if self.found:
            ds = netCDF4.Dataset(self.fname_path)

            time_var = ds.variables['time']

            seps = [str.split(str(time_var[i]), ".") for i in range(0, time_var.shape[0])]

            times = [
                pd.to_datetime(seps[i][0], format='%Y%m%d') + pd.to_timedelta(np.single('0.' + seps[i][1]), unit='d')
                for i in range(0, time_var.shape[0])]

            self.units = []

            self.df = pd.DataFrame()
            self.df['date'] = times
            self.df['date'] = pd.to_datetime(self.df['date'])
            for var in variables:
                self.df[var] = ds.variables[var][:, 0, 0]
                self.units.append(ds.variables[var].units)

            self.df.set_index('date')


            ds.close()