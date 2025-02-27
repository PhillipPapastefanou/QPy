

import unittest
import os
import glob
import sys
import subprocess
from time import perf_counter
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

from src.postprocessing.qnc_std_output_factory import Output_format
from src.postprocessing.qnc_std_output_factory import QNC_std_output_factory
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

class Test_Post_Process_Test_Bed(unittest.TestCase):
    def init(self):
        if 'QUINCY' in os.environ:        
            self.QUINCY_ROOT_PATH = os.environ.get("QUINCY")
        else:
            print("Environmental variable QUINCY is not defined")
            print("Please set QUINCY to the directory of your quincy root path")
            exit(99)
            
    def test_run_test_bed(self):
        
        self.OUTPUT_DIR = 'output/static'

        # Classic sensitivity analysis where we are apply differnt Namelist or Lctlib files to ONE climate file
        # The basic forcing path
        # We need a base namelist and lctlib which we then modify accordingly
        namelist_root_path = os.path.join(self.QUINCY_ROOT_PATH,'contrib', 'namelist' ,'namelist.slm')
        lctlib_root_path = os.path.join(self.QUINCY_ROOT_PATH,'data', 'lctlib_quincy_nlct14.def')
        # Path where to save the setup
        self.setup_root_path = os.path.join(THIS_DIR, self.OUTPUT_DIR)

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
                                                self.setup_root_path, 
                                                site)      

        env_input = EnvironmentalInputSite(forcing_mode=forcing_mode, 
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
        quincy_single_run_config = Quincy_Single_Run(self.setup_root_path)

        #Create one QUINCY setup
        quincy_setup = Quincy_Setup(folder = self.setup_root_path,
                                    namelist = namelist_base, 
                                    lctlib = lctlib_base,
                                    forcing_path=forcing_file, 
                                    user_git_info= user_git_info)
        # Export setup
        quincy_single_run_config.set_setup(quincy_setup)
        quincy_single_run_config.generate_files()

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
        # Quincy run scripts
        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

        t1 = perf_counter()

        quincy_binary_path = os.path.join(self.QUINCY_ROOT_PATH, "x86_64-gfortran", "bin", "land.x")

        p = subprocess.Popen(quincy_binary_path,
                                cwd=self.setup_root_path)

        stdout, stderr = p.communicate()
        returncode = p.returncode

        t2 = perf_counter()
        print(f"Elapsed: {t2-t1} seconds.")
                            
    def test_post_process_std(self):
        
        if not os.path.exists(self.setup_root_path):
            print("No testbed output found")
            exit(99)
        
        target_categories = []
        format = Output_format.Single
        output_factory = QNC_std_output_factory(self.setup_root_path, output_format=format, target_categories=target_categories)
        output_factory.Calculate_std_output()
        output_factory.Calculate_fluxnet_stat()
        print("Finished!")
        
if __name__ == "__main__":
    ttb = Test_Post_Process_Test_Bed()
    ttb.init()
    ttb.test_run_test_bed()
    ttb.test_post_process_std()