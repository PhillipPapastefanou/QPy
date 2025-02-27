

import unittest
import os
import glob
import sys
import subprocess
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

from src.postprocessing.qnc_std_output_factory import Output_format
from src.postprocessing.qnc_std_output_factory import QNC_std_output_factory

class Test_Post_Process_Test_Bed(unittest.TestCase):
    def init(self):
        if 'QUINCY' in os.environ:        
            self.QUINCY_ROOT_PATH = os.environ.get("QUINCY")
        else:
            print("Environmental variable QUINCY is not defined")
            print("Please set QUINCY to the directory of your quincy root path")
            exit(99)
                    
    def test_standard_output(self):
        exp_path = os.path.join(THIS_DIR, os.pardir, 'runs','output')
        
        if not os.path.exists(exp_path):
            print("No testbed output found")
            exit(99)
        
        target_categories = []
        format = Output_format.Single
        output_factory = QNC_std_output_factory(exp_path, output_format=format, target_categories=target_categories)
        output_factory.Calculate_std_output()
        output_factory.Calculate_fluxnet_stat()
        print("Finished!")
        
if __name__ == "__main__":
    ttb = Test_Post_Process_Test_Bed()
    ttb.init()
    ttb.test_standard_output()