import sys
import os
import shutil
import subprocess
from time import perf_counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir))
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
NMAXTASKS  = 150
# Path where all the simulation data will be saved
RAM_IN_GB = 4


names = ["df_ind", "df_psi_stem_ind", "df_psi_stem_leaf_ind", "df_psi_stem_leaf_stem_flow_ind"]
for name in names:

    n_soil_combs = 1
    qpf = QuincyPathFinder()
    QUINCY_ROOT_PATH = qpf.quincy_root_path

    PARTITION = 'work'
    INPUT_DIRECTORY =  "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/63_run_transient_3days/"
    RUN_DIRECTORY =  f"/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/isimip/ismip_selection_63_res_{name}/"

    setup_root_path = os.path.join(THIS_DIR, RUN_DIRECTORY)

    ISIMIP_CLIM_PATH = "/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/ISIMIP_3b/QUINCY_ready/"
    LOCATION = "DE-Hai"
    MODELS = ["mri-esm2-0","mpi-esm1-2", "ipsl-cm6a", "gfdl-esm4" ,"ukesm1-0"]
    SCENARIOS = ['ssp126', 'ssp370', 'ssp585']

    df_run = pd.read_csv(os.path.join(INPUT_DIRECTORY, "post", "ana", f"{name}.csv"))
    run_ids = df_run['fid'].values

    print(run_ids)

    # Sanity check
    if os.path.realpath(INPUT_DIRECTORY) == os.path.realpath(setup_root_path):
        print("Run and input directories should NOT be the same")
        exit(-1)
    
    if os.path.exists(setup_root_path):
        shutil.rmtree(setup_root_path)
        
        
    # We create a single quincy setup
    quincy_multi_run = Quincy_Multi_Run(setup_root_path)

    nruns = 0
    for model in MODELS:
        for scenario in SCENARIOS:
            
            climate_dat_file = os.path.join(ISIMIP_CLIM_PATH, rf"forcing_{model}_{scenario}_{LOCATION}.dat" )
            sub_run_dir = os.path.join(setup_root_path, model, scenario)
                    
            os.makedirs(sub_run_dir, exist_ok=True)
            os.makedirs(os.path.join(sub_run_dir, "output"), exist_ok=True)

            for id in run_ids:            
                scen_dir = os.path.join(INPUT_DIRECTORY,"output", str(id))    
                rerun_dir = os.path.join(sub_run_dir, "output", str(id))
                os.makedirs(rerun_dir, exist_ok=True)
                
                namelist_path = os.path.join(scen_dir, "namelist.slm")
                lctlib_path = os.path.join(scen_dir, "lctlib_quincy_nlct14.def")
                
                
                
                # shutil.copy(os.path.join(scen_dir, "namelist.slm"), 
                #             new_namelist_path)
                # shutil.copy(os.path.join(scen_dir, "lctlib_quincy_nlct14.def"), 
                #             os.path.join(rerun_dir, "lctlib_quincy_nlct14.def"))
                
                # shutil.copy(os.path.join(scen_dir, "parameter_slm_run.list"),
                #             os.path.join(rerun_dir, "parameter_slm_run.list"))
                
                forcing_file = climate_dat_file        
                lctlib_reader = LctlibReader(lctlib_path)
                lctlib_base = lctlib_reader.parse()

                nlm_reader = NamelistReader(namelist_path)
                namelist_base = nlm_reader.parse()
                
                
                pft_id = namelist_base.vegetation_ctl.plant_functional_type_id.value
                pft = PftQuincy(pft_id)
                lctlib_base[pft].g_res = 0.001 
                
                paramlist = Paramlist()
                paramlist.phenology_ctl.gdd_t_air_threshold.value = 8.0
                paramlist.phenology_ctl.gdd_t_air_threshold.parsed = True
                        
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
                                                os.path.join(rerun_dir), 
                                                site)  
            
                #Create one QUINCY setup
                quincy_setup = Quincy_Setup(folder = os.path.join(rerun_dir), 
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
    quincy_binary_path = os.path.join(QUINCY_ROOT_PATH, "x86_64-gfortran", "bin", "land.x")

    GenerateSlurmScriptArrayBased(
                        ntasks        = nruns,
                        path          = setup_root_path,
                        quincy_binary = quincy_binary_path,
                        ram_in_gb     = RAM_IN_GB, 
                        ntasksmax     = NMAXTASKS, 
                        partition     = PARTITION,
                        python        = python_ex)

    shutil.copyfile(os.path.join(THIS_DIR, os.pardir, os.pardir,  os.pardir, 'src', 'quincy', 'run_scripts', 
                                'run_quincy_array.py'), 
                                os.path.join(setup_root_path, 'run_quincy_array.py'))

    time.sleep(1.0)

    import subprocess
    scriptpath = os.path.join(setup_root_path, 'submit.sh')
    p = subprocess.Popen(f'/usr/bin/sbatch {scriptpath}', shell=True, cwd=setup_root_path)       
    stdout, stderr = p.communicate()

