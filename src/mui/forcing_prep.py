import xarray as xr
import numpy as np
import pandas as pd
from math import floor
import subprocess
from src.forcing.quinct_input_generator import QuincyInputGenerator
from src.forcing.misc_forcing_settings import ProjectionScenario
from src.mui.ui_settings import Ui_Settings
from src.mui.var_types import ForcingDataset
import os
class ForcingSlicer:
    def __init__(self, root_path):

        self.vars = ["pre", "pres", "spfh", 'tmin', 'tmax', 'tmp', 'tswrf', 'wetdays', 'wind', 'dlwrf']
        self.root_path = root_path
        self.var_dummy = self.vars[0]

        ds = xr.open_dataset(os.path.join(self.root_path,f"kmcrujra.v2.4.5d.{self.var_dummy}.1981-2022.365d.nc"))

        self.lons = ds['lon'].to_numpy()
        self.lats = ds['lat'].to_numpy()

        self.forc_dataset = ForcingDataset()

        self.forc_dataset.min_lon = self.lons.min()
        self.forc_dataset.max_lon = self.lons.max()
        self.forc_dataset.min_lat = self.lats.min()
        self.forc_dataset.max_lat = self.lats.max()

        res_lon = self.lons[1] - self.lons[0]
        res_lat = self.lats[1] - self.lats[0]

        if res_lon != res_lat:
            print(f"Lon dimension ({res_lon})) and lat dimension ({res_lat}) do not match")
            exit(99)
        self.forc_dataset.res = res_lon

        offset_lat = self.forc_dataset.min_lat - np.floor(self.forc_dataset.min_lat)
        offset_lon = self.forc_dataset.min_lon - np.floor(self.forc_dataset.min_lon)

        if offset_lon != offset_lat:
            print(f"Lon offset ({offset_lon})) and lat offset ({offset_lat}) do not match")
            exit(99)
        self.forc_dataset.offset = offset_lat
        ds.close()


    def get_temp_prec_slice(self, lon, lat):
        vars = ["pre", 'tmp']
        dsi = {}
        for var in vars:
            dsi[var] =  xr.open_dataset(os.path.join(self.root_path,f"kmcrujra.v2.4.5d.{var}.1981-2022.365d.nc"))

        lon_index = self.find_nearest_index(self.lons, lon)
        lat_index = self.find_nearest_index(self.lats, lat)

        df = pd.DataFrame()
        for var in vars:
            df[var] = dsi[var][var][lon_index, lat_index].values

        df["datetime"] = pd.to_datetime("1981-01-01")
        df["months"] = np.arange(0, df.shape[0])
        df["datetime"] = self.vadd_months(df["datetime"], df['months']);
        df["datetime"] = pd.to_datetime(df["datetime"]);
        df.drop(columns=['months'], inplace=True);
        df.set_index('datetime', inplace=True);
        return df

    def get_other_forcing(self, lon, lat):
        vars = ["pres", "spfh", 'tmin', 'tmax', 'tswrf', 'wetdays', 'wind', 'dlwrf']
        dsi = {}
        for var in vars:
            dsi[var] = xr.open_dataset(os.path.join(self.root_path,f"kmcrujra.v2.4.5d.{var}.1981-2022.365d.nc"))

        lon_index = self.find_nearest_index(self.lons, lon)
        lat_index = self.find_nearest_index(self.lats, lat)

        df = pd.DataFrame()
        for var in vars:
            df[var] = dsi[var][var][lon_index, lat_index].values

        df["datetime"] = pd.to_datetime("1981-01-01")
        df["months"] = np.arange(0, df.shape[0])
        df["datetime"] = self.vadd_months(df["datetime"], df['months']);
        df["datetime"] = pd.to_datetime(df["datetime"]);
        df.drop(columns=['months'], inplace=True);
        df.set_index('datetime', inplace=True);
        return df

    def vadd_months(self, dates, months):
        ddt = dates.dt
        m = ddt.month - 1 + months
        mb = pd.to_datetime(pd.DataFrame({
            'year': ddt.year + m // 12,
            'month': (m % 12) + 1,
            'day': 1})) + (dates - dates.dt.normalize())
        me = mb + pd.offsets.MonthEnd()
        r = mb + (ddt.day - 1) * pd.Timedelta(days=1)
        r = np.minimum(r, me)
        return r
    def find_nearest_index(self, array, value):
        array = np.asarray(array)
        idx = (np.abs(array - value)).argmin()
        return idx


class ForcingGenerator:

    def __init__(self, settings : Ui_Settings):
        self.ui_settings = settings

    def generate_subdaily_forcing(self, output_path):

        gen_path  = self.ui_settings.binary_weather_generator
        input_forcing = os.path.join(output_path, self.ui_settings.monthly_forcing_fname)
        input_settings = os.path.join(output_path,self.ui_settings.site_settings_fname)
        output_filname = os.path.join(output_path,self.ui_settings.subdaily_forcing_fname)
        subprocess.run(f"{gen_path} {input_forcing} {input_settings} {output_filname}", shell=True)

    def generate_additional_quincy_forcing(self, lon, lat, output_path):

        subdaily_filname = os.path.join(output_path,self.ui_settings.subdaily_forcing_fname)
        forcing_generator = QuincyInputGenerator(self.ui_settings.misc_input)
        forcing_generator.generate(lon=lon, lat=lat, forcing_file=subdaily_filname)
        forcing_generator.Export_static_forcing(os.path.join(output_path,self.ui_settings.quincy_forcing_fname))



