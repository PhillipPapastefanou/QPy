import sys
import os
import subprocess
from time import perf_counter
import numpy as np
import pandas as pd
import subprocess
from copy import deepcopy
import shutil

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

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

# Output libraries
from src.postprocessing.qtd_multi_run_plot import Quincy_Multi_Run_Plot

if 'QUINCY' in os.environ:        
    QUINCY_ROOT_PATH = os.environ.get("QUINCY")
else:
    print("Environmental variable QUINCY is not defined")
    print("Please set QUINCY to the directory of your quincy root path")
    exit(99)
    
USER = os.environ.get("USER")

# Define the number of runs and variables
number_of_runs = 3
# Number of cpu cores to be used
NNODES = 1
NTASKS  = 3
RAM_IN_GB = 3
PARTITION = 'work'

OUTPUT_DIRECTORY = "03_example"

# Path where all the simulation data will be saved
RUN_DIRECTORY = os.path.join("/Net/Groups/BSI/scratch/atto_school", USER, 'simulations', OUTPUT_DIRECTORY)

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


# Parse user git information
user_git_info = UserGitInformation(QUINCY_ROOT_PATH, 
                                           RUN_DIRECTORY, 
                                           "ATTO")      

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

# Now we rescale parameters
sand_fracs = [0.2, 0.3, 0.4]
clay_fracs = [0.4, 0.5, 0.6]

print(RUN_DIRECTORY)

# We create a multi quincy run object
quincy_multi_run = Quincy_Multi_Run(RUN_DIRECTORY)

# We loop through the number of slice
for i in range(0, number_of_runs):
    
    # We create a copy of the lctlibfile...
    lctlib = deepcopy(lctlib_base)
    nlm = deepcopy(namelist)

    nlm.spq_ctl.soil_sand.value = sand_fracs[i]
    nlm.spq_ctl.soil_clay.value = clay_fracs[i]
    nlm.spq_ctl.soil_silt.value = 1.0 - nlm.spq_ctl.soil_clay.value - nlm.spq_ctl.soil_sand.value
        

    user_git_info = UserGitInformation(QUINCY_ROOT_PATH, 
                                           os.path.join(RUN_DIRECTORY, "output", str(i)), 
                                           "ATTO")  

    #Create one QUINCY setup
    quincy_setup = Quincy_Setup(folder = os.path.join(RUN_DIRECTORY, "output", str(i)), 
                                namelist = nlm, 
                                lctlib = lctlib, 
                                forcing_path= forcing_file,
                                user_git_info= user_git_info)

    # Add to the setup creation
    quincy_multi_run.add_setup(quincy_setup)    

# Generate quincy setups
quincy_multi_run.generate_files()

df_parameter_setup = pd.DataFrame({
    "id": np.arange(number_of_runs),
    "fid": np.arange(number_of_runs),
    "sand_fracs": np.round(sand_fracs, 3),
    "clay_fracs": np.round(clay_fracs, 3),
})
df_parameter_setup.to_csv(os.path.join(RUN_DIRECTORY, "parameters.csv"), index=False)
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Quincy run scripts
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

GenerateSlurmScript(path         = RUN_DIRECTORY, 
                    ntasks       = NTASKS,
                    ram_in_gb    = RAM_IN_GB, 
                    nnodes       = NNODES, 
                    partition    = PARTITION)

shutil.copyfile(os.path.join(THIS_DIR, os.pardir, os.pardir,'src', 'quincy', 'run_scripts', 'run_mpi.py'), 
                             os.path.join(RUN_DIRECTORY, 'run_mpi.py'))

import time
time.sleep(1.0)

import subprocess
scriptpath = os.path.join(RUN_DIRECTORY, 'submit.sh')
p = subprocess.Popen(f'/usr/bin/sbatch {scriptpath}', 
                     shell=True, 
                     cwd=RUN_DIRECTORY,
                     stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True)       
stdout, stderr = p.communicate()

import re
match = re.search(r"Submitted batch job (\d+)", stdout)

if match:
    jobid = match.group(1)
    print(f"Captured job ID: {jobid}")
else: 
    raise RuntimeError(f"Could not parse job ID from sbatch output:\n{stdout}")
    
    
poll_interval = 10
# --- Poll with sacct until job is finished ---
final_states = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY"}
done = False
tstart = time.time()
while not done:
    print(f"Waiting for simulation to fininsh...({int(np.round(time.time()-tstart))}s)")
    res = subprocess.run(
        ["sacct", "-j", jobid, "--format=JobID,State", "--noheader"],
        capture_output=True,
        text=True
    )
    state_lines = [line.strip().split() for line in res.stdout.splitlines() if line.strip()]
    if state_lines:
        # Job may have multiple steps; pick the main one (exact jobid, not jobid.batch)
        for jid, state in state_lines:
            if jid == jobid and state in final_states:
                print(f"Job {jobid} finished with state: {state}")
                done = True
                break
    if done:
        break
    time.sleep(poll_interval)
    
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Postprocessing
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

print("Starting postprocessing...", end='')
qm_post_process = Quincy_Multi_Run_Plot(RUN_DIRECTORY)

qm_post_process.plot_variable("Q_ASSIMI", "gpp_avg", "D")
print('Done!')
