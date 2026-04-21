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

from src.sens.auxil import Subslicer
from scipy.stats import qmc
from src.sens.auxil import rescale


# Fluxnet3 forcing
forcing = ForcingDataset.FLUXNET3
# Fluxnet3 sites
site = "DE-Hai"
# Use static forcing
forcing_mode = ForcingMode.TRANSIENT
# Number of cpu cores to be used
NTASKS  = 64
# Path where all the simulation data will be saved
RAM_IN_GB = 300
NNODES = 1
PARTITION = 'work'
RUN_DIRECTORY = "output/04_transient_fluxnet"

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

# Override forcing file
forcing_file = '/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/QUINCY_DE-Hai_1901_2024.dat'


# Apply the testbed configuration 
ApplyDefaultSiteLevel(namelist=namelist_base)

namelist_base.base_ctl.file_sel_output_variables.value = os.path.join(QUINCY_ROOT_PATH, 'data', 'basic_output_variables.txt')

# C only
namelist_base.vegetation_ctl.veg_bnf_scheme.value = VegBnfScheme.UNLIMITED
namelist_base.vegetation_ctl.leaf_stoichom_scheme.value = LeafStoichomScheme.FIXED
namelist_base.soil_biogeochemistry_ctl.flag_sb_prescribe_po4.value = True
namelist_base.soil_biogeochemistry_ctl.sb_bnf_scheme.value = SbBnfScheme.UNLIMITED
namelist_base.base_ctl.flag_slow_sb_pool_spinup_accelerator.value = False

namelist_base.jsb_forcing_ctl.transient_spinup_years.value = 100

namelist_base.base_ctl.output_end_last_day_year.value = 124
namelist_base.base_ctl.output_start_first_day_year.value = 1
namelist_base.jsb_forcing_ctl.transient_simulation_start_year.value = 1901
namelist_base.jsb_forcing_ctl.transient_spinup_start_year.value = 1901
namelist_base.jsb_forcing_ctl.transient_spinup_end_year.value = 1930
namelist_base.jsb_forcing_ctl.simulation_length_number.value = 124
namelist_base.base_ctl.fluxnet_type_transient_timestep_output.value = True
namelist_base.base_ctl.fluxnet_static_forc_start_yr.value = 2000
namelist_base.base_ctl.fluxnet_static_forc_last_yr.value = 2024


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

number_of_runs = 100
number_of_soil_samples = int(number_of_runs/2)

# If we speicify more variables that we use we do NOT have a problem
number_of_variables = 2

# Create a latin hypercube sample that is distributed between 0-1
seed   = 123456789
sampler = qmc.LatinHypercube(d = number_of_variables, seed= seed)
sample = sampler.random(n = number_of_soil_samples)
sample = sample.T

# Create a subslicer to make rescaling easier
slicer = Subslicer(array=sample)

# Parameter sand 
sand_min = 0.16
sand_max = 0.25

# Parameter silt 
silt_min = 0.28
silt_max = 0.38

silts = rescale(slicer.get(), min = silt_min, max = silt_max)
sands = rescale(slicer.get(), min = sand_min, max = sand_max)


silt_list = []
sand_list = []
soil_phys_list = []

h = 0
for j in range(0, 2):
    # We loop through the number of soil samples
    for i in range(0, number_of_soil_samples):
        
        # We create a copy of the lctlibfile...
        lctlib = deepcopy(lctlib_base)
        nlm = deepcopy(namelist_base)        
        
        if j ==0 :
            nlm.base_ctl.use_soil_phys_jsbach.value = False
            nlm.spq_ctl.spq_deactivate_spq.value = False
        else:
            nlm.base_ctl.use_soil_phys_jsbach.value = True
            nlm.spq_ctl.spq_deactivate_spq.value = True
        
        
        #lctlib[pft].psi50_xylem = -3.8        
        # lctlib[pft].slope_leaf_close = float(slope_leaf_closes[i])
        # lctlib[pft].g_res = float(10**g_res_logs[i])
        
        nlm.spq_ctl.spq_soil_silt.value = float(silts[i])
        nlm.spq_ctl.spq_soil_sand.value = float(sands[i])
        nlm.spq_ctl.spq_soil_clay.value = 1.0 - nlm.spq_ctl.spq_soil_silt.value - nlm.spq_ctl.spq_soil_sand.value
        
        
        nlm.jsb_sse_nml.qs_soil_silt.value = float(silts[i])
        nlm.jsb_sse_nml.qs_soil_sand.value = float(sands[i])
        nlm.jsb_sse_nml.qs_soil_clay.value = 1.0 - nlm.jsb_sse_nml.qs_soil_silt.value - nlm.jsb_sse_nml.qs_soil_sand.value
        
        user_git_info = UserGitInformation(QUINCY_ROOT_PATH, 
                                            os.path.join(setup_root_path, "output", str(h)), 
                                            site)  
        
        #Create one QUINCY setup
        quincy_setup = Quincy_Setup(folder = os.path.join(setup_root_path, "output", str(h)), 
                                    namelist = nlm, 
                                    lctlib = lctlib, 
                                    forcing_path= forcing_file,
                                    user_git_info= user_git_info)
        # Add to the setup creation
        quincy_multi_run.add_setup(quincy_setup)  
      
        soil_phys_list.append(j)
        h += 1

    silt_list.append(silts)
    sand_list.append(sands)
    
# Generate quincy setups
quincy_multi_run.generate_files()


df_parameter_setup = pd.DataFrame({
    'id': np.arange(number_of_runs),
    'fid': np.arange(number_of_runs),
    'use_jsb_physics': soil_phys_list, 
    'sand': np.array(sand_list).flatten(),
    'silt': np.array(silt_list).flatten()
})

# df_parameter_setup['silt']= np.round(silts ,5)
# df_parameter_setup['sand']= np.round(sands ,5)

df_parameter_setup.to_csv(os.path.join(setup_root_path, "parameters.csv"), index=False)

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