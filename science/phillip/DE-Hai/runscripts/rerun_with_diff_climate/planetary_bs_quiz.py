import sys
import os
import shutil
import subprocess
from time import perf_counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir, os.pardir, os.pardir))
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

# --- Standard Configuration ---
forcing = ForcingDataset.FLUXNET3
site = "DE-Hai"
forcing_mode = ForcingMode.TRANSIENT
NMAXTASKS  = 150
RAM_IN_GB = 4
PARTITION = 'small,work'

# --- Custom Base Files ---
# Set your custom paths for the namelist and lctlib here
CUSTOM_NAMELIST_PATH = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/72_rerun_transient_3days_new_mort_new_phen_fix/output/0/namelist.slm"
CUSTOM_LCTLIB_PATH = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/72_rerun_transient_3days_new_mort_new_phen_fix/output/0/lctlib_quincy_nlct14.def"

# --- Extreme Planetary Forcing Files ---
CUSTOM_FORCING_FILES = [
    "forcing_mpi-esm1-2_ssp126_DE-Hai.dat",                     # The Baseline
    "forcing_mpi-esm1-2_ssp126_DE-Hai_jupyter_wind.dat",        # Jupiter
    "forcing_mpi-esm1-2_ssp126_DE-Hai_mars_co2.dat",            # Mars
    "forcing_mpi-esm1-2_ssp126_DE-Hai_mercury_rad.dat",         # Mercury
    "forcing_mpi-esm1-2_ssp126_DE-Hai_tmin_max_venus.dat",      # Venus
    "forcing_mpi-esm1-2_ssp126_DE-Hai_qsat_uranus.dat",         # Venus
    "forcing_mpi-esm1-2_ssp126_DE-Hai_water_GJ_1214b.dat"       # Waterworld Exoplanet
]

n_soil_combs = 1
qpf = QuincyPathFinder()
QUINCY_ROOT_PATH = qpf.quincy_root_path

RUN_DIRECTORY =  f"/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/planetary_bullshit2/"
setup_root_path = os.path.join(THIS_DIR, RUN_DIRECTORY)
ISIMIP_CLIM_PATH = "/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/ISIMIP_3b/QUINCY_ready/"


if os.path.exists(setup_root_path):
    shutil.rmtree(setup_root_path)
    
# We create a single quincy setup
quincy_multi_run = Quincy_Multi_Run(setup_root_path)

nruns = 0

# Loop over the custom forcing files directly
for forcing_filename in CUSTOM_FORCING_FILES:
    
    climate_dat_file = os.path.join(ISIMIP_CLIM_PATH, forcing_filename)
    
    # Create a clean folder name for the run by stripping the '.dat' extension
    experiment_name = forcing_filename.replace('.dat', '')
    sub_run_dir = os.path.join(setup_root_path, experiment_name)
            
    os.makedirs(sub_run_dir, exist_ok=True)
    os.makedirs(os.path.join(sub_run_dir, "output"), exist_ok=True)
           
    # Use the global custom paths instead of pulling from the old scen_dir
    namelist_path = CUSTOM_NAMELIST_PATH
    lctlib_path = CUSTOM_LCTLIB_PATH
    
    forcing_file = climate_dat_file        
    
    # Read and parse the custom configuration files
    lctlib_reader = LctlibReader(lctlib_path)
    lctlib_base = lctlib_reader.parse()
                
    nlm_reader = NamelistReader(namelist_path)
    namelist_base = nlm_reader.parse()
            
    paramlist = Paramlist()
    paramlist.lnd_q_pheno_nml.gdd_t_air_threshold.value = 8.0
    paramlist.lnd_q_pheno_nml.gdd_t_air_threshold.parsed = True
            
    namelist_base.base_ctl.output_end_last_day_year.value = 100
    namelist_base.base_ctl.output_start_first_day_year.value = 1
    namelist_base.jsb_forcing_ctl.transient_simulation_start_year.value = 1850
    namelist_base.jsb_forcing_ctl.transient_spinup_start_year.value = 1850
    namelist_base.jsb_forcing_ctl.transient_spinup_end_year.value = 1950
    namelist_base.jsb_forcing_ctl.simulation_length_number.value = 251
    namelist_base.base_ctl.fluxnet_type_transient_timestep_output.value = True
    namelist_base.base_ctl.fluxnet_static_forc_start_yr.value = 2000
    namelist_base.base_ctl.fluxnet_static_forc_last_yr.value = 2100

    namelist_base.base_ctl.forcing_file_start_yr.value = 1850
    namelist_base.base_ctl.forcing_file_last_yr.value = 2100
    namelist_base.jsb_forcing_ctl.is_daily_forcing.value = True
    
    user_git_info = UserGitInformation(QUINCY_ROOT_PATH, 
                                    os.path.join(sub_run_dir), 
                                    site)  

    # Create one QUINCY setup
    quincy_setup = Quincy_Setup(folder = os.path.join(sub_run_dir), 
                                namelist = namelist_base, 
                                lctlib = lctlib_base, 
                                forcing_path= forcing_file,
                                user_git_info= user_git_info,
                                paramlist = paramlist)
                                
    # Add to the setup creation
    quincy_multi_run.add_setup(quincy_setup)  
    nruns += 1

# Generate quincy setups
quincy_multi_run.generate_files()

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# SLURM runscript options
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

python_ex = "/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python"
quincy_binary_path = os.path.join(QUINCY_ROOT_PATH, "x86_64-gfortran", "bin", "qs.bin")

GenerateSlurmScriptArrayBased(
                    ntasks        = nruns,
                    path          = setup_root_path,
                    quincy_binary = quincy_binary_path,
                    ram_in_gb     = RAM_IN_GB, 
                    ntasksmax     = NMAXTASKS, 
                    partition     = PARTITION,
                    python        = python_ex)

shutil.copyfile(os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir, os.pardir,  os.pardir, 'src', 'quincy', 'run_scripts', 
                            'run_quincy_array.py'), 
                            os.path.join(setup_root_path, 'run_quincy_array.py'))

time.sleep(1.0)

scriptpath = os.path.join(setup_root_path, 'submit.sh')
p = subprocess.Popen(f'/usr/bin/sbatch {scriptpath}', shell=True, cwd=setup_root_path)       
stdout, stderr = p.communicate()