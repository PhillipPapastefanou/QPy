import unittest
import os
import glob
import sys
import subprocess
import multiprocessing
import xarray as xr
import numpy as np
import pandas as pd

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.LctlibReader import LctlibReader
from src.quincy.base import Namelist
from src.sens.base import Quincy_Setup
from src.sens.base import Quincy_Multi_Run
from src.quincy.base.EnvironmentalInputTypes import *
from src.quincy.base.NamelistTypes import ForcingMode
from src.quincy.base.EnvironmentalInput import EnvironmentalInputSite
from src.quincy.base.user_git_information import UserGitInformation
from src.quincy.run_scripts.default import ApplyDefaultSiteLevel
from time import perf_counter

class Test_U30(unittest.TestCase):    
    def init(self):
        if 'QUINCY' in os.environ:        
            self.QUINCY_ROOT_PATH = os.environ.get("QUINCY")
        else:
            print("Environmental variable QUINCY is not defined")
            print("Please set QUINCY to the directory of your quincy root path")
            exit(99)
            
        self.OUTPUT_DIR = 'output_u30'
        self.org_delta = 0.0
        self.qpy_delta = 0.0
        # CruNCEP test sites
        self.sites = ["ESP_01", "FIN_01", "HAI_01", "PUE_01", "US2_01"]
        
        
    def test_standard_config(self):
        
        self.init()
        
        # Classic sensitivity analysis where we are apply differnt Namelist or Lctlib files to ONE climate file
        # The basic forcing path
        # We need a base namelist and lctlib which we then modify accordingly
        namelist_root_path = os.path.join(self.QUINCY_ROOT_PATH,'contrib', 'namelist' ,'namelist.slm')
        lctlib_root_path = os.path.join(self.QUINCY_ROOT_PATH,'data', 'lctlib_quincy_nlct14.def')
        # Path where to save the setup
        setup_root_path = os.path.join(THIS_DIR, self.OUTPUT_DIR)

        # Parse base namelist path
        nlm_reader = NamelistReader(namelist_root_path)
        namelist_base = nlm_reader.parse()


        # CruNCEP forcing
        forcing = ForcingDataset.CRUNCEP
        # Use static forcing
        forcing_mode = ForcingMode.TRANSIENT

        env_input = EnvironmentalInputSite(
                                        forcing_mode=forcing_mode, 
                                        forcing_dataset=forcing)
        
        # Apply the testbed configuration 
        ApplyDefaultSiteLevel(namelist=namelist_base)        
        
        # Apply the standard selected output variables    
        namelist_base.base_ctl.file_sel_output_variables.value = os.path.join(self.QUINCY_ROOT_PATH,
                                                                              'data', 
                                                                              'basic_output_variables.txt')
        
        namelist_base.base_ctl.output_end_last_day_year.value = 4
        namelist_base.base_ctl.output_start_first_day_year.value = 1
        namelist_base.jsb_forcing_ctl.transient_simulation_start_year.value = 1901
        namelist_base.jsb_forcing_ctl.transient_spinup_start_year.value = 1901
        namelist_base.jsb_forcing_ctl.transient_spinup_end_year.value = 1930
        namelist_base.jsb_forcing_ctl.transient_spinup_years.value = 2
        namelist_base.jsb_forcing_ctl.simulation_length_number.value = 4
        

        
        
        # Parse paths of the forcing
        namelist_dicts, forcing_dicts = env_input.parse_multi_sites(namelist=namelist_base,
                                    sitelist= self.sites,
                                    site_list_type=SimulationSiteType.CUSTOM)        
        
        
        # Parse base lctlibe path
        lctlib_reader = LctlibReader(lctlib_root_path)
        lctlib_base = lctlib_reader.parse()
        
        quincy_multi_run = Quincy_Multi_Run(setup_root_path)
                
        for site in self.sites:
            
            # Generate user git info 
            user_git_info = UserGitInformation(self.QUINCY_ROOT_PATH, os.path.join(setup_root_path, "output", site), site)     
                    
            #Create one QUINCY setup
            quincy_setup = Quincy_Setup(folder = os.path.join(setup_root_path, "output", site), 
                                        namelist = namelist_dicts[site],
                                        lctlib = lctlib_base,
                                        forcing_path= forcing_dicts[site], 
                                        user_git_info= user_git_info)
            
            # Add to the setup creation
            quincy_multi_run.add_setup(quincy_setup)
            

    
            
        
        # Generate quincy setups
        quincy_multi_run.generate_files()
        

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
        # Quincy run scripts
        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        
        processes = []
        results_queue = multiprocessing.Queue() 
    
        # p1 = multiprocessing.Process(target= self.irun_org_quincy_test_bed, args = (self.QUINCY_ROOT_PATH, results_queue, self.org_delta))
        # p1.start()
        # p1.join()
        
        for site in self.sites:        
            p = multiprocessing.Process(target= self.irun_QPY_test_bed, args = (self.QUINCY_ROOT_PATH,
                                                                                os.path.join(setup_root_path, 'output', site),
                                                                                results_queue, self.qpy_delta))
            processes.append(p)
        
        # p1.start()
        for p in processes:  
            p.start() 
        
        # Wait for all processes to finish and collect results
        for p in processes:  
            p.join() 
            
        # Get results from the queue
        results = [results_queue.get() for _ in range(2)]       
   
        for i, (success, stdout, stderr) in enumerate(results):
            print(f"Results for quincy runs")
            if success:
                print("Success!")
            else:
                print("Failure!")
            self.assertTrue(success, stderr.decode() if stderr else "No error message.")

        print(f"Org runtime elapsed: {self.org_delta}")
        print(f"QPy runtime elapsed: {self.qpy_delta}")
        
        
        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
        # Quincy postprocessing
        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


    def irun_org_quincy_test_bed(self, QUINCY_ROOT_PATH, q, org_delta):
        
        t1 = perf_counter()
        quincy_u30_script_path = os.path.join(QUINCY_ROOT_PATH,"contrib", "site_level", "prepare_sim_quincy.sh")
        
        p = subprocess.Popen([quincy_u30_script_path, "-u", "30"])

        stdout, stderr = p.communicate()
       
                
        returncode = p.returncode
        
        try:
            # ... (Quincy execution)
            if returncode == 0:
                q.put((True, stdout, stderr)) # Put results in the queue
            else:
                q.put((False, None, stderr))
        except Exception as e:
            q.put((False, None, str(e)))
            
            
            
            
        t2 = perf_counter()
        org_delta = t2 - t1

    def irun_QPY_test_bed(self, QUINCY_ROOT_PATH, setup_root_path, q, qpy_delta):
        
        t1 = perf_counter()
        quincy_binary_path = os.path.join(QUINCY_ROOT_PATH,"x86_64-gfortran", "bin", "land.x")
        
        p = subprocess.Popen(quincy_binary_path,
                             cwd=setup_root_path)
        
        stdout, stderr = p.communicate()
        returncode = p.returncode
        
        try:
            # ... (Quincy execution)
            if returncode == 0:
                q.put((True, stdout, stderr)) # Put results in the queue
            else:
                q.put((False, None, stderr))
        except Exception as e:
            q.put((False, None, str(e)))
        
        
        t2 = perf_counter()
        qpy_delta = t2 - t1
        
    def compare_outputs(self):
        
        base_ref_path = "/Net/Groups/BSI/work/quincy/model/reference_runs/cruncepv7_subset_u30_31/20250220_1_develop_342ef5f8"        
        ref_path = os.path.join(base_ref_path,'exp_30_progress_options_short_transient_cruncep_ssm_342ef5f8/')
        
        if not os.path.exists(ref_path):
            print("Could not find usecase 30 ref output")
            print("Stopping comparison")
            exit(99)
        
        print("Comparing Vegetation output...")
        
        for site in self.sites:
            print(f"Testing {site}: ")
            df_org = pd.read_csv(os.path.join(ref_path, site , "output", "vegpoolC_daily.txt"), sep= "\s+")
            org_veg_c = df_org['Total_C'].values
            
            ds_new = xr.open_dataset(os.path.join(THIS_DIR, self.OUTPUT_DIR, "output", site,"VEG_transient_daily.nc"), decode_times=True)
            new_veg_c = ds_new['total_veg_c'][:].values
               
                
            print(f"Total carbon pools: QPy({new_veg_c[-1]}) vs Org({org_veg_c[-1]})")
            
            min_diff = np.min(new_veg_c[:]- org_veg_c[:])  
            
            self.assertAlmostEqual(min_diff, 0.0, 4, "Carbon pools do not match to 4 digits")  
            
            self.assertGreater(0.1, min_diff)        
    
        ds_new.close()
        
        print("Done!")

        
        
if __name__ == "__main__":
    tu30 = Test_U30()
    tu30.init()
    tu30.test_standard_config()
    
    tu30.compare_outputs()
    
    
    