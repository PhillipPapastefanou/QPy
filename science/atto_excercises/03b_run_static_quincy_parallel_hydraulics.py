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
from src.quincy.IO.ParamlistWriter import ParamlistWriter
from src.quincy.IO.ParamlistWriter import Paramlist
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
NTASKS  = number_of_runs
RAM_IN_GB = 12
PARTITION = 'work'

OUTPUT_DIRECTORY = "03_static_parallel_hyd"

# Path where all the simulation data will be saved
RUN_DIRECTORY = os.path.join("/Net/Groups/BSI/scratch/atto_school", USER, 'simulations', OUTPUT_DIRECTORY)

# We need a base namelist and lctlib which we then modify accordingly
namelist_root_path = os.path.join(THIS_DIR, "namelist_atto_base.slm")
lctlib_root_path = os.path.join(QUINCY_ROOT_PATH, 'data', 'lctlib_quincy_nlct14.def')
forcing_file = '/Net/Groups/BSI/work_scratch/ppapastefanou/ATTO_forcing/static/ATTO_s_2000-2023.dat'

# Parse base namelist path
nlm_reader = NamelistReader(namelist_root_path)
nlm_base = nlm_reader.parse()

pft_id = nlm_base.vegetation_ctl.plant_functional_type_id.value
pft = PftQuincy(pft_id)

# Parse base lctlib path
lctlib_reader = LctlibReader(lctlib_root_path)
lctlib_base = lctlib_reader.parse()

paramslist_base = Paramlist()

# Parse user git information
user_git_info = UserGitInformation(QUINCY_ROOT_PATH, 
                                           RUN_DIRECTORY, 
                                           "ATTO")      

# Apply the testbed configuration
ApplyDefaultSiteLevel(namelist=nlm_base)

# Limit output variables
nlm_base.base_ctl.file_sel_output_variables.value = os.path.join(QUINCY_ROOT_PATH, 'data', 'basic_output_variables.txt')

# C only
nlm_base.vegetation_ctl.veg_bnf_scheme.value = VegBnfScheme.UNLIMITED
nlm_base.vegetation_ctl.leaf_stoichom_scheme.value = LeafStoichomScheme.FIXED
nlm_base.soil_biogeochemistry_ctl.flag_sb_prescribe_po4.value = True
nlm_base.soil_biogeochemistry_ctl.sb_bnf_scheme.value = SbBnfScheme.UNLIMITED
nlm_base.base_ctl.flag_slow_sb_pool_spinup_accelerator.value = False

# Static forcing setup
nlm_base.jsb_forcing_ctl.forcing_mode.value = ForcingMode.STATIC
nlm_base.base_ctl.forcing_file_start_yr.value = 2000
nlm_base.base_ctl.forcing_file_last_yr.value = 2023
nlm_base.base_ctl.output_end_last_day_year.value = 24
nlm_base.base_ctl.output_start_first_day_year.value = 1
nlm_base.jsb_forcing_ctl.simulation_length_number.value = 24
nlm_base.base_ctl.output_interval_pool.value = OutputIntervalPool.TIMESTEP
nlm_base.base_ctl.output_interval_flux.value = OutputIntervalPool.TIMESTEP

# This line is important so QUINCY know it is expecting a paramlist
nlm_base.base_ctl.set_parameter_values_from_file.value = True

# Turn on plant hydraulics
nlm_base.assimilation_ctl.gs_beta_type.value = GsBetaType.PLANT
nlm_base.phyd_ctl.use_plant_hydraulics.value = True

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Main code to be modified
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# Now we rescale parameters
psi_leaf_close = [ -1.0, -1.0, -1.0, -1.0]
gamma_stems = [400, 400, 400, 400]
k_xylem_sats = [8, 8 , 8, 8 ]


# We create a multi quincy run object
quincy_multi_run = Quincy_Multi_Run(RUN_DIRECTORY)

# We loop through the number of slice
for i in range(0, number_of_runs):
    
    # We create a copy of the lctlibfile...
    lctlib = deepcopy(lctlib_base)
    nlm = deepcopy(nlm_base)
    paramlist = deepcopy(paramslist_base)
    
    if i == 0:
        nlm.assimilation_ctl.gs_beta_type.value = GsBetaType.SOIL
        nlm.phyd_ctl.use_plant_hydraulics.value = False

    nlm.spq_ctl.soil_sand.value = 0.1
    nlm.spq_ctl.soil_clay.value = 0.8
    nlm.spq_ctl.soil_silt.value = 1.0 - nlm.spq_ctl.soil_clay.value - nlm.spq_ctl.soil_sand.value
    
    # paramlist.vegetation_ctl.fresp_growth.value = resp_coeffs[i] 
    # paramlist.vegetation_ctl.fresp_growth.parsed = True  
    
    lctlib[pft].psi50_leaf_close = psi_leaf_close[i] 
    lctlib[pft].slope_leaf_close = 1.5 
    
    lctlib[pft].kappa_stem = gamma_stems[i]
    lctlib[pft].kappa_leaf = 0.001
    lctlib[pft].k_xylem_sat = k_xylem_sats[i]
    lctlib[pft].root_scale = 200.0

    user_git_info = UserGitInformation(QUINCY_ROOT_PATH, 
                                           os.path.join(RUN_DIRECTORY, "output", str(i)), 
                                           "ATTO")  

    #Create one QUINCY setup
    quincy_setup = Quincy_Setup(folder = os.path.join(RUN_DIRECTORY, "output", str(i)), 
                                namelist = nlm, 
                                lctlib = lctlib, 
                                forcing_path= forcing_file,
                                user_git_info= user_git_info,
                                paramlist = paramlist)

    # Add to the setup creation
    quincy_multi_run.add_setup(quincy_setup)    

# Generate quincy setups
quincy_multi_run.generate_files()

df_parameter_setup = pd.DataFrame({
    "id": np.arange(number_of_runs),
    "fid": np.arange(number_of_runs),
    "resp_coeffs": np.round(psi_leaf_close, 3),

    # "sand_fracs": np.round(sand_fracs, 3),
    # "clay_fracs": np.round(clay_fracs, 3),
})
df_parameter_setup.to_csv(os.path.join(RUN_DIRECTORY, "parameters.csv"), index=False)
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Quincy run scripts
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
print(RUN_DIRECTORY)
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

qm_post_process.plot_variable_multi_time("Q_ASSIMI", "gpp_avg")
# qm_post_process.plot_variable_multi_time("Q_ASSIMI", "beta_gs", "D")
# qm_post_process.plot_variable_multi_time("VEG", "npp_avg", "D")
# qm_post_process.plot_variable_multi_time("VEG", "total_veg_c", "D")
# qm_post_process.plot_variable_multi_time("VEG", "LAI", "D")
# qm_post_process.plot_variable_multi_time("SPQ", "transpiration_avg", "D")
# qm_post_process.plot_variable_multi_time("SPQ", "evaporation_avg", "D")
# qm_post_process.plot_variable_multi_time("SPQ", "rootzone_soilwater_potential", "D")
# qm_post_process.plot_variable_multi_time("SB", "sb_total_c", "D")
# qm_post_process.plot_variable_multi_time("SB", "sb_total_som_c", "D")

qm_post_process.plot_variable_multi_time("PHYD", "psi_leaf_avg",)
qm_post_process.plot_variable_multi_time("PHYD", "psi_stem_avg")
qm_post_process.plot_variable_multi_time("PHYD", "stem_flow_avg")

# qm_post_process.plot_variable_multi_time("SB", "sb_total_c", "D")
# qm_post_process.plot_variable_multi_time("SB", "sb_total_som_c", "D")
#obs_pl_path = os.path.join(THIS_DIR, os.pardir, os.pardir, "data", "atto_psi_leaf", "Day1.csv")
#qm_post_process.plot_against_PSILEAF_variable_multi_time(obs_pl_path, g = 1)

print('Done!')
