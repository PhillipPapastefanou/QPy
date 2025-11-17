import sys
import os
import shutil

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir))
from copy import deepcopy
import numpy as np
import pandas as pd

from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.LctlibReader import LctlibReader
from src.quincy.base.PFTTypes import PftQuincy, PftFluxnet, GetQuincyPFTfromFluxnetPFT
from src.sens.base import Quincy_Setup
from src.sens.base import Quincy_Multi_Run
from src.quincy.base.user_git_information import UserGitInformation
from src.quincy.run_scripts.default import ApplyDefaultSiteLevel
from src.quincy.run_scripts.submit import GenerateSlurmScript
from src.quincy.base.EnvironmentalInputTypes import *
from src.quincy.base.NamelistTypes import *
from src.quincy.base.EnvironmentalInput import EnvironmentalInputSite


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

NNODES = 10

# Define the number of runs and variables
number_of_runs = 64*NNODES*14
# Fluxnet3 forcing
forcing = ForcingDataset.FLUXNET3
# Fluxnet3 sites
site = "DE-Hai"
# Use static forcing
forcing_mode = ForcingMode.TRANSIENT
# Number of cpu cores to be used
NTASKS  = 64*NNODES
RAM_IN_GB = 300

PARTITION = 'work'
# Path where all the simulation data will be saved
RUN_DIRECTORY = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/kmax_gammastem/11_std_only"

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
# use fixed allocation scheme (Sönke comment)
namelist_base.vegetation_ctl.biomass_alloc_scheme.value = BiomassAllocScheme.FIXED

# For now 100 years of spinup are sufficient 
namelist_base.base_ctl.output_end_last_day_year.value = 124
namelist_base.base_ctl.output_start_first_day_year.value = 1
namelist_base.jsb_forcing_ctl.transient_simulation_start_year.value = 1901
namelist_base.jsb_forcing_ctl.transient_spinup_start_year.value = 1901
namelist_base.jsb_forcing_ctl.transient_spinup_end_year.value = 1930
namelist_base.jsb_forcing_ctl.transient_spinup_years.value = 500
namelist_base.jsb_forcing_ctl.simulation_length_number.value = 124
namelist_base.base_ctl.fluxnet_type_transient_timestep_output.value = True
namelist_base.base_ctl.fluxnet_static_forc_start_yr.value = 2000
namelist_base.base_ctl.fluxnet_static_forc_last_yr.value = 2024


# Turn on plant hydraulics
namelist_base.assimilation_ctl.gs_beta_type.value = GsBetaType.PLANT
namelist_base.phyd_ctl.use_plant_hydraulics.value = True

# Parse base lctlibe path
lctlib_reader = LctlibReader(lctlib_root_path)
lctlib_base = lctlib_reader.parse()

#Obtain pft_id from namelist
pft_id = namelist_base.vegetation_ctl.plant_functional_type_id.value
pft = PftQuincy(pft_id)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Main code to be modified
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 


# 2 Parameter latin hypercupe sensitivity calculation


# If we speicify more variables that we use we do NOT have a problem
number_of_variables = 6

# Create a latin hypercube sample that is distributed between 0-1
seed   = 123456789
sampler = qmc.LatinHypercube(d = number_of_variables, seed= seed)
sample = sampler.random(n = number_of_runs)
sample = sample.T

# Create a subslicer to make rescaling easier
slicer = Subslicer(array=sample)

# 1. Minimal water potential
phi_leaf_min_min = -2.5
phi_leaf_min_max = -1.0

# 2. root dist
root_dist_min = 4.0
root_dist_max = 6.0

# 3. Parameter sand 
sA_min = -0.1E-6
sA_max = -0.1E-5

# 4. Parameter silt 
sB_min = -10.0
sB_max = -14.0

# 5. Parameter silt 
kdiff_sat_sl_min = 1E-8
kdiff_sat_sl_max = 1E-6

# 6. Parameter silt 
theta_s_min = 0.5
theta_s_max = 0.57


# Now we rescale parameters
phi_leaf_mins = rescale(slicer.get(), min = phi_leaf_min_min, max = phi_leaf_min_max)
sAs = rescale(slicer.get(), min = sA_min, max = sA_max)
sBs = rescale(slicer.get(), min = sB_min, max = sB_max)
kdiff_sats_log = rescale(slicer.get(), min = np.log10(kdiff_sat_sl_min), max = np.log10(kdiff_sat_sl_max))
theta_ss = rescale(slicer.get(), min = theta_s_min, max = theta_s_max)


# kappa_leaves = rescale(slicer.get(), min = kappa_leaf_min, max = kappa_leaf_max)
# k_latosas = rescale(slicer.get(), min = k_latosa_min, max = k_latosa_max)
# g1s = rescale(slicer.get(), min = g1_min, max = g1_max)
# g0s = rescale(slicer.get(), min = g0_min, max = g0_max)

# silts = rescale(slicer.get(), min = silt_min, max = silt_max)
# sands = rescale(slicer.get(), min = sand_min, max = sand_max)
root_dists = rescale(slicer.get(), min = root_dist_min, max = root_dist_max)
# g_res_logs= rescale(slicer.get(), min = np.log10(g_res_min), max = np.log10(g_res_max))




# We create a multi quincy run object
quincy_multi_run = Quincy_Multi_Run(setup_root_path)

# We loop through the number of slice
for i in range(0, number_of_runs):
    
    # We create a copy of the lctlibfile...
    lctlib = deepcopy(lctlib_base)
    nlm = deepcopy(namelist_base)
    
    # Write one standard simulation without plant hydraulics  
    if i == 0:
        nlm.assimilation_ctl.gs_beta_type.value = GsBetaType.SOIL
        nlm.phyd_ctl.use_plant_hydraulics.value = False        
        
    else:  
        
        nlm.assimilation_ctl.gs_beta_type.value = GsBetaType.SOIL
        nlm.phyd_ctl.use_plant_hydraulics.value = False 
                
        #... and change the value of psi50
        # the float conversion in necessary to convert from a numpy numeric type to standard numeric python
        # lctlib[pft].k_xylem_sat = float(k_xylem_sats[i])#  = 2.03655
        # lctlib[pft].kappa_stem = float(kappa_stems[i])# = 342.64
          
        lctlib[pft].phi_leaf_min = float(phi_leaf_mins[i])
        
        
        lctlib[pft].kappa_leaf = 0.03082
        lctlib[pft].k_latosa = 3600.0
        lctlib[pft].g0 = 0.00613
        lctlib[pft].g1_medlyn = 4.0101
        lctlib[pft].k_root_dist = float(root_dists[i])
        #lctlib[pft].root_scale = float(root_scales[i])
        lctlib[pft].psi50_xylem = -3.8        
        #lctlib[pft].slope_leaf_close = float(slope_leaf_closes[i])
        lctlib[pft].g_res = 0.0   
             
        nlm.spq_ctl.saxtonA.value = float(sAs[i])
        nlm.spq_ctl.saxtonB.value = float(sBs[i])
        nlm.spq_ctl.kdiff_sat_sl.value = float(10**kdiff_sats_log[i])
        nlm.spq_ctl.theta_sat_sl.value = float(theta_ss[i])
        # nlm.spq_ctl.soil_clay.value = 1.0 - nlm.spq_ctl.soil_silt.value - nlm.spq_ctl.soil_sand.value
        
        

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

#Important: we need to save the psi50s so that we can later identify which simulation belongs to which file
df_parameter_setup = pd.DataFrame(np.round(phi_leaf_mins, 5))
df_parameter_setup.columns = ['phi_leaf_min']
df_parameter_setup['id'] = np.arange(0, number_of_runs)
df_parameter_setup['fid'] = np.arange(0, number_of_runs)
# df_parameter_setup['kappa_stem'] = np.round(kappa_stems,5)
# df_parameter_setup['kappa_leaf'] = np.round(kappa_leaves,5)
# df_parameter_setup['k_latosa']= np.round(k_latosas,5)
# df_parameter_setup['g0']= np.round(g0s,5)
# df_parameter_setup['g1']= np.round(g1s,5)
# df_parameter_setup['psi50_close']= np.round(psi_close50s,5)
df_parameter_setup['root_dist']= np.round(root_dists,5)
# df_parameter_setup['silt']= np.round(silts ,5)
# df_parameter_setup['sand']= np.round(sands ,5)
df_parameter_setup['saxtonA']= np.round(sAs ,7)
df_parameter_setup['saxtonB']= np.round(sBs ,5)
df_parameter_setup['kdiff_sat_sl']= np.round(10**kdiff_sats_log ,16)
df_parameter_setup['theta_sat_sl']= np.round(theta_ss ,5)
# df_parameter_setup['root_scale']= np.round(root_scales,5)
# df_parameter_setup['slope_leaf_close']= np.round(slope_leaf_closes ,5)
# df_parameter_setup['slope_leaf_close']= np.round(slope_leaf_closes ,5)
# df_parameter_setup['g_res']= np.round(10**g_res_logs,8)

df_parameter_setup.to_csv(os.path.join(setup_root_path, "parameters.csv"), index=False)

GenerateSlurmScript(path         = setup_root_path, 
                    ntasks       = NTASKS,
                    ram_in_gb    = RAM_IN_GB, 
                    nnodes       = NNODES, 
                    partition    = PARTITION)

shutil.copyfile(os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir,'src', 'quincy', 'run_scripts', 'run_mpi.py'), 
                             os.path.join(setup_root_path, 'run_mpi.py'))

import time
time.sleep(1.0)

import subprocess
scriptpath = os.path.join(setup_root_path, 'submit.sh')
p = subprocess.Popen(f'/usr/bin/sbatch {scriptpath}', shell=True, cwd=setup_root_path)       
stdout, stderr = p.communicate()
