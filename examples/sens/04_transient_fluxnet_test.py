import sys
import os
import shutil

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))
from copy import deepcopy
import numpy as np
import pandas as pd

from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.LctlibReader import LctlibReader
from src.quincy.base.PFTTypes import PftQuincy, PftFluxnet
from src.sens.base import Quincy_Setup
from src.sens.base import Quincy_Multi_Run
from src.quincy.base.EnvironmentalInputTypes import *
from src.quincy.base.NamelistTypes import *
from src.quincy.base.EnvironmentalInput import EnvironmentalInputSite
from src.quincy.base.user_git_information import UserGitInformation


from src.quincy.run_scripts.default import ApplyDefaultSiteLevel
from src.quincy.run_scripts.submit import GenerateSlurmScript

if 'QUINCY' in os.environ:        
    QUINCY_ROOT_PATH = os.environ.get("QUINCY")
else:
    print("Environmental variable QUINCY is not defined")
    print("Please set QUINCY to the directory of your quincy root path")
    exit(99)

# Fluxnet3 forcing
forcing = ForcingDataset.FLUXNET3
# Fluxnet3 sites
site = "DE-Hai"
# Use static forcing
forcing_mode = ForcingMode.TRANSIENT
# Number of cpu cores to be used
NTASKS  = 4
# Path where all the simulation data will be saved
RUN_DIRECTORY = "output/04_transient_fluxnet_test"


# Classic sensitivity analysis where we are apply differnt Namelist or Lctlib files to ONE climate file
# The basic forcing path
# We need a base namelist and lctlib which we then modify accordingly
namelist_root_path = os.path.join(QUINCY_ROOT_PATH,'contrib', 'namelist' ,'namelist.slm')
lctlib_root_path = os.path.join(QUINCY_ROOT_PATH,'data', 'lctlib_quincy_nlct14.def')

# Parse base namelist path
nlm_reader = NamelistReader(namelist_root_path)
namelist_base = nlm_reader.parse()

# Path where to save the setup
setup_root_path = os.path.join(THIS_DIR, RUN_DIRECTORY)

env_input = EnvironmentalInputSite(
                                   forcing_mode=forcing_mode, 
                                   forcing_dataset=forcing)

# Parse paths of the forcing
namelist_base, forcing_file = env_input.parse_single_site(namelist=namelist_base, site = site)

# Apply the testbed configuration 
ApplyDefaultSiteLevel(namelist=namelist_base)

# Dummy change to be reset to 500-1000 years
#namelist_base.jsb_forcing_ctl.transient_spinup_years = 500
namelist_base.base_ctl.file_sel_output_variables.value = os.path.join(QUINCY_ROOT_PATH, 'data', 'basic_output_variables.txt')


# C only
namelist_base.vegetation_ctl.veg_bnf_scheme.value = VegBnfScheme.UNLIMITED
namelist_base.vegetation_ctl.leaf_stoichom_scheme.value = LeafStoichomScheme.FIXED
namelist_base.soil_biogeochemistry_ctl.flag_sb_prescribe_po4.value = True
namelist_base.soil_biogeochemistry_ctl.sb_bnf_scheme.value = SbBnfScheme.UNLIMITED
namelist_base.base_ctl.flag_slow_sb_pool_spinup_accelerator.value = False


namelist_base.base_ctl.output_end_last_day_year.value = 30
namelist_base.base_ctl.output_start_first_day_year.value = 1
namelist_base.jsb_forcing_ctl.transient_simulation_start_year.value = 1901
namelist_base.jsb_forcing_ctl.transient_spinup_start_year.value = 1901
namelist_base.jsb_forcing_ctl.transient_spinup_end_year.value = 1930
namelist_base.jsb_forcing_ctl.transient_spinup_years.value = 10
namelist_base.jsb_forcing_ctl.simulation_length_number.value = 20

namelist_base.base_ctl.fluxnet_type_transient_timestep_output.value = True
namelist_base.base_ctl.fluxnet_static_forc_start_yr.value = 1910
namelist_base.base_ctl.fluxnet_static_forc_last_yr.value = 1920



# Parse base lctlibe path
lctlib_reader = LctlibReader(lctlib_root_path)
lctlib_base = lctlib_reader.parse()

#Obtain pft_id from namelist
pft_id = namelist_base.vegetation_ctl.plant_functional_type_id.value
pft = list(PftQuincy)[pft_id - 1]

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Main code to be modified
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# One at a time sensitivity calculation
# First we pick a parameter for example psi50_xylem
# The standard value is -3.0 MPa
psi50_xylem =  -3.0

# We define min and max MPa
psi50_xylem_min = -6.0
psi50_xylem_max = -0.5

# Define the number of steps we want to slice
nslice = 4
# Now we can use numpy to create and array
psi50s = np.linspace(psi50_xylem_min, psi50_xylem_max, num=nslice)

#you could also do it manually:
#psi50s = np.array([-6.0, -3.0, -2.0, -1.0])

# We create a multi quincy run object
quincy_multi_run = Quincy_Multi_Run(setup_root_path)

# We loop through the number of slice
for i in range(0, nslice):
    # We create a copy of the lctlibfile...
    lctlib = deepcopy(lctlib_base)

    #... and change the value of psi50
    # the float conversion in necessary to convert from a numpy numeric type to standard numeric python
    lctlib[pft].psi50_xylem = float(psi50s[i])
    # lctlib[pft].k_xylem_sat = 10.0
    # lctlib[pft].kappa_leaf = 1.0
    
    user_git_info = UserGitInformation(QUINCY_ROOT_PATH, 
                                           os.path.join(setup_root_path,"output", str(i)), 
                                           site)  

    #Create one QUINCY setup
    quincy_setup = Quincy_Setup(folder = os.path.join(setup_root_path,"output", str(i)), 
                                namelist = namelist_base,
                                lctlib = lctlib,
                                forcing_path = forcing_file,
                                user_git_info= user_git_info)

    # Add to the setup creation
    quincy_multi_run.add_setup(quincy_setup)

# Generate quincy setups
quincy_multi_run.generate_files()

#Important: we need to save the psi50s so that we can later identify which simulation belongs to which file
df_parameter_setup = pd.DataFrame(psi50s)
df_parameter_setup.columns = ['psi50_xylem']
df_parameter_setup['id'] = np.arange(0, nslice)
df_parameter_setup['fid'] = np.arange(0, nslice)
df_parameter_setup.to_csv(os.path.join(setup_root_path, "parameters.csv"), index=False)


GenerateSlurmScript(path = setup_root_path, ntasks=NTASKS)

shutil.copyfile(os.path.join(THIS_DIR, os.pardir, os.pardir,'src', 'quincy', 'run_scripts', 'run_mpi.py'), 
                             os.path.join(setup_root_path, 'run_mpi.py'))
import time
time.sleep(1.0)

import subprocess
scriptpath = os.path.join(setup_root_path, 'submit.sh')
p = subprocess.Popen(f'/usr/bin/sbatch {scriptpath}', shell=True, cwd=setup_root_path)       
stdout, stderr = p.communicate()