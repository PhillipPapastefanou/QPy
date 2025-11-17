import os
import glob
from copy import deepcopy
import pandas as pd

from src.quincy.base.EnvironmentalInputTypes import *
from src.quincy.base.NamelistTypes import ForcingMode
from src.quincy.base.Namelist import Namelist
from src.quincy.base.PFTTypes import PftQuincy, PftFluxnet, GetQuincyPFTfromFluxnetPFT

class EnvironmentalInputSite:

    def __init__(self, forcing_mode : ForcingMode, 
                 forcing_dataset : ForcingDataset, 
                 cru_ncep_site_type: CruNcepSiteType  = CruNcepSiteType.ALL
                 ):
        # Constants
        self.SITE_DATA_DIR_BASE = "/Net/Groups/BSI/data/quincy/input/point"
        self.MET_FORCING_DIR_NAME = "met_forcing"
        
        # self.isoilForcStatDirBase = "soil_forcing_stat_sl15"
        # self.iforceSoilLitterFile = "soil_forcing_litterfall.dat"
        # self.iforceSoilPhysicFile = "soil_forcing_soilphysics.dat"
        # self.isitelistFullPath = []

        # Properties
        self.forcing_dataset    = forcing_dataset
        self.forcing_mode       = forcing_mode
        self.cru_ncep_site_type = cru_ncep_site_type
        
        if self.forcing_mode == ForcingMode.STATIC:
            self.forcing_mode_short = 's'
        else:
            self.forcing_mode_short = 't'
            
        if self.forcing_dataset == ForcingDataset.CRUNCEP:
            self.forcing_mode_short = ''
                        
        if self.forcing_dataset == ForcingDataset.FLUXNET3: 
            self.forcing_dataset_str = "FLUXNET3"
            if self.forcing_mode == ForcingMode.STATIC:
                self.fn_sitelist = "flux3_all_sites_1991-2017_list.dat"
            else:
                self.fn_sitelist = "flux3_all_sites_1901-2017_list.dat"
                
        elif self.forcing_dataset == ForcingDataset.FLUXNET2: 
            self.forcing_dataset_str = "FLUXNET2"
            if self.forcing_mode == ForcingMode.STATIC:
                self.fn_sitelist = "flux_all_sites_1995-2006_list.dat"
            else:
                self.fn_sitelist = "flux_all_sites_1901-2006_list.dat"    
                
        elif self.forcing_dataset == ForcingDataset.CRUNCEP: 
            self.forcing_dataset_str = "CRUNCEPv7"            
            if self.cru_ncep_site_type == CruNcepSiteType.ALL:             
                if self.forcing_mode == ForcingMode.STATIC:                
                    self.fn_sitelist = "crun_all_gfdb_sites_1984-2013_list.dat"
                else:
                    self.fn_sitelist = "crun_all_gfdb_sites_1901-2015_list.dat"
            elif self.cru_ncep_site_type == CruNcepSiteType.CUE:             
                if self.forcing_mode == ForcingMode.STATIC:                
                    self.fn_sitelist = "crun_cue_gfdb_sites_1984-2013_list.dat"
                else:
                    self.fn_sitelist = "crun_cue_gfdb_sites_1901-2015_list.dat"
            elif self.cru_ncep_site_type == CruNcepSiteType.SPP:             
                if self.forcing_mode == ForcingMode.STATIC:                
                    self.fn_sitelist = "crun_spp_sites_1984-2013_list.dat"
                else:
                    self.fn_sitelist = "crun_spp_sites_1901-2015_list.dat"
            else:
                print(f"Unsupported cruncept site list: {self.forcing_dataset}")
                exit(99)       
        
        else:
            print(f"Unsupported forcing dataset: {self.forcing_dataset}")
            exit(99)        

    def parse_multi_sites(self, sitelist :list,
                          site_list_type: SimulationSiteType,
                          namelist: Namelist):  
        
        self.sitelist = sitelist
        if (site_list_type == SimulationSiteType.ALL) & (len(sitelist) > 0):
            print("Error: You specied a sitelist but also selected all site to be via the site_list_type.")
            print("Please provide a sitelist and set the site_list_type to CUSTOM or...")
            print("provide an empty sitelist and set site_list_type to ALL.")
            exit(99)
            
        if site_list_type == SimulationSiteType.ALL:
            df_config = pd.read_csv(f"{self.SITE_DATA_DIR_BASE}/{self.forcing_dataset_str}/{self.fn_sitelist}", sep=" ")    
            self.sitelist = df_config['Site-ID'].to_list()
        
        if not self.sitelist:
            print("Error: Empty sitelist provided or parsed")
            exit(99) 
        
        namelists = {}
        forcing_files = {}
        for site in self.sitelist:
            namelist_new = deepcopy(namelist)
            namelist_new, forcing_file = self.parse_single_site(site, namelist_new)
            namelists[site] = namelist_new
            forcing_files[site] = forcing_file
        return namelists, forcing_files
            
        
        
    def parse_single_site(self, site, namelist: Namelist):   
        self.sitelist = [site]        
        if len(self.sitelist) != 1:
            print(f"Please provide only one site in the sitelist: Values found {self.sitelist}")
            exit(99)
                    
        # Get first element in sitelist (it should be only one)
        site = self.sitelist[0]
        

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
        jsb_sse = namelist.jsb_sse_nml  
        if namelist.base_ctl.use_soil_phys_jsbach.value:
            spq.spq_deactivate_spq.value = True     
        else:          
            spq.spq_deactivate_spq.value = False    
        
        spq.spq_soil_clay.value = df_config_site.loc[0, 'clay']
        jsb_sse.qs_soil_clay.value = df_config_site.loc[0, 'clay']
        spq.spq_soil_silt.value = df_config_site.loc[0, 'silt']
        jsb_sse.qs_soil_silt.value = df_config_site.loc[0, 'silt']
        spq.spq_soil_sand.value = df_config_site.loc[0, 'sand']
        jsb_sse.qs_soil_sand.value = df_config_site.loc[0, 'sand']
        spq.spq_bulk_density.value = df_config_site.loc[0, 'bd']
        jsb_sse.qs_bulk_density.value = df_config_site.loc[0, 'bd']
        spq.spq_soil_awc_prescribe.value =  df_config_site.loc[0, 'awc']
        namelist.jsb_hydro_nml.qs_soil_awc_prescribe.value =  df_config_site.loc[0, 'awc']
            
        namelist.phenology_ctl.lai_max.value = df_config_site.loc[0, 'LAI']

        sb = namelist.soil_biogeochemistry_ctl
        sb.soil_ph.value = df_config_site.loc[0, 'ph']
        sb.nwrb_taxonomy_class.value = df_config_site.loc[0, 'taxnwrb']
        sb.usda_taxonomy_class.value = df_config_site.loc[0, 'taxusda']
        sb.soil_p_depth.value = df_config_site.loc[0, 'soilP_depth']
        sb.soil_p_labile.value = df_config_site.loc[0, 'soilP_labile']
        sb.soil_p_slow.value = df_config_site.loc[0, 'soilP_slow']
        sb.soil_p_occluded.value = df_config_site.loc[0, 'soilP_occluded']
        sb.soil_p_primary.value = df_config_site.loc[0, 'soilP_primary']
        sb.qmax_org_fine_particle.value = df_config_site.loc[0, 'Qmax_org_fp']
        
        namelist.q_syl_ctl.stand_replacing_year.value = df_config_site.loc[0, 'PlantYear']
        
        begin = namelist.base_ctl.forcing_file_start_yr.value
        end = namelist.base_ctl.forcing_file_last_yr.value         
        
        
        # Find the forcing file        
        fpaths = os.listdir(f"{self.SITE_DATA_DIR_BASE}/{self.forcing_dataset_str}/met_forcing/")
        
        # CRUNCEP has multiple sites per forcing. We need to remove the location integer identifier
        if self.forcing_dataset == ForcingDataset.CRUNCEP:
            site = site.split("_")[0]
            forcing_filenames = [s for s in fpaths if f"{site}_{begin}-{end}" in s]
        else:
            forcing_filenames = [s for s in fpaths if f"{site}_{self.forcing_mode_short}_{begin}-{end}" in s]

        if not len(forcing_filenames) == 1:
            print(f"Invalid forcing paths :{forcing_filenames}")
            exit(99)
            
        # We have only one and only forcingfile and can proceed
        forcing_file_single = forcing_filenames[0]
        forcing_file =  f"{self.SITE_DATA_DIR_BASE}/{self.forcing_dataset_str}/met_forcing/{forcing_file_single}"
        return namelist, forcing_file