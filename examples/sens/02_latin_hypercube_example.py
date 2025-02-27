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
from src.quincy.base.PFTTypes import PftQuincy, PftFluxnet, GetQuincyPFTfromFluxnetPFT
from src.sens.base import Quincy_Setup
from src.sens.base import Quincy_Multi_Run
from src.quincy.base.EnvironmentalInputTypes import *
from src.quincy.base.NamelistTypes import ForcingMode
from src.quincy.base.EnvironmentalInput import EnvironmentalInputSite
from src.quincy.base.user_git_information import UserGitInformation
from src.quincy.run_scripts.default import ApplyDefaultTestbed
from src.quincy.run_scripts.submit import GenerateSlurmScript

if 'QUINCY' in os.environ:        
    QUINCY_ROOT_PATH = os.environ.get("QUINCY")
else:
    print("Environmental variable QUINCY is not defined")
    print("Please set QUINCY to the directory of your quincy root path")
    exit(99)

from src.sens.auxil import Subslicer
from src.sens.auxil import rescale
from src.sens.auxil import rescale_mean
from scipy.stats import qmc


# Fluxnet3 forcing
forcing = ForcingDataset.FLUXNET3
# Fluxnet3 sites
site = "DE-Hai"
# Use static forcing
forcing_mode = ForcingMode.STATIC
# Number of cpu cores to be used
NTASKS  = 4
# Path where all the simulation data will be saved
RUN_DIRECTORY = "output/02_LH_test_bed_example"

# Path where to save the setup
setup_root_path = os.path.join(THIS_DIR, RUN_DIRECTORY)

# Classic sensitivity analysis where we are apply differnt Namelist or Lctlib files to ONE climate file
# The basic forcing path
# We need a base namelist and lctlib which we then modify accordingly
namelist_root_path = os.path.join(QUINCY_ROOT_PATH,'contrib', 'namelist' ,'namelist.slm')
lctlib_root_path = os.path.join(QUINCY_ROOT_PATH,'data', 'lctlib_quincy_nlct14.def')

# Parse base namelist path
nlm_reader = NamelistReader(namelist_root_path)
namelist_base = nlm_reader.parse()

env_input = EnvironmentalInputSite(
                                   forcing_mode=forcing_mode, 
                                   forcing_dataset=forcing)

# Parse paths of the forcing
namelist_base, forcing_file = env_input.parse_single_site(namelist=namelist_base, site = site)

# Apply the testbed configuration 
ApplyDefaultTestbed(namelist=namelist_base)

# Dummy change to be reset to 500-1000 years
#namelist_base.jsb_forcing_ctl.transient_spinup_years = 500
namelist_base.base_ctl.file_sel_output_variables.value = os.path.join(QUINCY_ROOT_PATH, 'data', 'basic_output_variables.txt')

# Parse base lctlibe path
lctlib_reader = LctlibReader(lctlib_root_path)
lctlib_base = lctlib_reader.parse()

#Obtain pft_id from namelist
pft_id = namelist_base.vegetation_ctl.plant_functional_type_id.value
pft = list(PftQuincy)[pft_id - 1]

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Main code to be modified
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 


# 2 Parameter latin hypercupe sensitivity calculation

# Define the number of runs and variables
number_of_runs = 128
# If we speicify more variables that we use we do NOT have a problem
number_of_variables = 3

# Create a latin hypercube sample that is distributed between 0-1
seed   = 123456789
sampler = qmc.LatinHypercube(d = number_of_variables, seed= seed)
sample = sampler.random(n = number_of_runs)
sample = sample.T

# Create a subslicer to make rescaling easier
slicer = Subslicer(array=sample)

# 1. Parameter k_xylem_sat (standard value was 1000)
k_xylem_sat_min_log = np.log10(1)
k_xylem_sat_max_log = np.log10(10000)

# 2. Parameter kappa_stem (standard value was 2000)
kappa_stem_min_log = np.log10(1)
kappa_stem_max_log = np.log10(5000)

# 3. Parameter kappa_leaf (standard value was 1)
kappa_leaf_min_log = np.log10(0.001)
kappa_leaf_max_log = np.log10(10)

# Now we rescale parameters
k_xylem_sats_log = rescale(slicer.get(), min = k_xylem_sat_min_log, max = k_xylem_sat_max_log)
kappa_stems_log = rescale(slicer.get(), min = kappa_stem_min_log, max = kappa_stem_max_log)
kappa_leaves_log = rescale(slicer.get(), min = kappa_leaf_min_log, max = kappa_leaf_max_log)

# We create a multi quincy run object
quincy_multi_run = Quincy_Multi_Run(setup_root_path)

# We loop through the number of slice
for i in range(0, number_of_runs):
    # We create a copy of the lctlibfile...
    lctlib = deepcopy(lctlib_base)

    #... and change the value of psi50
    # the float conversion in necessary to convert from a numpy numeric type to standard numeric python
    lctlib[pft].k_xylem_sat = float(10**k_xylem_sats_log[i])
    lctlib[pft].kappa_stem = float(10**kappa_stems_log[i])
    lctlib[pft].kappa_leaf = float(10**kappa_leaves_log[i])
    
    
    user_git_info = UserGitInformation(QUINCY_ROOT_PATH, 
                                           os.path.join(setup_root_path, str(i)), 
                                           site)  

    #Create one QUINCY setup
    quincy_setup = Quincy_Setup(folder = os.path.join(setup_root_path, str(i)), 
                                namelist = namelist_base, 
                                lctlib = lctlib, 
                                forcing_path= forcing_file,
                                user_git_info= user_git_info)

    # Add to the setup creation
    quincy_multi_run.add_setup(quincy_setup)

# Generate quincy setups
quincy_multi_run.generate_files()

#Important: we need to save the psi50s so that we can later identify which simulation belongs to which file
df_parameter_setup = pd.DataFrame(np.round(10**k_xylem_sats_log,3))
df_parameter_setup.columns = ['k_xylem_sat']
df_parameter_setup['id'] = np.arange(0, number_of_runs)
df_parameter_setup['fid'] = np.arange(0, number_of_runs)
df_parameter_setup['kappa_stem'] = np.round(10**kappa_stems_log,3)
df_parameter_setup['kappa_leaf'] = np.round(10**kappa_leaves_log,5)


df_parameter_setup.to_csv(os.path.join(setup_root_path, "parameters.csv"), index=False)



NTASKS  = 4

GenerateSlurmScript(path = setup_root_path, ntasks=NTASKS)

shutil.copyfile(os.path.join(THIS_DIR, os.pardir, os.pardir,'src', 'quincy', 'run_scripts', 'run_mpi.py'), 
                             os.path.join(setup_root_path, 'run_mpi.py'))

import time
time.sleep(1.0)

import subprocess
scriptpath = os.path.join(setup_root_path, 'submit.sh')
p = subprocess.Popen(f'/usr/bin/sbatch {scriptpath}', shell=True, cwd=setup_root_path)       
stdout, stderr = p.communicate()
