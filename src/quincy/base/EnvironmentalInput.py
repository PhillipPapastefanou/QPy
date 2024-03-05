import os
import glob

import pandas as pd

from src.quincy.base.EnvironmentalInputTypes import *
from src.quincy.base.NamelistTypes import ForcingMode
from src.quincy.base.Namelist import Namelist
from src.quincy.base.PFTTypes import PftQuincy

class EnvironmentalInput:

    def __init__(self):
        # Constants
        #self.isiteDataDirBase = "/Net/Groups/BSI/data/quincy/input/point"
        self.isiteDataDirBase = "/Volumes/BSI/data/quincy/input/point"
        self.imetForcingDir = "met_forcing"
        self.isoilForcStatDirBase = "soil_forcing_stat_sl15"
        self.iforceSoilLitterFile = "soil_forcing_litterfall.dat"
        self.iforceSoilPhysicFile = "soil_forcing_soilphysics.dat"
        self.isitelistFullPath = []

        # Properties
        self.forcingDataset = ForcingDataset.FLUXNET3
        self.forcingMode    = ForcingMode.STATIC
        self.sitelist = ['DE-Hai']
        # Inputs have been checked
        self.checked = False

    def check(self):

        self.ioverride_forcing()

        self.checked = True

    def ioverride_forcing(self):

        forcing_sep = "s" if self.forcingMode == ForcingMode.STATIC else "t"

        if self.forcingDataset == ForcingDataset.FLUXNET3:
            forcing_dataset_str = "FLUXNET3"
            if self.forcingMode == ForcingMode.STATIC:
                fn_sitelist = "flux3_all_sites_1991-2017_list.dat"
            else:
                fn_sitelist = "flux3_all_sites_1901-2017_list.dat"

        self.full_site_information_path = f"{self.isiteDataDirBase}/{forcing_dataset_str}/{fn_sitelist}"
        if not os.path.exists(self.full_site_information_path):
            print(f"Could not find file: {self.full_site_information_path}.")
            exit(99)

        forcing_folder_path =  f"{self.isiteDataDirBase}/{forcing_dataset_str}/{self.imetForcingDir}"

        for site in self.sitelist:

            full_forcing_site_path = f"{forcing_folder_path}/{site}_{forcing_sep}_"

            paths = glob.glob(f'{full_forcing_site_path}*.dat')
            if len(paths) == 0:
                print(f"Could not find forcing file in {full_forcing_site_path}")
                #exit(99)
            elif len(paths) > 1:
                print(f"Found multiple forcing files {paths}")
                #exit(99)
            else:
                path = paths[0]
                self.isitelistFullPath.append(path)

    def parse_sitelist_information(self, namelist: Namelist):

        base = namelist.base_ctl
        grid = namelist.grid_ctl
        spq = namelist.spq_ctl
        sb = namelist.soil_biogeochemistry_ctl
        pheno = namelist.phenology_ctl
        veg = namelist.vegetation_ctl

        if self.forcingDataset == ForcingDataset.FLUXNET3:

            df= pd.read_csv(self.full_site_information_path, delim_whitespace=True)

            # Todo refactor this section to work with an acutal list not only one element
            df_sel = df[df['Site-ID'] == self.sitelist[0]]

            if df_sel.empty:
                print(f"Could not find {self.sitelist[0]} in {self.full_site_information_path}")
                exit(99)


            grid.latitude  = df_sel['lat'].values[0]
            grid.longitude = df_sel['lon'].values[0]

            base.forcing_file_start_yr = df_sel['start'].values[0]
            base.forcing_file_last_yr  = df_sel['end'].values[0]

            spq.soil_clay       = df_sel['clay'].values[0]
            spq.soil_silt       = df_sel['silt'].values[0]
            spq.soil_sand       = df_sel['sand'].values[0]
            spq.bulk_density    = df_sel['bd'].values[0]

            sb.soil_ph              = df_sel['ph'].values[0]
            sb.nwrb_taxonomy_class  = df_sel['taxusda'].values[0]
            sb.usda_taxonomy_class  = df_sel['taxnwrb'].values[0]
            sb.soil_p_depth         = df_sel['soilP_depth'].values[0]
            sb.soil_p_labile        = df_sel['soilP_labile'].values[0]
            sb.soil_p_slow          = df_sel['soilP_slow'].values[0]
            sb.soil_p_occluded      = df_sel['soilP_occluded'].values[0]
            sb.soil_p_primary       = df_sel['soilP_primary'].values[0]
            sb.qmax_org_fine_particle = df_sel['Qmax_org_fp'].values[0]

            pheno.lai_site_specific = df_sel['LAI'].values[0]

            pft_str = df_sel['PFT'].values[0]
            veg.plant_functional_type_id = PftQuincy[pft_str].value

















