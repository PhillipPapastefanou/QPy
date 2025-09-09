import sys
import os
import shutil
import subprocess
from time import perf_counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir))
from copy import deepcopy
import numpy as np
import pandas as pd

from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.LctlibReader import LctlibReader
from src.quincy.base.PFTTypes import PftQuincy, PftFluxnet
from src.sens.base import Quincy_Setup
from src.sens.base import Quincy_Single_Run
from src.quincy.base.EnvironmentalInputTypes import *
from src.quincy.base.NamelistTypes import *
from src.quincy.base.EnvironmentalInput import EnvironmentalInputSite
from src.quincy.base.user_git_information import UserGitInformation


from src.quincy.run_scripts.default import ApplyDefaultSiteLevel
from src.quincy.run_scripts.submit import GenerateSlurmScript

from src.postprocessing.qnc_defintions import Output_format
from src.postprocessing.qnc_output_parser import QNC_output_parser
from src.postprocessing.qnc_ncdf_reader import QNC_ncdf_reader
from src.postprocessing.qnc_std_output_factory import QNC_std_output_factory



if 'QUINCY' in os.environ:        
    QUINCY_ROOT_PATH = os.environ.get("QUINCY")
else:
    print("Environmental variable QUINCY is not defined")
    print("Please set QUINCY to the directory of your quincy root path")
    exit(99)

site = "ATTO"
# Use static forcing
forcing_mode = ForcingMode.TRANSIENT
# Number of cpu cores to be used
NTASKS  = 1
# Path where all the simulation data will be saved
RUN_DIRECTORY = "output/transient_atto"


# We need a base namelist and lctlib which we then modify accordingly
namelist_root_path = "/User/homes/ppapastefanou/ATTO-BR2_test/namelist_atto_base.slm"
lctlib_root_path = os.path.join(QUINCY_ROOT_PATH, 'data', 'lctlib_quincy_nlct14.def')
forcing_file = '/Net/Groups/BSI/work_scratch/ppapastefanou/ATTO_forcing/transient/ATTO_t_1901-2023.dat'


# Parse base namelist path
nlm_reader = NamelistReader(namelist_root_path)
namelist_base = nlm_reader.parse()



# Path where to save the setup
setup_root_path = os.path.join(THIS_DIR, RUN_DIRECTORY)


user_git_info = UserGitInformation(QUINCY_ROOT_PATH, 
                                           setup_root_path, 
                                           site)      

# Apply the testbed configuration
ApplyDefaultSiteLevel(namelist=namelist_base)

namelist_base.base_ctl.file_sel_output_variables.value = os.path.join(QUINCY_ROOT_PATH, 'data', 'basic_output_variables.txt')


# C only
namelist_base.vegetation_ctl.veg_bnf_scheme.value = VegBnfScheme.UNLIMITED
namelist_base.vegetation_ctl.leaf_stoichom_scheme.value = LeafStoichomScheme.FIXED
namelist_base.soil_biogeochemistry_ctl.flag_sb_prescribe_po4.value = True
namelist_base.soil_biogeochemistry_ctl.sb_bnf_scheme.value = SbBnfScheme.UNLIMITED
namelist_base.base_ctl.flag_slow_sb_pool_spinup_accelerator.value = False

# For now 50 years of spinup are sufficient 
namelist_base.base_ctl.output_end_last_day_year.value = 123
namelist_base.base_ctl.output_start_first_day_year.value = 1
namelist_base.jsb_forcing_ctl.transient_simulation_start_year.value = 1901
namelist_base.jsb_forcing_ctl.transient_spinup_start_year.value = 1901
namelist_base.jsb_forcing_ctl.transient_spinup_end_year.value = 1930
namelist_base.jsb_forcing_ctl.transient_spinup_years.value = 50
namelist_base.jsb_forcing_ctl.simulation_length_number.value = 123
namelist_base.base_ctl.fluxnet_type_transient_timestep_output.value = True
namelist_base.base_ctl.fluxnet_static_forc_start_yr.value = 2000
namelist_base.base_ctl.fluxnet_static_forc_last_yr.value = 2023
namelist_base.base_ctl.forcing_file_start_yr.value = 1901
namelist_base.base_ctl.forcing_file_last_yr.value = 2023


namelist_base.base_ctl.output_interval_pool.value = OutputIntervalPool.DAILY
namelist_base.base_ctl.output_interval_flux.value = OutputIntervalPool.DAILY


# Turn off plant hydraulics
namelist_base.assimilation_ctl.gs_beta_type.value = GsBetaType.SOIL
namelist_base.phyd_ctl.use_plant_hydraulics.value = False


namelist_base.phenology_ctl.lai_max.value = 10
namelist_base.spq_ctl.soil_clay.value = 0.5
namelist_base.spq_ctl.soil_sand.value = 0.3
namelist_base.spq_ctl.soil_silt.value = 0.2


# Parse base lctlib path
lctlib_reader = LctlibReader(lctlib_root_path)
lctlib_base = lctlib_reader.parse()

#Obtain pft_id from namelist
pft_id = namelist_base.vegetation_ctl.plant_functional_type_id.value
pft = PftQuincy(pft_id)
lctlib_base[pft].k_xylem_sat = 5.0
lctlib_base[pft].psi50_xylem = -3.5
lctlib_base[pft].kappa_stem = 100
lctlib_base[pft].kappa_leaf = 0.005

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Main code to be modified
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# We create a single quincy setup
quincy_single_run_config = Quincy_Single_Run(setup_root_path)

#Create one QUINCY setup
quincy_setup = Quincy_Setup(folder = setup_root_path,
                            namelist = namelist_base, 
                            lctlib = lctlib_base, forcing_path=forcing_file,
                            user_git_info= user_git_info)
# Export setup
quincy_single_run_config.set_setup(quincy_setup)
quincy_single_run_config.generate_files()


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Quincy run scripts
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

t1 = perf_counter()

quincy_binary_path = os.path.join(QUINCY_ROOT_PATH, "x86_64-gfortran", "bin", "land.x")

p = subprocess.Popen(quincy_binary_path,
                        cwd=setup_root_path)

stdout, stderr = p.communicate()
returncode = p.returncode

t2 = perf_counter()
print(f"Elapsed: {t2-t1} seconds.")

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Postprocess
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


target_categories = []
format = Output_format.Single
output_factory = QNC_std_output_factory(root_path = os.path.join(THIS_DIR, RUN_DIRECTORY), 
                                        output_format=format,
                                        target_categories=target_categories)
output_factory.Calculate_std_output()
#output_factory.Calculate_fluxnet_stat()
print("Finished!")