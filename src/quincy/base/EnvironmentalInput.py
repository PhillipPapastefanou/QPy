import os
import glob

import pandas as pd

from src.quincy.base.EnvironmentalInputTypes import *
from src.quincy.base.NamelistTypes import ForcingMode
from src.quincy.base.Namelist import Namelist
from src.quincy.base.PFTTypes import PftQuincy, PftFluxnet, GetQuincyPFTfromFluxnetPFT

class EnvironmentalInputSite:

    def __init__(self, sitelist: list, forcing_mode : ForcingMode, forcing_dataset = ForcingDataset ):
        # Constants
        self.SITE_DATA_DIR_BASE = "/Net/Groups/BSI/data/quincy/input/point"
        self.MET_FORCING_DIR_NAME = "met_forcing"
        
        # self.isoilForcStatDirBase = "soil_forcing_stat_sl15"
        # self.iforceSoilLitterFile = "soil_forcing_litterfall.dat"
        # self.iforceSoilPhysicFile = "soil_forcing_soilphysics.dat"
        # self.isitelistFullPath = []

        # Properties
        self.forcing_dataset = forcing_dataset
        self.forcing_mode    = forcing_mode
        self.sitelist = sitelist
        
        if self.forcing_dataset == ForcingDataset.FLUXNET3: 
            self.forcing_dataset_str = "FLUXNET3"
            if self.forcing_mode == ForcingMode.STATIC:
                self.fn_sitelist = "flux3_all_sites_1991-2017_list.dat"
                self.forcing_mode_short = 's'
            else:
                self.fn_sitelist = "flux3_all_sites_1901-2017_list.dat"
                self.forcing_mode_short = 't'        
            

    # def check(self):

    #     self.ioverride_forcing()

    #     self.checked = True

    #def ioverride_forcing(self):

        # forcing_sep = "s" if self.forcing_mode == ForcingMode.STATIC else "t"

        # if self.forcing_dataset == ForcingDataset.FLUXNET3:
        #     forcing_dataset_str = "FLUXNET3"
        #     if self.forcing_mode == ForcingMode.STATIC:
        #         fn_sitelist = "flux3_all_sites_1991-2017_list.dat"
        #     else:
        #         fn_sitelist = "flux3_all_sites_1901-2017_list.dat"

        # self.full_site_information_path = f"{self.SITE_DATA_DIR_BASE}/{forcing_dataset_str}/{fn_sitelist}"
        # if not os.path.exists(self.full_site_information_path):
        #     print(f"Could not find file: {self.full_site_information_path}.")
        #     exit(99)

        # forcing_folder_path =  f"{self.SITE_DATA_DIR_BASE}/{forcing_dataset_str}/{self.MET_FORCING_DIR_NAME}"

        # for site in self.sitelist:

        #     full_forcing_site_path = f"{forcing_folder_path}/{site}_{forcing_sep}_"

        #     paths = glob.glob(f'{full_forcing_site_path}*.dat')
        #     if len(paths) == 0:
        #         print(f"Could not find forcing file in {full_forcing_site_path}")
        #         #exit(99)
        #     elif len(paths) > 1:
        #         print(f"Found multiple forcing files {paths}")
        #         #exit(99)
        #     else:
        #         path = paths[0]
        #         self.isitelistFullPath.append(path)

    def parse_single_site(self, namelist: Namelist):
        
        if len(self.sitelist) != 1:
            print(f"Please provide only one site in the sitelist: Values found {self.sitelist}")
            exit(99)
                    
        # Get first element in sitelist (it should be only one)
        site = self.sitelist[0]
        
        #Forcing file
        fpaths = os.listdir(f"{self.SITE_DATA_DIR_BASE}/{self.forcing_dataset_str}/met_forcing/")
        forcing_filenames = [s for s in fpaths if f"{site}_{self.forcing_mode_short}" in s]

        if not len(forcing_filenames) == 1:
            print(f"Invalid forcing paths :{forcing_filenames}")
            exit(99)
        
        # We have only one and only forcingfile and can proceed
        forcing_file_single = forcing_filenames[0]
        self.forcing_file =  f"{self.SITE_DATA_DIR_BASE}/{self.forcing_dataset_str}/met_forcing/{forcing_file_single}"

        # Get the config data
        df_config = pd.read_csv(f"{self.SITE_DATA_DIR_BASE}/{self.forcing_dataset_str}/{self.fn_sitelist}", sep=" ")
        df_config_site = df_config.loc[df_config['Site-ID'] == site] 

        if(df_config_site.empty):
            print(f"Could not find site {site} in the config file")
            exit(99)
            
        if(df_config_site.shape[0] > 1):
            print(f"Found duplicate entries of {site} in the config file")
            exit(99)
    

        # Reset the indexes so that we always have the correct location
        df_config_site.reset_index(inplace=True)
        namelist.grid_ctl.longitude.value = df_config_site.loc[0, 'lon']
        namelist.grid_ctl.latitude.value = df_config_site.loc[0, 'lat']

        # Parse Fluxnet PFT from config to Quincy PFT ... 
        pft_fluxnet =  PftFluxnet[df_config_site.loc[0,'PFT']]
        pft_quincy = GetQuincyPFTfromFluxnetPFT(pft_fluxnet)

        # ... and set it accordingly.
        namelist.vegetation_ctl.plant_functional_type_id.value = pft_quincy.value

        # Parse the years of the filename
        namelist.base_ctl.forcing_file_start_yr.value = df_config_site.loc[0, 'start']
        namelist.base_ctl.forcing_file_last_yr.value = df_config_site.loc[0, 'end']

        spq = namelist.spq_ctl
        spq.soil_clay.value = df_config_site.loc[0, 'clay']
        spq.soil_silt.value = df_config_site.loc[0, 'silt']
        spq.soil_sand.value = df_config_site.loc[0, 'sand']
        spq.bulk_density.value = df_config_site.loc[0, 'bd']

        sb = namelist.soil_biogeochemistry_ctl
        sb.soil_ph.value = df_config_site.loc[0, 'ph']
        sb.nwrb_taxonomy_class.value = df_config_site.loc[0, 'taxusda']
        sb.usda_taxonomy_class.value = df_config_site.loc[0, 'taxnwrb']
        sb.soil_p_depth.value = df_config_site.loc[0, 'soilP_depth']
        sb.soil_p_labile.value = df_config_site.loc[0, 'soilP_labile']
        sb.soil_p_slow.value = df_config_site.loc[0, 'soilP_slow']
        sb.soil_p_occluded.value = df_config_site.loc[0, 'soilP_occluded']
        sb.soil_p_primary.value = df_config_site.loc[0, 'soilP_primary']
        sb.qmax_org_fine_particle.value = df_config_site.loc[0, 'Qmax_org_fp']

















