import sys
import os
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir))

import unittest
from parsing.test_namelist_parsing import Test_Namelist
from runs.test_testbed import Test_Test_Bed
from runs.test_u30 import Test_U30
from runs.test_u31 import Test_U31

if __name__ == '__main__':
    unittest.main()
