import sys
import os
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir))

import unittest
from parsing.test_namelist_parsing import Test_Namelist
from runs.test_testbed import Test_Test_Bed

if __name__ == '__main__':
    unittest.main()
