
import os
import glob
import sys
import subprocess
import multiprocessing
import xarray as xr
import numpy as np

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.LctlibReader import LctlibReader
from src.quincy.base import Namelist
from src.sens.base import Quincy_Setup
from src.sens.base import Quincy_Single_Run
from src.quincy.auxil.find_quincy_paths import QuincyPathFinder
from src.quincy.base.EnvironmentalInputTypes import *
from src.quincy.base.NamelistTypes import ForcingMode, OutputIntervalFlux
from src.quincy.base.EnvironmentalInput import EnvironmentalInputSite
from src.quincy.base.user_git_information import UserGitInformation
from src.quincy.run_scripts.default import ApplyDefaultTestbed
from src.quincy.base.PFTTypes import PftQuincy, PftFluxnet
from time import perf_counter


qpf = QuincyPathFinder()
QUINCY_ROOT_PATH = qpf.quincy_root_path
OUTPUT_DIR = os.path.join('output', '00_static_run')


# Classic sensitivity analysis where we are apply differnt Namelist or Lctlib files to ONE climate file
# The basic forcing path
# We need a base namelist and lctlib which we then modify accordingly
namelist_root_path = qpf.namelist_root_path
lctlib_root_path = qpf.lctlib_root_path
# Path where to save the setup
setup_root_path = os.path.join(THIS_DIR, OUTPUT_DIR)

# Parse base namelist path
nlm_reader = NamelistReader(namelist_root_path)
namelist_base = nlm_reader.parse()


# Fluxnet3 forcing
forcing = ForcingDataset.FLUXNET3
# Fluxnet3 sites
site = "DE-Hai"
# Use static forcing
forcing_mode = ForcingMode.STATIC

user_git_info = UserGitInformation(QUINCY_ROOT_PATH, 
                                    setup_root_path, 
                                    site)      

env_input = EnvironmentalInputSite(
                                forcing_mode=forcing_mode, 
                                forcing_dataset=forcing)

# Parse paths of the forcing
namelist_base, forcing_file = env_input.parse_single_site(namelist=namelist_base, site=site)

# Apply the testbed configuration 
ApplyDefaultTestbed(namelist=namelist_base)        

# Apply the standard selected output variables    
namelist_base.base_ctl.file_sel_output_variables.value = os.path.join(QUINCY_ROOT_PATH,
                                                                        'data', 
                                                                        'basic_output_variables.txt')





#Obtain pft_id from namelist
pft_id = namelist_base.vegetation_ctl.plant_functional_type_id.value
# This the PFT object you need to modifiy the LCTLIB file
pft = list(PftQuincy)[pft_id - 1]



# Parse base lctlib
lctlib_reader = LctlibReader(lctlib_root_path)
lctlib_base = lctlib_reader.parse()

# We create a single quincy setup
quincy_single_run_config = Quincy_Single_Run(setup_root_path)

#Create one QUINCY setup
quincy_setup = Quincy_Setup(folder = setup_root_path,
                            namelist = namelist_base, 
                            lctlib = lctlib_base,
                            forcing_path=forcing_file, 
                            user_git_info = user_git_info)

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