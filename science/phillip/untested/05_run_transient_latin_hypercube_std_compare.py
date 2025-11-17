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

# Define the number of runs and variables
number_of_runs = 4096
# Fluxnet3 forcing
forcing = ForcingDataset.FLUXNET3
# Fluxnet3 sites
site = "DE-Hai"
# Use static forcing
forcing_mode = ForcingMode.TRANSIENT
# Number of cpu cores to be used
NTASKS  = 512
RAM_IN_GB = 300
NNODES = 8
PARTITION = 'work'
# Path where all the simulation data will be saved
RUN_DIRECTORY = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/14_transient_latin_hypercube_with_std_HAINICH_data_full"

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
namelist_base.base_ctl.output_end_last_day_year.value = 106
namelist_base.base_ctl.output_start_first_day_year.value = 1
namelist_base.jsb_forcing_ctl.transient_simulation_start_year.value = 1901
namelist_base.jsb_forcing_ctl.transient_spinup_start_year.value = 1901
namelist_base.jsb_forcing_ctl.transient_spinup_end_year.value = 1930
namelist_base.jsb_forcing_ctl.transient_spinup_years.value = 500
namelist_base.jsb_forcing_ctl.simulation_length_number.value = 106
namelist_base.base_ctl.fluxnet_type_transient_timestep_output.value = True
namelist_base.base_ctl.fluxnet_static_forc_start_yr.value = 2000
namelist_base.base_ctl.fluxnet_static_forc_last_yr.value = 2006


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
number_of_variables = 10

# Create a latin hypercube sample that is distributed between 0-1
seed   = 123456789
sampler = qmc.LatinHypercube(d = number_of_variables, seed= seed)
sample = sampler.random(n = number_of_runs)
sample = sample.T

# Create a subslicer to make rescaling easier
slicer = Subslicer(array=sample)

# 1. Parameter k_xylem_sat
k_xylem_sat_min = 1.5
k_xylem_sat_max = 10.0

# 2. Parameter kappa_stem
kappa_stem_min = 40
kappa_stem_max = 600

# 3. Parameter kappa_leaf 
kappa_leaf_min_log = np.log10(0.001)
kappa_leaf_max_log = np.log10(0.01)

# 4. Parameter klatosa 
k_latosa_min = 3000
k_latosa_max = 5000

# 5. Parameter klatosa 
g1_min = 0.5
g1_max = 7.0

# 6. Parameter klatosa 
g0_min = 0.001
g0_max = 0.02

# 7. Parameter klatosa 
psi_close50_min = -2.5
psi_close50_max = -2.0

# 8. Parameter sand 
sand_min = 0.16
sand_max = 0.25

# 9. Parameter silt 
silt_min = 0.28
silt_max = 0.38

# 10. Parameter silt 
root_dist_min = 1.2
root_dist_max = 6.5

# Now we rescale parameters
k_xylem_sats = rescale(slicer.get(), min = k_xylem_sat_min, max = k_xylem_sat_max)
kappa_stems = rescale(slicer.get(), min = kappa_stem_min, max = kappa_stem_max)
kappa_leaves_log = rescale(slicer.get(), min = kappa_leaf_min_log, max = kappa_leaf_max_log)
k_latosas = rescale(slicer.get(), min = k_latosa_min, max = k_latosa_max)
g1s = rescale(slicer.get(), min = g1_min, max = g1_max)
g0s = rescale(slicer.get(), min = g0_min, max = g0_max)
psi_close50s = rescale(slicer.get(), min = psi_close50_min, max = psi_close50_max)
silts = rescale(slicer.get(), min = silt_min, max = silt_max)
sands = rescale(slicer.get(), min = sand_min, max = sand_max)
root_dists = rescale(slicer.get(), min = root_dist_min, max = root_dist_max)

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
        #... and change the value of psi50
        # the float conversion in necessary to convert from a numpy numeric type to standard numeric python
        lctlib[pft].k_xylem_sat = float(k_xylem_sats[i])
        lctlib[pft].kappa_stem = float(kappa_stems[i])
        lctlib[pft].kappa_leaf = float(10**kappa_leaves_log[i])
        lctlib[pft].k_latosa = float(k_latosas[i])
        lctlib[pft].g0 = float(g0s[i])
        lctlib[pft].g1_medlyn = float(g1s[i])
        lctlib[pft].psi50_leaf_close = float(psi_close50s[i])
        lctlib[pft].k_root_dist = float(root_dists[i])
        lctlib[pft].psi50_xylem = -3.7

    
        nlm.spq_ctl.soil_silt.value = float(silts[i])
        nlm.spq_ctl.soil_sand.value = float(sands[i])
        nlm.spq_ctl.soil_clay.value = 1.0 - nlm.spq_ctl.soil_silt.value - nlm.spq_ctl.soil_sand.value

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
df_parameter_setup = pd.DataFrame(np.round(k_xylem_sats, 5))
df_parameter_setup.columns = ['k_xylem_sat']
df_parameter_setup['id'] = np.arange(0, number_of_runs)
df_parameter_setup['fid'] = np.arange(0, number_of_runs)
df_parameter_setup['kappa_stem'] = np.round(kappa_stems,5)
df_parameter_setup['kappa_leaf'] = np.round(10**kappa_leaves_log,5)
df_parameter_setup['k_latosa']= np.round(k_latosas,5)
df_parameter_setup['g0']= np.round(g0s,5)
df_parameter_setup['g1']= np.round(g1s,5)
df_parameter_setup['psi50_close']= np.round(psi_close50s,5)
df_parameter_setup['root_dist']= np.round(root_dists,5)
df_parameter_setup['silt']= np.round(silts ,5)
df_parameter_setup['samd']= np.round(sands ,5)


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
