import unittest
import os
import glob
import sys
import subprocess
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.NamelistWriter import NamelistWriter
from src.quincy.base import Namelist

class Test_Namelist(unittest.TestCase):
    def test_namelist_reading(self):        
        namelist_default_path = os.path.join(           
        'tests', 'res', 'namelist.slm')
        
        nlm_reader = NamelistReader(namelist_default_path)
        
        namelist = nlm_reader.parse()        
        for cat_str in vars(namelist):
            cat = getattr(namelist, cat_str)            
            for var_str in vars(cat):
                item = getattr(cat, var_str)
                self.assertTrue(item.parsed, f"Did not parse {var_str} in {cat_str}")

if __name__ == "__main__":
    Test_Namelist().test_namelist_reading()