
from time import perf_counter
from src.forcing.misc_forcing_settings import Misc_Forcing_Settings
from src.forcing.misc_forcing_settings import Verbosity
from src.forcing.misc_forcing_settings import ProjectionScenario
import numpy as np
import pandas as pd

from src.forcing.gridded_input import NdepositionForcing
from src.forcing.gridded_input import PdepositionForcing


class QuincyInputGenerator:
    def __init__(self, settings : Misc_Forcing_Settings):

        self.quincy_full_forcing_columns = ['year','doy','hour','swvis_srf_down','lw_srf_down','t_air','q_air','press_srf',
             'rain','snow','wind_air','co2_mixing_ratio','co2_dC13','co2DC14','nhx_srf_down','noy_srf_down','p_srf_down']

        # Unit row according to QUINCY forcing
        self.quincy_unit_row = ['-', '-', '-', 'Wm-2', 'Wm-2', 'K', 'g/kg', 'hPa', 'mm/day', 'mm/day', 'm/s', 'ppm', 'per-mill', 'per-mill', 'mg/m2/day', 'mg/m2/day', 'mg/m2/day']

        self.settings = settings
    def generate(self, lon, lat, forcing_file):

        self.DataFrame = pd.read_csv(forcing_file, sep='\s+', index_col=None, skiprows=[1])

        self.DataFrame.rename(columns={'day': 'doy'}, inplace=True)

        # Removing too low wind values to avoid model instabilities
        self.DataFrame.loc[self.DataFrame['wind_air'] < 0.1, 'wind_air'] = 0.1

        self.year_min = np.min(self.DataFrame['year'])
        self.year_max = np.max(self.DataFrame['year'])

        # Parse CO2 forcing
        self.dprint("Parsing CO2..", lambda: self._parse_co2_forcing())

        # Parse dC13 and DC14
        self.dprint("Parsing dCO2-13 and 14..", lambda: self._parse_dC13_and_DC14(lon, lat))

        # Parse phosphorus deposition
        self.dprint("Parsing P deposition..", lambda: self._parse_p_depositions(lon, lat))

        # Parse nitrogen deposition
        self.dprint("Parsing N deposition..",
                    lambda: self._parse_n_deposition(lon, lat, self.year_min, self.year_max))

        # Testing for Nan
        self.dprint("Testing for missing values..", lambda: self._testing_for_nan())
    def Export_static_forcing(self, filename):
        # Exporting QUINCY file
        self.dprint("Exporting static forcing data..", lambda:self._export_static(filename))
    def _parse_co2_forcing(self):
        # Parse main CO2
        df_co2 = pd.read_csv(self.settings.co2_concentration_file, sep='\s+', header=None)
        df_co2.columns = ['year', 'co2_mixing_ratio']
        self.DataFrame = pd.merge(self.DataFrame, df_co2, on='year')

    def _parse_dC13_and_DC14(self, lon, lat):
        df_co2_dC13 = pd.read_csv(self.settings.co2_dC13_file,
                                  sep='\s+', header=None)

        df_co2_dC13.columns = ['year', 'co2_dC13']
        df_co2_dC13['year'] = df_co2_dC13['year'] - 0.5
        df_co2_dC13['year'] = df_co2_dC13['year'].astype(int)
        self.DataFrame = pd.merge(self.DataFrame, df_co2_dC13, on='year')

        # Parse DC14
        df_co2_DC14 = pd.read_csv(self.settings.co2_DC14_file,
                                  sep='\s+', header=None)
        df_co2_DC14.columns = ['year', '1', '2', '3']
        df_co2_DC14['year'] = df_co2_DC14['year'] - 0.5
        df_co2_DC14['year'] = df_co2_DC14['year'].astype(int)

        if lat > 30.0:
            c14_index = 1
        elif (lat > -30.0) & (lat <= 30.0):
            c14_index = 2
        elif lat <= -30.0:
            c14_index = 3
        else:
            print("This should not happen")
            exit(99)

        df_c14_slice = df_co2_DC14[['year', str(c14_index)]]
        df_c14_slice = df_c14_slice.rename(columns={str(c14_index): 'co2DC14'})
        self.DataFrame = pd.merge(self.DataFrame, df_c14_slice, on='year')

    def _parse_p_depositions(self, lon, lat):
        rt_path_p = self.settings.root_pdep_path
        p_dep_forcing = PdepositionForcing(root_path=rt_path_p, verbosity_level= self.settings.verbosity)
        p_dep_forcing.extract(lon, lat)
        self.DataFrame["p_srf_down"] = p_dep_forcing.p_dep

    def _parse_n_deposition(self, lon, lat, year_min, year_max):
        rt_path_n = self.settings.root_ndep_path
        n_dep_forcing = NdepositionForcing(root_path=rt_path_n, projection_scenario=self.settings.ndep_projection_scenario, verbosity_level= self.settings.verbosity)
        n_dep_forcing.extract(lon=lon, lat=lat, year_min=year_min, year_max=year_max)
        self.DataFrame = pd.merge(self.DataFrame, n_dep_forcing.Data.copy(), on=['year', 'doy'])
        self.DataFrame = self.DataFrame.rename(columns={'nhx': 'nhx_srf_down', 'noy': 'noy_srf_down'})

    def _export_static(self, filename):
        df_export = self.DataFrame.copy()

        # Round values according to 4 significant figures
        # for var in self.quincy_full_forcing_columns:
        #     df_export[var] = round(df_export[var], 4)
        #     df_export[var] = df_export[var].apply(pd.to_numeric, downcast='float').fillna(0)

        # Make sure that columns are sorted according to QUINCY's needs
        df_export = df_export[self.quincy_full_forcing_columns]

        # Insert first unit row
        df_export.loc[-1] = self.quincy_unit_row
        df_export.index = df_export.index + 1
        df_export = df_export.sort_index()

        rt_output_folder = self.settings.root_output_path
        static_folder = f"{rt_output_folder}/{self.settings.static_forcing_folder_name}"

        # Export file acccording to QUINCY standards
        df_export.to_csv(filename, header=True, sep=" ", index=None)

    def dprint(self, text , f: callable):
        if (self.settings.verbosity == Verbosity.Info) | (self.settings.verbosity == Verbosity.Full):
            print(text, end="")
            t1 = perf_counter()
        f()
        if (self.settings.verbosity == Verbosity.Info) | (self.settings.verbosity == Verbosity.Full):
            t2 = perf_counter()
            print(f"Done! ({np.round(t2 - t1, 1)} sec.)")

    def _testing_for_nan(self):
        nan_rows = self.DataFrame[self.DataFrame.isna().any(axis=1)].shape[0]
        if nan_rows > 0:
            raise Exception(f"Error: Found {nan_rows} rows with nan values. Skipping location...")

        self.DataFrame['year'] = self.DataFrame['year'].astype(int)
        self.DataFrame['doy'] = self.DataFrame['doy'].astype(int)