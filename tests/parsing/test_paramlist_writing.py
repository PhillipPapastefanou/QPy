import unittest
import os
import glob
import sys
import subprocess
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

from src.quincy.IO.ParamlistWriter import ParamlistWriter
from src.quincy.base.Paramlist import Paramlist

class Test_Paramlist(unittest.TestCase):
    def test_paramlist_parsing(self):        
     
        paramlist = Paramlist()     
        for cat_str in vars(paramlist):
            cat = getattr(paramlist, cat_str)            
            for var_str in vars(cat):
                item = getattr(cat, var_str)
                self.assertFalse(item.parsed, f"Did not parse {var_str} in {cat_str}")
        
        paramlist.phenology_ctl.gdd_t_air_threshold.value = 12.0
        paramlist.phenology_ctl.gdd_t_air_threshold.parsed = True
        
        writer = ParamlistWriter(paramlist)
        writer.export("parameter_slm.list")

if __name__ == "__main__":
    Test_Paramlist().test_paramlist_parsing()