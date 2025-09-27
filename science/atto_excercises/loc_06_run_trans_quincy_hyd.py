import sys
import os
import subprocess
from time import perf_counter
import numpy as np
import pandas as pd
from copy import deepcopy


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

RT_DIR = os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir)
QPY_DIR = os.path.join(THIS_DIR, os.pardir, os.pardir)
RESULT_DIR = os.path.join(RT_DIR, "results")

from pathlib import Path


# Read paths from your metadata files
with open(os.path.join(RESULT_DIR, "data_files.txt")) as f:
    data_files = [Path(line.strip()) for line in f if line.strip()]

with open(os.path.join(RESULT_DIR, "python_path.txt")) as f:
    python_path = Path(f.read().strip())

with open(os.path.join(RESULT_DIR, "quincy_path.txt")) as f:
    quincy_path = Path(f.read().strip())

# Assign them to variables
data_transient = data_files[0]
data_static = data_files[1]
data_nee_obs = data_files[2]


from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.LctlibReader import LctlibReader
from src.quincy.base.PFTTypes import PftQuincy, PftFluxnet
from src.sens.base import Quincy_Setup
from src.sens.base import Quincy_Multi_Run
from src.quincy.IO.ParamlistWriter import Paramlist
from src.quincy.base.EnvironmentalInputTypes import *
from src.quincy.base.NamelistTypes import *
from src.quincy.base.EnvironmentalInput import EnvironmentalInputSite
from src.quincy.base.user_git_information import UserGitInformation
from src.quincy.run_scripts.default import ApplyDefaultSiteLevel

# Output libraries
from src.postprocessing.qtd_multi_run_plot import Quincy_Multi_Run_Plot



# Path where all the simulation data will be saved
RUN_DIRECTORY = os.path.join(QPY_DIR, "simulations", "tes_t_hyd") 

QUINCY_ROOT_PATH = os.path.join(os.path.dirname(os.path.dirname(quincy_path)), "quincy")
print(QUINCY_ROOT_PATH)
# We need a base namelist and lctlib which we then modify accordingly
namelist_root_path = os.path.join(THIS_DIR, "namelist_atto_base.slm")
lctlib_root_path = os.path.join(QUINCY_ROOT_PATH, 'data', 'lctlib_quincy_nlct14.def')
forcing_file = data_transient   

# Parse base namelist path
nlm_reader = NamelistReader(namelist_root_path)
nlm_base = nlm_reader.parse()



# Parse base lctlib path
lctlib_reader = LctlibReader(lctlib_root_path)
lctlib_base = lctlib_reader.parse()

paramslist_base = Paramlist()


# Path where to save the setup
setup_root_path =  RUN_DIRECTORY

# Parse user git information
user_git_info = UserGitInformation(QUINCY_ROOT_PATH, 
                                           setup_root_path, 
                                           'ATTO')      

# Apply the testbed configuration
ApplyDefaultSiteLevel(namelist=nlm_base)

pft_id = nlm_base.vegetation_ctl.plant_functional_type_id.value
pft = PftQuincy(pft_id)

# Limit output variables
nlm_base.base_ctl.file_sel_output_variables.value = os.path.join(QUINCY_ROOT_PATH, 'data', 'basic_output_variables.txt')

# C only
nlm_base.vegetation_ctl.veg_bnf_scheme.value = VegBnfScheme.UNLIMITED
nlm_base.vegetation_ctl.leaf_stoichom_scheme.value = LeafStoichomScheme.FIXED
nlm_base.soil_biogeochemistry_ctl.flag_sb_prescribe_po4.value = True
nlm_base.soil_biogeochemistry_ctl.sb_bnf_scheme.value = SbBnfScheme.UNLIMITED
nlm_base.base_ctl.flag_slow_sb_pool_spinup_accelerator.value = False
# Transient forcing setup
nlm_base.jsb_forcing_ctl.forcing_mode.value = ForcingMode.TRANSIENT
nlm_base.base_ctl.output_end_last_day_year.value = 123
nlm_base.base_ctl.output_start_first_day_year.value = 1
nlm_base.jsb_forcing_ctl.transient_simulation_start_year.value = 1901
nlm_base.jsb_forcing_ctl.transient_spinup_start_year.value = 1901
nlm_base.jsb_forcing_ctl.transient_spinup_end_year.value = 1930
nlm_base.jsb_forcing_ctl.transient_spinup_years.value = 200
nlm_base.jsb_forcing_ctl.simulation_length_number.value = 123
nlm_base.base_ctl.fluxnet_type_transient_timestep_output.value = True
nlm_base.base_ctl.fluxnet_static_forc_start_yr.value = 2000
nlm_base.base_ctl.fluxnet_static_forc_last_yr.value = 2023
nlm_base.base_ctl.forcing_file_start_yr.value = 1901
nlm_base.base_ctl.forcing_file_last_yr.value = 2023

# This line is important so QUINCY know it is expecting a paramlist
nlm_base.base_ctl.set_parameter_values_from_file.value = True


# Turn on plant hydraulics
nlm_base.assimilation_ctl.gs_beta_type.value = GsBetaType.PLANT
nlm_base.phyd_ctl.use_plant_hydraulics.value = True


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Main code to be modified
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# Now we rescale parameters
psi_leaf_close = [ -2.0, -1.75, -1.5, -2.0]
#resp_coeffs = [0.1, 0.5, 0.99]
# sand_fracs = [0.3, 0.3, 0.3]
# clay_fracs = [0.5, 0.5, 0.5]
gamma_stems = [300, 150, 100, 600]
k_xylem_sats = [3, 2.5 , 5, 5 ]

number_of_runs = len(k_xylem_sats)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Do not modify below
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# We create a multi quincy run object
quincy_multi_run = Quincy_Multi_Run(RUN_DIRECTORY)

# We loop through the number of slice
for i in range(0, number_of_runs):
    
    # We create a copy of the lctlibfile...
    lctlib = deepcopy(lctlib_base)
    nlm = deepcopy(nlm_base)
    paramlist = deepcopy(paramslist_base)

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
    #"resp_coeffs": np.round(resp_coeffs, 3),
    # "sand_fracs": np.round(sand_fracs, 3),
    # "clay_fracs": np.round(clay_fracs, 3),
})
df_parameter_setup.to_csv(os.path.join(RUN_DIRECTORY, "parameters.csv"), index=False)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Quincy run scripts
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

import subprocess
import numpy as np
from time import perf_counter
n_cores = os.cpu_count()

print(f"System has {n_cores} cores; launching {number_of_runs} processes in parallel.")
t1 = perf_counter()
procs = []
# launch 3 processes in parallel
for i in range(number_of_runs):
    p = subprocess.Popen(
        [quincy_path],
        cwd=os.path.join(setup_root_path, "output", str(i)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    procs.append(p)

# wait for all to finish and collect results
for i, p in enumerate(procs):
    stdout, stderr = p.communicate()
    print(f"Run {i} finished with code {p.returncode}")
    if stdout:
        print(stdout.decode())
    if stderr:
        print(stderr.decode())

t2 = perf_counter()
print(f"Elapsed: {np.round(t2 - t1)} seconds.")

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Postprocess
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

# print("Starting postprocessing...", end='')
# qm_post_process = Quincy_Multi_Run_Plot(RUN_DIRECTORY, data_nee_obs)

# qm_post_process.plot_variable_multi_time("Q_ASSIMI", "gpp_avg", "D")
# qm_post_process.plot_variable_multi_time("Q_ASSIMI", "beta_gs", "D")
# qm_post_process.plot_variable_multi_time("VEG", "npp_avg", "D")
# qm_post_process.plot_variable_multi_time("VEG", "total_veg_c", "D")
# qm_post_process.plot_variable_multi_time("VEG", "LAI", "D")
# qm_post_process.plot_variable_multi_time("SPQ", "transpiration_avg", "D")
# qm_post_process.plot_variable_multi_time("SPQ", "evaporation_avg", "D")
# qm_post_process.plot_variable_multi_time("SPQ", "rootzone_soilwater_potential", "D")

# qm_post_process.plot_variable_multi_time("PHYD", "psi_leaf_avg", "D")
# qm_post_process.plot_variable_multi_time("PHYD", "psi_stem_avg", "D")
# qm_post_process.plot_variable_multi_time("PHYD", "stem_flow_avg", "D")

# qm_post_process.plot_variable_multi_time("SB", "sb_total_c", "D")
# qm_post_process.plot_variable_multi_time("SB", "sb_total_som_c", "D")

print('Done!')
