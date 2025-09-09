import sys
import os
import subprocess
from time import perf_counter
import numpy as np

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

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

# Output libraries
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

site = 'ATTO'

# Number of cpu cores to be used
NTASKS  = 1
# Path where all the simulation data will be saved
RUN_DIRECTORY = "output/01_static_quincy"

# We need a base namelist and lctlib which we then modify accordingly
namelist_root_path = os.path.join(THIS_DIR, "namelist_atto_base.slm")
lctlib_root_path = os.path.join(QUINCY_ROOT_PATH, 'data', 'lctlib_quincy_nlct14.def')
forcing_file = '/Net/Groups/BSI/work_scratch/ppapastefanou/ATTO_forcing/static/ATTO_s_2000-2023.dat'

# Parse base namelist path
nlm_reader = NamelistReader(namelist_root_path)
namelist = nlm_reader.parse()

# Parse base lctlib path
lctlib_reader = LctlibReader(lctlib_root_path)
lctlib_base = lctlib_reader.parse()


# Path where to save the setup
setup_root_path = os.path.join(THIS_DIR, RUN_DIRECTORY)

# Parse user git information
user_git_info = UserGitInformation(QUINCY_ROOT_PATH, 
                                           setup_root_path, 
                                           site)      

# Apply the testbed configuration
ApplyDefaultSiteLevel(namelist=namelist)

# Limit output variables
namelist.base_ctl.file_sel_output_variables.value = os.path.join(QUINCY_ROOT_PATH, 'data', 'basic_output_variables.txt')

# C only
namelist.vegetation_ctl.veg_bnf_scheme.value = VegBnfScheme.UNLIMITED
namelist.vegetation_ctl.leaf_stoichom_scheme.value = LeafStoichomScheme.FIXED
namelist.soil_biogeochemistry_ctl.flag_sb_prescribe_po4.value = True
namelist.soil_biogeochemistry_ctl.sb_bnf_scheme.value = SbBnfScheme.UNLIMITED
namelist.base_ctl.flag_slow_sb_pool_spinup_accelerator.value = False

# Static forcing setup
namelist.jsb_forcing_ctl.forcing_mode.value = ForcingMode.STATIC
namelist.base_ctl.forcing_file_start_yr.value = 2000
namelist.base_ctl.forcing_file_last_yr.value = 2023
namelist.base_ctl.output_end_last_day_year.value = 24
namelist.base_ctl.output_start_first_day_year.value = 1
namelist.jsb_forcing_ctl.simulation_length_number.value = 24
namelist.base_ctl.output_interval_pool.value = OutputIntervalPool.DAILY
namelist.base_ctl.output_interval_flux.value = OutputIntervalPool.DAILY

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Main code to be modified
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# Change some parameters 
namelist.spq_ctl.soil_clay.value = 0.5
namelist.spq_ctl.soil_sand.value = 0.3
namelist.spq_ctl.soil_silt.value = 0.2

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Do not modify below
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# We create a single quincy setup
quincy_single_run_config = Quincy_Single_Run(setup_root_path)

#Create one QUINCY setup
quincy_setup = Quincy_Setup(folder = setup_root_path,
                            namelist = namelist, 
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
print(f"Elapsed: {np.round(t2-t1)} seconds.")

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Postprocess
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

target_categories = []
format = Output_format.Single
output_factory = QNC_std_output_factory(root_path = os.path.join(THIS_DIR, RUN_DIRECTORY), 
                                        output_format=format,
                                        target_categories=target_categories)
output_factory.Calculate_std_output()
print("Finished!")