import sys
import os
import subprocess
from time import perf_counter
import numpy as np
import pandas as pd
from copy import deepcopy


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))
from src.postprocessing.qtd_multi_run_plot import Quincy_Multi_Run_Plot
from src.postprocessing.qtd_multi_run_plot import SimPhase

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

qm_post_process = Quincy_Multi_Run_Plot(RUN_DIRECTORY, obs_path=data_nee_obs)

phases = [
    #SimPhase.SPINUP,
    #SimPhase.TRANSIENT,
    SimPhase.FLUXNETDATA
]

print("Postprocessing output...")
for phase in phases:
    print(f"SimPhase {phase.name}")
    # qm_post_process.plot_variable_multi_time("Q_ASSIMI", "gpp_avg", phase)
    # qm_post_process.plot_variable_multi_time("Q_ASSIMI", "beta_gs", phase)
    qm_post_process.plot_variable_multi_time("VEG", "npp_avg", phase)
    # qm_post_process.plot_variable_multi_time("VEG", "total_veg_c", phase)
    # qm_post_process.plot_variable_multi_time("VEG", "LAI", phase)
    # qm_post_process.plot_variable_multi_time("SPQ", "transpiration_avg", phase)
    # qm_post_process.plot_variable_multi_time("SPQ", "evaporation_avg", phase)
    # qm_post_process.plot_variable_multi_time("SPQ", "rootzone_soilwater_potential", phase)
    # # qm_post_process.plot_variable_multi_time("SB", "sb_total_c", phase)
    # # qm_post_process.plot_variable_multi_time("SB", "sb_total_som_c", phase) 
    qm_post_process.plot_variable_multi_time("PHYD", "psi_leaf_avg", phase)
    qm_post_process.plot_variable_multi_time("PHYD", "psi_stem_avg", phase)
    # qm_post_process.plot_variable_multi_time("PHYD", "stem_flow_avg", phase)

qm_post_process.plot_against_NEE_variable_multi_time()
obs_pl_path = os.path.join(THIS_DIR, os.pardir, os.pardir, "data", "atto_psi_leaf", "Day1.csv")
qm_post_process.plot_against_PSILEAF_variable_multi_time(obs_pl_path, g = 1)
qm_post_process.plot_against_PSILEAF_variable_multi_time(obs_pl_path, g = 2)