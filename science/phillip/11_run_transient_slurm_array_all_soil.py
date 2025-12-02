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
from src.quincy.IO.ParamlistWriter import ParamlistWriter, Paramlist
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
from src.quincy.run_scripts.submit import GenerateSlurmScriptArrayBased

from src.sens.auxil import Subslicer
from scipy.stats import qmc
from src.sens.auxil import rescale
import time



# Fluxnet3 forcing
forcing = ForcingDataset.FLUXNET3
# Fluxnet3 sites
site = "DE-Hai"
# Use static forcing
forcing_mode = ForcingMode.TRANSIENT
# Number of cpu cores to be used
NMAXTASKS  = 512
# Path where all the simulation data will be saved
RAM_IN_GB = 4

number_of_runs = 1024*8

n_soil_combs = 2

PARTITION = 'work'
RUN_DIRECTORY =  "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/jsbach_spq/11_transient_slurm_array/"

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

namelist_base.jsb_forcing_ctl.transient_spinup_years.value = 200

namelist_base.base_ctl.output_end_last_day_year.value = 124
namelist_base.base_ctl.output_start_first_day_year.value = 1
namelist_base.jsb_forcing_ctl.transient_simulation_start_year.value = 1901
namelist_base.jsb_forcing_ctl.transient_spinup_start_year.value = 1901
namelist_base.jsb_forcing_ctl.transient_spinup_end_year.value = 1930
namelist_base.jsb_forcing_ctl.simulation_length_number.value = 124
namelist_base.base_ctl.fluxnet_type_transient_timestep_output.value = True
namelist_base.base_ctl.fluxnet_static_forc_start_yr.value = 1901
namelist_base.base_ctl.fluxnet_static_forc_last_yr.value = 2024


# Parse base lctlibe path
lctlib_reader = LctlibReader(lctlib_root_path)
lctlib_base = lctlib_reader.parse()

#Obtain pft_id from namelist
pft_id = namelist_base.vegetation_ctl.plant_functional_type_id.value
pft = PftQuincy(pft_id)

# Generate empty paramlist
paramlist_base = Paramlist()

# This line is important so QUINCY know it is expecting a paramlist
namelist_base.base_ctl.set_parameter_values_from_file.value = True

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Main code to be modified
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# We create a single quincy setup
quincy_multi_run = Quincy_Multi_Run(setup_root_path)


number_of_soil_samples = int(number_of_runs/n_soil_combs)

# If we speicify more variables that we use we do NOT have a problem
number_of_variables = 15

# Create a latin hypercube sample that is distributed between 0-1
seed   = 123456789
sampler = qmc.LatinHypercube(d = number_of_variables, seed= seed)
sample = sampler.random(n = number_of_soil_samples)
sample = sample.T

# Create a subslicer to make rescaling easier
slicer = Subslicer(array=sample)

# 1. Parameter k_xylem_sat
k_xylem_sat_min = 4.0
k_xylem_sat_max = 8.0

# 2. Parameter kappa_stem
kappa_stem_min = 100
kappa_stem_max = 180

# 3. Parameter kappa_leaf 
kappa_leaf_min      = 0.02
kappa_leaf_max      = 0.04

# 4. Parameter klatosa 
k_latosa_min = 3000
k_latosa_max = 5000

# 5. Parameter klatosa 
g1_min = 2.5
g1_max = 3.5

# 6. Parameter klatosa 
g0_min = 0.0018
g0_max = 0.0022

# 7. Parameter klatosa 
psi_close50_min = -0.8
psi_close50_max = -1.5

# 8. Parameter sand 
# sand_min = 0.16
# sand_max = 0.25
sand_min = 0.23
sand_max = 0.25



# 9. Parameter silt 
silt_min = 0.28
silt_max = 0.38

silt_min = 0.33
silt_max = 0.35

# 10. root dist
root_dist_min = 3.5
root_dist_max = 6.5

# 11. Parameter kappa_leaf 
root_scale_min = 10.0
root_scale_max = 500.0

# 12. Parameter kappa_leaf 
slope_leaf_close_min = 2.0
slope_leaf_close_max = 3.0


# 13. Parameter silt 
gdd_t_air_thres_min  = 8.0
gdd_t_air_thres_max = 8.0

# 14. Parameter silt 
gdd_t_air_req_min  = 400
gdd_t_air_req_max = 440

# 15. Parameter silt 
k_gdd_min  = 0.015
k_gdd_max  = 0.017

k_xylem_sats = rescale(slicer.get(), min = k_xylem_sat_min, max = k_xylem_sat_max)
kappa_stems = rescale(slicer.get(), min = kappa_stem_min, max = kappa_stem_max)
kappa_leaves = rescale(slicer.get(), min = kappa_leaf_min, max = kappa_leaf_max)
k_latosas = rescale(slicer.get(), min = k_latosa_min, max = k_latosa_max)
g1s = rescale(slicer.get(), min = g1_min, max = g1_max)
g0s = rescale(slicer.get(), min = g0_min, max = g0_max)
psi_close50s = rescale(slicer.get(), min = psi_close50_min, max = psi_close50_max)
silts = rescale(slicer.get(), min = silt_min, max = silt_max)
sands = rescale(slicer.get(), min = sand_min, max = sand_max)
root_dists = rescale(slicer.get(), min = root_dist_min, max = root_dist_max)
root_scale_log= rescale(slicer.get(), min = np.log10(root_scale_min), max = np.log10(root_scale_max))
slope_leaf_closes = rescale(slicer.get(), min = slope_leaf_close_min, max = slope_leaf_close_max)

gdd_t_air_thresholds = rescale(slicer.get(), min = gdd_t_air_thres_min, max = gdd_t_air_thres_max)
gdd_t_air_reqs = rescale(slicer.get(), min = gdd_t_air_req_min, max = gdd_t_air_req_max)
k_gdd_s = rescale(slicer.get(), min = k_gdd_min, max = k_gdd_max)

soil_phys_list = []
soil_phys_mod_list = []

h = 0
for j in range(0, n_soil_combs):
    # We loop through the number of soil samples
    for i in range(0, number_of_soil_samples):
              

        # We create a copy of the lctlibfile...
        lctlib = deepcopy(lctlib_base)
        nlm = deepcopy(namelist_base) 
        
        # Duplicate the paramlist
        paramlist = deepcopy(paramlist_base)
        
        # Write one standard simulation without plant hydraulics  
        if i == 0:
            nlm.assimilation_ctl.gs_beta_type.value = GsBetaType.SOIL
            nlm.phyd_ctl.use_plant_hydraulics.value = False      
        
        else:
            nlm.assimilation_ctl.gs_beta_type.value = GsBetaType.PLANT
            nlm.phyd_ctl.use_plant_hydraulics.value = True    
               
        soil_model_str = ""
        
        nlm.base_ctl.use_soil_phys_jsbach.value = True
        nlm.spq_ctl.spq_deactivate_spq.value = True
            
        if j == 0:
            nlm.jsb_hydro_nml.soilhydmodel.value = JSBSoilHydModelType.VanGenuchten
            soil_model_str = "VanGenuchten"       
        elif j == 1:
            nlm.jsb_hydro_nml.soilhydmodel.value = JSBSoilHydModelType.Campbell
            soil_model_str = "Campbell"           
        else:
            print("Invalid soil model")
            exit(99)
                
        
        # Set GDD air temperature according from array
        paramlist.phenology_ctl.gdd_t_air_threshold.value = float(gdd_t_air_thresholds[i])
        paramlist.phenology_ctl.gdd_t_air_threshold.parsed = True
        
        lctlib[pft].gdd_req_max = float(gdd_t_air_reqs[i])
        lctlib[pft].k_gdd_dormance = float(k_gdd_s[i])
       
        lctlib[pft].k_xylem_sat = float(k_xylem_sats[i])
        lctlib[pft].kappa_stem = float(kappa_stems[i])
        lctlib[pft].kappa_leaf = float(kappa_leaves[i])
        lctlib[pft].k_latosa = float(k_latosas[i])
        lctlib[pft].g0 = float(g0s[i])
        lctlib[pft].g1_medlyn = float(g1s[i])
        lctlib[pft].psi50_leaf_close = float(psi_close50s[i])
        lctlib[pft].k_root_dist = float(root_dists[i])
        lctlib[pft].root_scale = float(10**root_scale_log[i])
        lctlib[pft].psi50_xylem = -3.8        
        lctlib[pft].slope_leaf_close = float(slope_leaf_closes[i])
        
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
                                    user_git_info= user_git_info,
                                    paramlist = paramlist)
        # Add to the setup creation
        quincy_multi_run.add_setup(quincy_setup)  
      
        soil_phys_list.append(j)
        soil_phys_mod_list.append(soil_model_str)
        h += 1
        
# Generate quincy setups
quincy_multi_run.generate_files()


df_parameter_setup = pd.DataFrame({
    'id': np.arange(number_of_runs),
    'fid': np.arange(number_of_runs),
    'use_jsb_physics': soil_phys_list,
    'soil_pyhs_ret': soil_phys_mod_list
})

df_parameter_setup['k_xylem_sats'] = np.round(np.tile(k_xylem_sats, n_soil_combs),5)
df_parameter_setup['kappa_stem'] = np.round(np.tile(kappa_stems, n_soil_combs),5)
df_parameter_setup['kappa_leaf'] = np.round(np.tile(kappa_leaves, n_soil_combs),5)
df_parameter_setup['k_latosa']=np.round(np.tile(k_latosas, n_soil_combs),5)
df_parameter_setup['g0']= np.round(np.tile(g0s, n_soil_combs),5)
df_parameter_setup['g1']=np.round(np.tile(g1s, n_soil_combs),5)
df_parameter_setup['psi50_close']= np.round(np.tile(psi_close50s, n_soil_combs),5)
df_parameter_setup['root_dist']= np.round(np.tile(root_dists, n_soil_combs),5)
df_parameter_setup['silt']= np.round(np.tile(silts, n_soil_combs),5)
df_parameter_setup['sand']= np.round(np.tile(sands, n_soil_combs),5)
df_parameter_setup['root_scale']= np.round(10**np.tile(root_scale_log, n_soil_combs),5)
df_parameter_setup['slope_leaf_close']= np.round(np.tile(slope_leaf_closes, n_soil_combs) ,5)

df_parameter_setup['gdd_t_air_threshold']= np.round(np.tile(gdd_t_air_thresholds,n_soil_combs), 5)
df_parameter_setup['gdd_t_air_req']= np.round(np.tile(gdd_t_air_reqs,n_soil_combs), 5)
df_parameter_setup['k_gdd']= np.round(np.tile(k_gdd_s,n_soil_combs), 5)

df_parameter_setup.to_csv(os.path.join(setup_root_path, "parameters.csv"), index=False)

quincy_binary_path = os.path.join(QUINCY_ROOT_PATH, "x86_64-gfortran", "bin", "land.x")

GenerateSlurmScriptArrayBased(
                    ntasks        = number_of_runs,
                    path          = setup_root_path,
                    quincy_binary = quincy_binary_path,
                    ram_in_gb     = RAM_IN_GB, 
                    ntasksmax     = NMAXTASKS, 
                    partition     = PARTITION)

shutil.copyfile(os.path.join(THIS_DIR, os.pardir, os.pardir,'src', 'quincy', 'run_scripts', 'run_quincy_array.py'), 
                             os.path.join(setup_root_path, 'run_quincy_array.py'))

time.sleep(1.0)

import subprocess
scriptpath = os.path.join(setup_root_path, 'submit.sh')
p = subprocess.Popen(f'/usr/bin/sbatch {scriptpath}', shell=True, cwd=setup_root_path)       
stdout, stderr = p.communicate()
