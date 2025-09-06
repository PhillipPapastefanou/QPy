import numpy  as np
import pandas as pd
import netCDF4

from src.quincy.base.PFTTypes import PftFluxnet, GetQuincyPFTfromFluxnetPFT

from src.forcing.site_derived.converter.settings import Settings, Verbosity
from src.forcing.site_derived.converter.base_parsing import Base_Parsing
from src.forcing.site_derived.converter.atto_forcing import Quincy_ATTO_Forcing


from src.forcing.site_derived.base.gridded_input import SoilGridsDatabase
from src.forcing.site_derived.base.gridded_input import LithologyMap
from src.forcing.site_derived.base.gridded_input import Phosphorus_Inputs

class Quincy_ATTO_Site_Data:

    def __init__(self, lon, lat, settings : Settings):
        self.lon =  lon
        self.lat = lat
        self.settings = settings

    def Parse_Environmental_Data(self):

        # ds = netCDF4.Dataset(self.fnet.fname_path_meteo)

        # # Longitude reference to account for solar inclination difference
        # # For now just se to the longitude coordinate
        # self.Gmt_ref = self.lon

        # # Get clay fraction and convert from % to fraction
        # self.Clay_fraction = ds['CLYPPT'][0,0] / 100.0

        # # Get silt fraction and convert from % to fraction
        # self.Silt_fraction = ds['SLTPPT'][0,0] / 100.0

        # # Get sand fraction and convert from % to fraction
        # self.Sand_fraction = ds['SNDPPT'][0,0] / 100.0

        # # Get bulk density
        # self.Bulk_density_sg = ds['BLDFIE'][0,0]

        # # Saturated water content (volumetric fraction) for tS  [fraction]
        # Fc_vol_sg = ds['AWCtS'][0, 0] / 100.0

        # # Available soil water capacity (volumetric fraction) until wilting point
        # pwp_vol_sg = ds['WWP'][0, 0] / 100.0

        # Obtain depth to berock from the soil grids database
        soil_grid_database = SoilGridsDatabase(self.settings.soil_grid_database_path, self.settings.verbosity)
        soil_grid_database.extract(lon= self.lon, lat = self.lat)
        depth_to_bedrock = soil_grid_database.Depth_to_Bedrock

        # if (Fc_vol_sg < pwp_vol_sg) & (self.settings.verbosity == Verbosity.Warning):
        #     print(f"Saturated water content ({Fc_vol_sg}) is less then available water capacity ({pwp_vol_sg}).")

        # self.AWC = (Fc_vol_sg - pwp_vol_sg) * depth_to_bedrock * 1000.0;

        self.Taxousda = soil_grid_database.Taxousda
        self.Taxnwrb = soil_grid_database.Taxnwrb

        qmax_df = pd.read_csv(self.settings.qmax_file, delim_whitespace=True)
        self.Q_max_org = qmax_df['qmax_org_value'].values[int(self.Taxnwrb)]


        phosphorus_inputs = Phosphorus_Inputs(self.settings.phosphorus_input_path, self.settings.verbosity)
        phosphorus_inputs.extract(lon =self.lon, lat = self.lat)
        self.P_soil_depth = phosphorus_inputs.P_depth
        self.P_soil_labile = phosphorus_inputs.P_labile_inorganic
        self.P_soil_slow = phosphorus_inputs.P_slow
        self.P_soil_occlud = phosphorus_inputs.P_occluded
        self.P_soil_primary = phosphorus_inputs.P_primary


        lithology_map = LithologyMap(self.settings.lithology_map_path, self.settings.verbosity)
        lithology_map.extract(lon =self.lon, lat = self.lat)
        self.Glim_class = lithology_map.Glim_class



        # Get soil PH from the data
        # self.PH = ds['PHIHOX'][0,0] / 10.0

        # Set Nleaf to missing value
        self.Nleaf = -9999.0

        # Set SLA to missing value
        self.SLA = -9999.0

        # Set height to missing value
        self.Height = -9999.0

        # Set Age to missing value
        self.Age = -9999
        # Parsing plant year for now using standard values of 1500
        self.Plant_year = self.Age
        if self.Plant_year < 0:
            self.Plant_year = 1500


        # Set BG ?? to missing value
        # Todo figure out what BG means
        self.BG = -9999

        # Copy IGBP str
        self.PFT_fluxnet = "TrBE"



        #ds.close()

        # ds_rs = netCDF4.Dataset(self.fnet.fname_path_rs)
        # # Take the first LAI value
        # self.LAI = ds_rs['LAI'][0,0,0]

        # ds_rs.close()

    def Parse_PFT(self, qf : Quincy_ATTO_Forcing):

        KelvinToCelcius = 273.15

        df = qf.DataFrame.copy()
        df['t_air_C']  = df['t_air'] - KelvinToCelcius
        df['date'] = self.fnet.df['date']

        self.Temp_monthly_avg_min = df['t_air_C'].groupby([df['date'].dt.year, df['date'].dt.month]).mean().min()
        self.Temp_yearly_avg = df['t_air_C'].groupby([df['date'].dt.year]).mean().mean()
        # Mulitply times 365 because rainfall is per day
        self.Rain_yearly_sum_avg = (df['rain'].groupby([df['date'].dt.year]).mean() * 365.0).mean()

        self._parse_IGBP_string(IGBP_str        = self.PFT_IGBP_str,
                                T_monthly_min   = self.Temp_monthly_avg_min,
                                T_yearly_avg    = self.Temp_yearly_avg,
                                P_yearly_sum    = self.Rain_yearly_sum_avg,
                                )
        
        self.flxunet_pft = PftFluxnet.TrBE
        self.pft_quincy = GetQuincyPFTfromFluxnetPFT(self.flxunet_pft)


    def Perform_sanity_checks(self):
        if np.isnan(self.Sand_fraction):
            self.Sand_fraction = 0.4
        if np.isnan(self.Silt_fraction):
            self.Silt_fraction = 0.4
        if np.isnan(self.Clay_fraction):
            self.Clay_fraction = 1.0 - self.Sand_fraction - self.Silt_fraction
        if np.isnan(self.PH):
            self.PH = 6.0
        if np.isnan(self.AWC):
            self.AWC = 200.0
        if np.isnan(self.Bulk_density_sg):
            self.Bulk_density_sg = 1500.0
        if np.isnan(self.Taxousda):
            self.Taxousda = 30
        if np.isnan(self.Taxnwrb):
            self.Taxnwrb = 27
        if np.isnan(self.Glim_class):
            self.Glim_class = 2





