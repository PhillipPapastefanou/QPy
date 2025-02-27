import sys
import os
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir))

import unittest
from parsing.test_namelist_parsing import Test_Namelist
from runs.test_testbed import Test_Test_Bed
from runs.test_u30 import Test_U30
from runs.test_u31 import Test_U31

from post_process.test_post_test_bed import Test_Post_Process_Test_Bed

if __name__ == '__main__':
    unittest.main()
