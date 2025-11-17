import sys
import os
import shutil
import subprocess
from time import perf_counter

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
from src.quincy.auxil.find_quincy_paths import QuincyPathFinder

from src.quincy.run_scripts.default import ApplyDefaultSiteLevel
from src.quincy.run_scripts.submit import GenerateSlurmScript

# Fluxnet3 forcing
forcing = ForcingDataset.FLUXNET3
# Fluxnet3 sites
site = "DE-Hai"
# Use static forcing
forcing_mode = ForcingMode.TRANSIENT
# Number of cpu cores to be used
NTASKS  = 1
# Path where all the simulation data will be saved
RAM_IN_GB = 10
NNODES = 1
PARTITION = 'work'
RUN_DIRECTORY = "output/01_transient_fluxnet"

qpf = QuincyPathFinder()
QUINCY_ROOT_PATH = qpf.quincy_root_path

# Classic sensitivity analysis where we are apply differnt Namelist or Lctlib files to ONE climate file
# The basic forcing path
# We need a base namelist and lctlib which we then modify accordingly
namelist_root_path = qpf.namelist_root_path
lctlib_root_path = qpf.lctlib_root_path

# Parse base namelist path
nlm_reader = NamelistReader(namelist_root_path)
namelist_base = nlm_reader.parse()

# Path where to save the setup
setup_root_path = os.path.join(THIS_DIR, RUN_DIRECTORY)


user_git_info = UserGitInformation(QUINCY_ROOT_PATH, 
                                           setup_root_path, 
                                           site)      
env_input = EnvironmentalInputSite(
                                   forcing_mode=forcing_mode, 
                                   forcing_dataset=forcing)


# Parse paths of the forcing
namelist_base, forcing_file = env_input.parse_single_site(namelist=namelist_base, site = site)

# Apply the testbed configuration 
ApplyDefaultSiteLevel(namelist=namelist_base)

namelist_base.base_ctl.file_sel_output_variables.value = os.path.join(QUINCY_ROOT_PATH, 'data', 'basic_output_variables.txt')

# C only
namelist_base.vegetation_ctl.veg_bnf_scheme.value = VegBnfScheme.UNLIMITED
namelist_base.vegetation_ctl.leaf_stoichom_scheme.value = LeafStoichomScheme.FIXED
namelist_base.soil_biogeochemistry_ctl.flag_sb_prescribe_po4.value = True
namelist_base.soil_biogeochemistry_ctl.sb_bnf_scheme.value = SbBnfScheme.UNLIMITED
namelist_base.base_ctl.flag_slow_sb_pool_spinup_accelerator.value = False


namelist_base.base_ctl.output_end_last_day_year.value = 106
namelist_base.base_ctl.output_start_first_day_year.value = 1
namelist_base.jsb_forcing_ctl.transient_simulation_start_year.value = 1901
namelist_base.jsb_forcing_ctl.transient_spinup_start_year.value = 1901
namelist_base.jsb_forcing_ctl.transient_spinup_end_year.value = 1930
namelist_base.jsb_forcing_ctl.transient_spinup_years.value = 50
namelist_base.jsb_forcing_ctl.simulation_length_number.value = 106

namelist_base.base_ctl.fluxnet_type_transient_timestep_output.value = True
namelist_base.base_ctl.fluxnet_static_forc_start_yr.value = 2000
namelist_base.base_ctl.fluxnet_static_forc_last_yr.value = 2006
namelist_base.base_ctl.forcing_file_last_yr.value = 2006


# Parse base lctlibe path
lctlib_reader = LctlibReader(lctlib_root_path)
lctlib_base = lctlib_reader.parse()

#Obtain pft_id from namelist
pft_id = namelist_base.vegetation_ctl.plant_functional_type_id.value
pft = PftQuincy(pft_id)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Main code to be modified
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# We create a single quincy setup
quincy_multi_run = Quincy_Multi_Run(setup_root_path)

number_of_runs = NTASKS


# We loop through the number of slice
for i in range(0, number_of_runs):
    
    # We create a copy of the lctlibfile...
    lctlib = deepcopy(lctlib_base)
    nlm = deepcopy(namelist_base)


    # lctlib[pft].psi50_xylem = -3.8        
    # lctlib[pft].slope_leaf_close = float(slope_leaf_closes[i])
    # lctlib[pft].g_res = float(10**g_res_logs[i])
    
    # nlm.spq_ctl.soil_silt.value = float(silts[i])
    # nlm.spq_ctl.soil_sand.value = float(sands[i])
    #nlm.spq_ctl.soil_clay.value = 1.0 - nlm.spq_ctl.soil_silt.value - nlm.spq_ctl.soil_sand.value
    
    user_git_info = UserGitInformation(QUINCY_ROOT_PATH, 
                                        os.path.join(setup_root_path, "output", str(i)), 
                                        site)  
    
    #Create one QUINCY setup
    quincy_setup = Quincy_Setup(folder = os.path.join(setup_root_path, "output", str(i)), 
                                namelist = nlm, 
                                lctlib = lctlib, 
                                forcing_path= forcing_file,
                                user_git_info= user_git_info)
    # Add to the setup creation
    quincy_multi_run.add_setup(quincy_setup)  
      
# Generate quincy setups
quincy_multi_run.generate_files()

df_parameter_setup = pd.DataFrame({
    'id': np.arange(number_of_runs),
    'fid': np.arange(number_of_runs),
})

# df_parameter_setup['silt']= np.round(silts ,5)
# df_parameter_setup['sand']= np.round(sands ,5)

df_parameter_setup.to_csv(os.path.join(setup_root_path, "parameters.csv"), index=False)


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# SLURM runscript options
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

GenerateSlurmScript(path         = setup_root_path, 
                    ntasks       = NTASKS,
                    ram_in_gb    = RAM_IN_GB, 
                    nnodes       = NNODES, 
                    partition    = PARTITION)

shutil.copyfile(os.path.join(THIS_DIR, os.pardir, os.pardir,'src', 'quincy', 'run_scripts', 'run_mpi.py'), 
                             os.path.join(setup_root_path, 'run_mpi.py'))

import time
time.sleep(1.0)

import subprocess
scriptpath = os.path.join(setup_root_path, 'submit.sh')
p = subprocess.Popen(f'/usr/bin/sbatch {scriptpath}', shell=True, cwd=setup_root_path)       
stdout, stderr = p.communicate()


# t1 = perf_counter()

# quincy_binary_path = os.path.join(QUINCY_ROOT_PATH, "x86_64-gfortran", "bin", "land.x")

# p = subprocess.Popen(quincy_binary_path,
#                         cwd=setup_root_path)

# stdout, stderr = p.communicate()
# returncode = p.returncode

# t2 = perf_counter()
# print(f"Elapsed: {t2-t1} seconds.")