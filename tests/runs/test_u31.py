import unittest
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))
sys.path.append(THIS_DIR)

from src.quincy.run_scripts.default import ApplyUseCase31
from quincy_test_utils import UseCaseTests


class Test_U31(UseCaseTests, unittest.TestCase):
    # QUINCY usecase 31 (short transient CNP, JSM soil model) on the CRUNCEP sites,
    # compared with the newest reference run, see quincy_test_utils.py
    USECASE = "31"
    OUTPUT_DIR = os.path.join(THIS_DIR, "output_u31")
    apply_usecase = staticmethod(ApplyUseCase31)


if __name__ == "__main__":
    unittest.main()
