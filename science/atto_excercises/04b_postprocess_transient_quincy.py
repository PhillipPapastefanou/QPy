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
from src.postprocessing.qtd_multi_run_plot import Quincy_Multi_Run_Plot
from src.postprocessing.qtd_multi_run_plot import SimPhase


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

OUTPUT_DIRECTORY = "04_transient"
#OUTPUT_DIRECTORY = "03_example"


obs_path = "/Net/Groups/BSI/work_scratch/ppapastefanou/atto_summerschool_25/data/ATTO_evaluation.csv"

# Path where all the simulation data will be saved
RUN_DIRECTORY = os.path.join("/Net/Groups/BSI/scratch/atto_school", USER, 'simulations', OUTPUT_DIRECTORY)

qm_post_process = Quincy_Multi_Run_Plot(RUN_DIRECTORY, obs_path=obs_path)

phases = [
    SimPhase.SPINUP,
    SimPhase.TRANSIENT,
    SimPhase.FLUXNETDATA
]

print("Postprocessing output...")
for phase in phases:
    print(f"SimPhase {phase.name}")
    qm_post_process.plot_variable_multi_time("Q_ASSIMI", "gpp_avg", phase)
    qm_post_process.plot_variable_multi_time("Q_ASSIMI", "beta_gs", phase)
    qm_post_process.plot_variable_multi_time("VEG", "npp_avg", phase)
    qm_post_process.plot_variable_multi_time("VEG", "total_veg_c", phase)
    qm_post_process.plot_variable_multi_time("VEG", "LAI", phase)
    qm_post_process.plot_variable_multi_time("SPQ", "transpiration_avg", phase)
    qm_post_process.plot_variable_multi_time("SPQ", "evaporation_avg", phase)
    qm_post_process.plot_variable_multi_time("SPQ", "rootzone_soilwater_potential", phase)
    qm_post_process.plot_variable_multi_time("SB", "sb_total_c", phase)
    qm_post_process.plot_variable_multi_time("SB", "sb_total_som_c", phase) 
    


qm_post_process.plot_against_NEE_variable_multi_time()