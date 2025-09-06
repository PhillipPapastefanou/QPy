import pandas as pd
import numpy as np
import calendar
import os

# from lib.converter.Model_forcing_input import SW_Input_Parser
# from lib.converter.Model_forcing_input import LW_Input_Parser
# from lib.converter.Model_forcing_input import Tair_Input_Parser
# from lib.converter.Model_forcing_input import Precipitation_Input_Parser
# from lib.converter.Model_forcing_input import Qair_Input_Parser
# from lib.converter.Model_forcing_input import Pressure_Input_Parser
# from lib.converter.Model_forcing_input import Windspeed_Input_Parser

from src.forcing.site_derived.base.gridded_input import NdepositionForcing
from src.forcing.site_derived.base.gridded_input import PdepositionForcing

from src.forcing.site_derived.converter.settings import Settings, Verbosity
from src.forcing.site_derived.converter.base_parsing import Base_Parsing

class Quincy_ATTO_Forcing(Base_Parsing):
    def __init__(self, settings: Settings):

        Base_Parsing.__init__(self, settings = settings)

        # Fluxnet specific variable name according to QUINCY conventions
        self.quincy_fluxnet_columns = ['year', 'doy', 'hour', 'swvis_srf_down', 'lw_srf_down', 't_air', 'q_air', 'press_srf',
             'rain','snow','wind_air']

        self.quincy_full_forcing_columns = ['year','doy','hour','swvis_srf_down','lw_srf_down','t_air','q_air','press_srf',
             'rain','snow','wind_air','co2_mixing_ratio','co2_dC13','co2DC14','nhx_srf_down','noy_srf_down','p_srf_down']

        # Unit row according to QUINCY forcing
        self.quincy_unit_row = ['-', '-', '-', 'Wm-2', 'Wm-2', 'K', 'g/kg', 'hPa', 'mm/day', 'mm/day', 'm/s', 'ppm', 'per-mill', 'per-mill', 'mg/m2/day', 'mg/m2/day', 'mg/m2/day']
        
        
        self.vars_atto_df = ["TA", "Q", "LW_IN", 'SW_IN_PI_F',  'PA', 'WS', "P"]

    def Parse_forcing(self, lat, lon, forcing_file):

        # Retrieve longitude and latitude
        self.Lat = lat
        self.Lon = lon
        
        self.sitename = "ATTO"
        
        # Create main QUINCY forcing dataframe
        self.DataFrame = pd.DataFrame(columns = self.quincy_fluxnet_columns)
            
        df_raw = pd.read_csv(forcing_file)
        df_raw['datetime'] = pd.to_datetime(df_raw['datetime'])
        df_raw.set_index('datetime', inplace=True)

        self.year_min = df_raw.index.year[0]
        self.year_max = df_raw.index.year[-1]

        self.DataFrame['year']= df_raw.index.year
        self.DataFrame['doy'] = df_raw.index.dayofyear.values
        
        hour_dec = df_raw.index.hour + df_raw.index.minute / 60.0
        self.DataFrame['hour'] = hour_dec


        self.DataFrame['swvis_srf_down'] = df_raw['SW_IN_PI_F_filled'].values
        self.DataFrame['lw_srf_down'] = df_raw['LW_IN_filled'].values
        self.DataFrame['t_air'] = (df_raw['TA_filled'] + 273.15).values
        self.DataFrame['q_air'] = (df_raw['Q_filled'] * 1000.0).values
        self.DataFrame['press_srf'] = (df_raw['PA_filled'] * 10.0).values
        self.DataFrame['rain'] = (df_raw['P_filled'] * 48.0).values
        # Sofar we have no snow input
        self.DataFrame['snow'] = 0.0
        self.DataFrame['wind_air'] = df_raw['WS_filled'].values

        # Removing too low wind values to avoid model instabilities
        self.DataFrame.loc[self.DataFrame['wind_air'] < 0.1, 'wind_air'] = 0.1


        # # Parse CO2 forcing
        # self.dprint("Parsing CO2..", lambda: self._parse_co2_forcing())

        # # Parse dC13 and DC14
        # self.dprint("Parsing dCO2-13 and 14..", lambda:self._parse_dC13_and_DC14())

        # # Parse phosphorus deposition
        # self.dprint("Parsing P deposition..",lambda: self._parse_p_depositions())

        # # Parse nitrogen deposition
        # self.dprint("Parsing N deposition..", lambda:self._parse_n_deposition())

        # # Testing for Nan
        # self.dprint("Testing for missing values..", lambda: self._testing_for_nan())
        



    def Export_static_forcing(self):
        # Exporting QUINCY file
        self.dprint("Exporting static forcing data..", lambda:self._export_static())

    def Export_transient_forcing(self):
        # Exporting QUINCY file
        self.dprint("Exporting transient forcing data..", lambda: self._generate_and_export_transient_forcing())

    def _parse_co2_forcing(self):
        # Parse main CO2
        df_co2 = pd.read_csv(self.settings.co2_concentration_file, delim_whitespace=True, header=None)
        df_co2.columns = ['year', 'co2_mixing_ratio']
        self.DataFrame = pd.merge(self.DataFrame, df_co2, on='year')

    # def _parse_fluxnet_forcing(self, fnet):
    #     # Set up unit parser
    #     sw_parser = SW_Input_Parser(fnet.units['SWdown'])
    #     lw_parser = LW_Input_Parser(fnet.units['LWdown'])
    #     temp_parser = Tair_Input_Parser(fnet.units['Tair'])
    #     precip_parser = Precipitation_Input_Parser(fnet.units['Precip'])
    #     qair_parser = Qair_Input_Parser(fnet.units['Qair'])
    #     psurv_parser = Pressure_Input_Parser(fnet.units['Psurf'])
    #     ws_parser = Windspeed_Input_Parser(fnet.units['Wind'])

    #     # parse fluxnet data by passing through the parsers
    #     self.DataFrame['swvis_srf_down'] = sw_parser.convert(fnet.df['SWdown'])
    #     self.DataFrame['lw_srf_down'] = lw_parser.convert(fnet.df['LWdown'])
    #     self.DataFrame['t_air'] = temp_parser.convert(fnet.df['Tair'])
    #     self.DataFrame['q_air'] = qair_parser.convert(fnet.df['Qair'])
    #     self.DataFrame['press_srf'] = psurv_parser.convert(fnet.df['Psurf'])
    #     self.DataFrame['rain'] = precip_parser.convert(fnet.df['Precip'])
    #     # Sofar we have no snow input
    #     self.DataFrame['snow'] = 0.0
    #     self.DataFrame['wind_air'] = ws_parser.convert(fnet.df['Wind'])

    #     # Removing too low wind values to avoid model instabilities
    #     self.DataFrame.loc[self.DataFrame['wind_air'] < 0.1, 'wind_air'] = 0.1


    def _parse_dC13_and_DC14(self):
        df_co2_dC13 = pd.read_csv(self.settings.co2_dC13_file,
                                  delim_whitespace=True, header=None)
        df_co2_dC13.columns = ['year', 'co2_dC13']
        df_co2_dC13['year'] = df_co2_dC13['year'] - 0.5
        df_co2_dC13['year'] = df_co2_dC13['year'].astype(int)
        self.DataFrame = pd.merge(self.DataFrame, df_co2_dC13, on='year')

        # Parse DC14
        df_co2_DC14 = pd.read_csv(self.settings.co2_DC14_file,
                                  delim_whitespace=True, header=None)
        df_co2_DC14.columns = ['year', '1', '2', '3']
        df_co2_DC14['year'] = df_co2_DC14['year'] - 0.5
        df_co2_DC14['year'] = df_co2_DC14['year'].astype(int)

        if self.Lat > 30.0:
            c14_index = 1
        elif (self.Lat > - 30.0) & (self.Lat <= 30.0):
            c14_index = 2
        elif self.Lat <= -30.0:
            c14_index = 3
        else:
            print("This should not happen")
            exit(99)

        df_c14_slice = df_co2_DC14[['year', str(c14_index)]]
        df_c14_slice = df_c14_slice.rename(columns={str(c14_index): 'co2DC14'})
        self.DataFrame = pd.merge(self.DataFrame, df_c14_slice, on='year')

    def _parse_p_depositions(self):
        rt_path_p = self.settings.root_pdep_path
        p_dep_forcing = PdepositionForcing(root_path=rt_path_p, verbosity_level= self.settings.verbosity)
        p_dep_forcing.extract(lon=self.Lon, lat= self.Lat)
        self.DataFrame["p_srf_down"] = p_dep_forcing.p_dep

    def _parse_n_deposition(self):
        rt_path_n = self.settings.root_ndep_path
        n_dep_forcing = NdepositionForcing(root_path=rt_path_n, projection_scenario=self.settings.ndep_projection_scenario, verbosity_level= self.settings.verbosity)
        n_dep_forcing.extract(lon=self.Lon, lat= self.Lat, year_min= self.year_min, year_max= self.year_max)
        self.DataFrame = pd.merge(self.DataFrame, n_dep_forcing.Data.copy(), on=['year', 'doy'])
        self.DataFrame = self.DataFrame.rename(columns={'nhx': 'nhx_srf_down', 'noy': 'noy_srf_down'})

    def _export_static(self):
        df_export = self.DataFrame.copy()

        # Round values according to 4 significant figures
        for var in self.quincy_full_forcing_columns:
            df_export[var] = round(df_export[var], 4)
            df_export[var] = df_export[var].apply(pd.to_numeric, downcast='float').fillna(0)

        # Make sure that columns are sorted according to QUINCY's needs
        df_export = df_export[self.quincy_full_forcing_columns]

        # Insert first unit row
        df_export.loc[-1] = self.quincy_unit_row
        df_export.index = df_export.index + 1
        df_export = df_export.sort_index()

        rt_output_folder = self.settings.root_output_path
        static_folder = f"{rt_output_folder}/{self.settings.static_forcing_folder_name}"
        

        os.makedirs(static_folder, exist_ok=True)

        # Export file acccording to QUINCY standards
        outSiteFile = f"{static_folder}/{self.sitename}_s_{self.year_min}-{self.year_max}.dat"
        df_export.to_csv(outSiteFile, header=True, sep=" ", index=None)

    def _generate_and_export_transient_forcing(self):

        # Create a simple reproducible random number generator seed
        sname  = self.sitename
        seed = 0
        for char in sname:
            seed += int(ord(char))
        np.random.seed(seed = seed)
        if self.settings.verbosity == Verbosity.Full:
            print(f"Using {seed} as random number generator seed.")

        # copy main Fluxnet file
        df_fluxnet = self.DataFrame.copy()

        ymin = self.year_min
        ymax = 2010
        yforcing_0 = self.settings.first_transient_forcing_year

        # These years need to be filed with data
        years_to_be_sampled = np.arange(yforcing_0, ymin)
        # These years are aviable to sample from (year max is included)
        years_available = np.arange(ymin, ymax + 1)

        # Create transient dataframe
        df_transient = pd.DataFrame()

        for year in years_to_be_sampled:
            # Randomly sampled year
            year_sampled = np.random.choice(years_available)

            # Copy dataset and replace the year
            df_slice = df_fluxnet[df_fluxnet['year'] == year_sampled].copy()
            df_slice['year'] = year

            df_transient = pd.concat([df_transient, df_slice], ignore_index=True)
            if self.settings.verbosity == Verbosity.Full:
                print(f"{year} sampled from {year_sampled}.")


        # Add the org. fluxnet data add the end of the file
        df_transient = pd.concat([df_transient, df_fluxnet], ignore_index=True)


            
            
        self.DataFrame = df_transient
        
        self.year_min = yforcing_0
        
        #self.DataFrame  =  self.DataFrame .drop(columns=['co2_dC13', 'co2_mixing_ratio', 'co2DC14'])

        
        # Parse CO2 forcing
        self.dprint("Parsing CO2..", lambda: self._parse_co2_forcing())

        # Parse dC13 and DC14
        self.dprint("Parsing dCO2-13 and 14..", lambda:self._parse_dC13_and_DC14())

        # Parse phosphorus deposition
        self.dprint("Parsing P deposition..",lambda: self._parse_p_depositions())

        # Parse nitrogen deposition
        self.dprint("Parsing N deposition..", lambda:self._parse_n_deposition())

        # Testing for Nan
        self.dprint("Testing for missing values..", lambda: self._testing_for_nan())
        
       
        
        # Round values according to 4 significant figures
        for var in self.quincy_full_forcing_columns:
            self.DataFrame[var] = round(self.DataFrame[var], 4)
            self.DataFrame[var] = self.DataFrame[var].apply(pd.to_numeric, downcast='float').fillna(0)
            
        print(self.DataFrame) 
            

        # Make sure that columns are sorted according to QUINCY's needs
        self.DataFrame = self.DataFrame[self.quincy_full_forcing_columns]

        # Resetting index to avoid year scrable after sorting
        self.DataFrame.reset_index()

        # Insert first unit row
        self.DataFrame.loc[-1] = self.quincy_unit_row
        self.DataFrame.index = self.DataFrame.index + 1
        self.DataFrame = self.DataFrame.sort_index()

        rt_output_folder = self.settings.root_output_path
        transient_folder = f"{rt_output_folder}/{self.settings.transient_forcing_folder_name}"
        
        
        os.makedirs(transient_folder, exist_ok=True)
        
        
        



        # Export file acccording to QUINCY standards
        outSiteFile = f"{transient_folder}/{self.sitename}_t_{yforcing_0}-{self.year_max}.dat"
        self.DataFrame.to_csv(outSiteFile, header=True, sep=" ", index=None)


    def _testing_for_nan(self):
        nan_rows = self.DataFrame[self.DataFrame.isna().any(axis=1)].shape[0]
        if nan_rows > 0:
            raise Exception(f"Error: Found {nan_rows} rows with nan values. Skipping location...")

        self.DataFrame['year'] = self.DataFrame['year'].astype(int)
        self.DataFrame['doy'] = self.DataFrame['doy'].astype(int)
