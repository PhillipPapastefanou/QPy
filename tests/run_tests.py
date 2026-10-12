import sys
import os
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir))

import unittest

from parsing.test_quincy_files_parsing import Test_QuincyFilesParsing
from runs.test_packages import TestRequiredPackages
from runs.test_find_quincy import TestQuincyPathsExist
from runs.test_testbed import Test_Test_Bed
from consistency.test_config_consistency import Test_ConfigConsistency
from consistency.test_forcing_checks import Test_ForcingChecks_Synthetic, Test_Era5LandBuild_Functions
#from post_process.test_post_test_bed import Test_Post_Process_Test_Bed

if __name__ == '__main__':
    unittest.main()
