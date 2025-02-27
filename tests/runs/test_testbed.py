import unittest
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
from src.quincy.base.EnvironmentalInputTypes import *
from src.quincy.base.NamelistTypes import ForcingMode
from src.quincy.base.EnvironmentalInput import EnvironmentalInputSite
from src.quincy.base.user_git_information import UserGitInformation
from src.quincy.run_scripts.default import ApplyDefaultTestbed
from time import perf_counter

class Test_Test_Bed(unittest.TestCase):
    
    def init(self):
        if 'QUINCY' in os.environ:        
            self.QUINCY_ROOT_PATH = os.environ.get("QUINCY")
        else:
            print("Environmental variable QUINCY is not defined")
            print("Please set QUINCY to the directory of your quincy root path")
            exit(99)
        self.OUTPUT_DIR = 'output'
        self.org_delta = 0.0
        self.qpy_delta = 0.0        
        
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


        # Fluxnet3 forcing
        forcing = ForcingDataset.FLUXNET3
        # Fluxnet3 sites
        site = "DE-Hai"
        # Use static forcing
        forcing_mode = ForcingMode.STATIC
        
        user_git_info = UserGitInformation(self.QUINCY_ROOT_PATH, 
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
        namelist_base.base_ctl.file_sel_output_variables.value = os.path.join(self.QUINCY_ROOT_PATH,
                                                                              'data', 
                                                                              'basic_output_variables.txt')

        # Parse base lctlibe path
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
        
        processes = []
        results_queue = multiprocessing.Queue() 
    
        p1 = multiprocessing.Process(target= self.irun_org_quincy_test_bed, args = (self.QUINCY_ROOT_PATH, results_queue, self.org_delta))
        p2 = multiprocessing.Process(target= self.irun_QPY_test_bed, args = (self.QUINCY_ROOT_PATH, setup_root_path, results_queue, self.qpy_delta))
        
        processes.append(p1)
        processes.append(p2)
        
        p1.start()
        p2.start()
        
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
        quincy_testbed_script_path = os.path.join(QUINCY_ROOT_PATH,"contrib", "test_bed", "run_quincy_testbed.sh")
        
        p = subprocess.Popen(quincy_testbed_script_path)
        
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
        
        print("Comparing Vegetation output...")
        
        ds_org = xr.open_dataset(os.path.join(self.QUINCY_ROOT_PATH, "contrib", "test_bed", "land", "VEG_static_timestep.nc"), decode_times=True)
        
        org_time = ds_org['time'][:]
        org_veg_c = ds_org['total_veg_c'][:]
        
        ds_new = xr.open_dataset(os.path.join(THIS_DIR, self.OUTPUT_DIR, "VEG_static_timestep.nc"), decode_times=True)
        new_time = ds_new['time'][:]
        new_veg_c = ds_new['total_veg_c'][:]
        
        self.assertEqual(org_time[0], new_time[0], "First time point does not match")
        
        self.assertEqual(org_time[-1], new_time[-1], "Last time point does not match")
        
        min_diff = np.min(new_veg_c[:] - org_veg_c[:])  
        
        self.assertAlmostEqual(min_diff, 0.0, 16)  
        
        self.assertGreater(0.1, min_diff)
        
        ds_org.close()
        ds_new.close()
        
        print("Done!")

        
        
if __name__ == "__main__":
    ttb = Test_Test_Bed()
    ttb.init()
    ttb.test_standard_config()
    ttb.compare_outputs()
    
    
    