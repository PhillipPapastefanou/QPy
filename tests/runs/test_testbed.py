import unittest
import os
import glob
import sys
import subprocess
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
from examples.sens.default_testbed import ApplyDefaultTestbed


class Test_Test_Bed(unittest.TestCase):
    def test_standard_config(self):
        QUINCY_ROOT_PATH = '/Net/Groups/BSI/work_scratch/ppapastefanou/src/quincy'
        OUTPUT_DIR = 'output'

        # Classic sensitivity analysis where we are apply differnt Namelist or Lctlib files to ONE climate file
        # The basic forcing path
        # We need a base namelist and lctlib which we then modify accordingly
        namelist_root_path = os.path.join(QUINCY_ROOT_PATH,'contrib', 'namelist' ,'namelist.slm')
        lctlib_root_path = os.path.join(QUINCY_ROOT_PATH,'data', 'lctlib_quincy_nlct14.def')
        # Path where to save the setup
        setup_root_path = os.path.join(THIS_DIR, OUTPUT_DIR)

        # Parse base namelist path
        nlm_reader = NamelistReader(namelist_root_path)
        namelist_base = nlm_reader.parse()


        # Fluxnet3 forcing
        forcing = ForcingDataset.FLUXNET3
        # Fluxnet3 sites
        sites = ["DE-Hai"]
        # Use static forcing
        forcing_mode = ForcingMode.STATIC

        env_input = EnvironmentalInputSite(sitelist=sites,
                                        forcing_mode=forcing_mode, 
                                        forcing_dataset=forcing)

        # Parse paths of the forcing
        env_input.parse_single_site(namelist=namelist_base)

        # Apply the testbed configuration 
        ApplyDefaultTestbed(namelist=namelist_base)

        # Parse base lctlibe path
        lctlib_reader = LctlibReader(lctlib_root_path)
        lctlib_base = lctlib_reader.parse()
        
        
        # We create a single quincy setup
        quincy_single_run_config = Quincy_Single_Run(setup_root_path)

        #Create one QUINCY setup
        quincy_setup = Quincy_Setup(folder = setup_root_path,
                                    namelist = namelist_base, 
                                    lctlib = lctlib_base, forcing_path=env_input.forcing_file)
        # Export setup
        quincy_single_run_config.set_setup(quincy_setup)
        quincy_single_run_config.generate_files()
        
        
        quincy_binary_path = os.path.join(QUINCY_ROOT_PATH,"x86_64-gfortran", "bin", "land.x")
        
        p = subprocess.Popen(quincy_binary_path,
                             cwd=setup_root_path)
        
        stdout, stderr = p.communicate()
        returncode = p.returncode
        
        if returncode == 0:
            print("Quincy executed successfully.")

        else:
            print(f"Quincy failed with return code {returncode}")
            if stderr:
                print("Error:", stderr.decode())  


if __name__ == "__main__":
    Test_Test_Bed().test_standard_config()
    #Test_Namelist().test_check_SimPHony_tests_exists()