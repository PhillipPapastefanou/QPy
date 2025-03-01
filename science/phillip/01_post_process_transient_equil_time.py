import sys
import os
import shutil
import subprocess
from time import perf_counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))
from copy import deepcopy
import numpy as np
import pandas as pd

from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.LctlibReader import LctlibReader
from src.quincy.base.PFTTypes import PftQuincy, PftFluxnet
from src.sens.base import Quincy_Setup
from src.sens.base import Quincy_Single_Run
from src.quincy.base.EnvironmentalInputTypes import *
from src.quincy.base.NamelistTypes import *

from src.postprocessing.qnc_std_output_factory import Output_format
from src.postprocessing.qnc_std_output_factory import QNC_std_output_factory

if 'QUINCY' in os.environ:        
    QUINCY_ROOT_PATH = os.environ.get("QUINCY")
else:
    print("Environmental variable QUINCY is not defined")
    print("Please set QUINCY to the directory of your quincy root path")
    exit(99)


# Path where all the simulation data will be saved
RUN_DIRECTORY = "output/01_transient_fluxnet"


if not os.path.exists(os.path.join(THIS_DIR, RUN_DIRECTORY)):
    print("No testbed output found")
    exit(99)

target_categories = []
format = Output_format.Single
output_factory = QNC_std_output_factory(root_path = os.path.join(THIS_DIR, RUN_DIRECTORY), 
                                        output_format=format,
                                        target_categories=target_categories)
output_factory.Calculate_std_output()
output_factory.Calculate_fluxnet_stat()
print("Finished!")