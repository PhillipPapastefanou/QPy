import sys
rtpath ="/Net/Groups/BSI/work_scratch/ppapastefanou/data/QPy"
sys.path.append(rtpath)

from copy import deepcopy
import numpy as np
import pandas as pd
import os

from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.LctlibReader import LctlibReader
from src.quincy.base.PFTTypes import PftQuincy
from src.sens.base import Quincy_Setup
from src.sens.base import Quincy_Multi_Run
from src.sens.auxil import Subslicer
from src.sens.auxil import rescale
from src.sens.auxil import rescale_mean

from scipy.stats import qmc

rtpath = '/Net/Groups/BSI/work_scratch/ppapastefanou/data/quincy_hydraulics_eamon/'

# Classic sensitivity analysis where we are apply differnt Namelist or Lctlib files to ONE climate file
# The basic forcing path
forcing_file = rtpath + 'climate.dat'
# We need a base namelist and lctlib which we then modify accordingly
namelist_root_path = rtpath + 'namelist.slm'
lctlib_root_path = rtpath + 'lctlib_quincy_nlct14.def'
# Path where to save the setup
setup_root_path = "LH2_test"

# Parse base namelist path
nlm_reader = NamelistReader(namelist_root_path)
namelist_base = nlm_reader.parse()

# Parse base lctlibe path
lctlib_reader = LctlibReader(lctlib_root_path)
lctlib_base = lctlib_reader.parse()


#Obtain pft_id from namelist
pft_id = namelist_base.vegetation_ctl.plant_functional_type_id
pft = list(PftQuincy)[pft_id - 1]

# Dummy change to be reset to 500-1000 years
namelist_base.jsb_forcing_ctl.transient_spinup_years = 500

# Main code to be modified
# 2 Parameter latin hypercupe sensitivity calculation

# Define the number of runs and variables
number_of_runs = 10
number_of_variables = 2

# Create a latin hypercube sample that is distributed between 0-1
seed   = 123456789
sampler = qmc.LatinHypercube(d = number_of_variables, seed= seed)
sample = sampler.random(n = number_of_runs)
sample = sample.T

# Create a subslicer to make rescaling easier
slicer = Subslicer(array=sample)

# 1. Parameter psi50_xylem (standard value was around -3.0)
psi50_xylem_min = -6.0
psi50_xylem_max = -0.5

# 2. Parameter k_xylem_sat (standard value was 5000)
k_xylem_sat_min = 500
k_xylem_sat_max = 10000

# Now we rescale parameters
psi50s = rescale(slicer.get(), min = psi50_xylem_min, max = psi50_xylem_max)
k_xylem_sats = rescale(slicer.get(), min = k_xylem_sat_min, max = k_xylem_sat_max)

# We create a multi quincy run object
quincy_multi_run = Quincy_Multi_Run(setup_root_path)

# We loop through the number of slice
for i in range(0, number_of_runs):
    # We create a copy of the lctlibfile...
    lctlib = deepcopy(lctlib_base)

    #... and change the value of psi50
    # the float conversion in necessary to convert from a numpy numeric type to standard numeric python
    lctlib[pft].psi50_xylem = float(psi50s[i])
    lctlib[pft].k_xylem_sat = float(k_xylem_sats[i])

    #Create one QUINCY setup
    quincy_setup = Quincy_Setup(folder = os.path.join(setup_root_path, str(i)), namelist = namelist_base, lctlib = lctlib, forcing_path=forcing_file)

    # Add to the setup creation
    quincy_multi_run.add_setup(quincy_setup)

# Generate quincy setups
quincy_multi_run.generate_files()

#Important: we need to save the psi50s so that we can later identify which simulation belongs to which file
df_parameter_setup = pd.DataFrame(psi50s)
df_parameter_setup.columns = ['psi50_xylem']
df_parameter_setup['id'] = np.arange(0, number_of_runs)


df_parameter_setup.to_csv(os.path.join(setup_root_path, "parameters.csv"), index=False)

