import sys
rtpath ="/Users/pp/Documents/Repos/QPy"
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

rtpath = '/Users/pp/data/quincy_hydraulics_eamon/'

# Classic sensitivity analysis where we are apply differnt Namelist or Lctlib files to ONE climate file
# The basic forcing path
forcing_file = rtpath + 'climate.dat'
# We need a base namelist and lctlib which we then modify accordingly
namelist_root_path = rtpath + 'namelist.slm'
lctlib_root_path = rtpath + 'lctlib_quincy_nlct14.def'
# Path where to save the setup
setup_root_path = "oaat_psi50_test"

# Parse base namelist path
nlm_reader = NamelistReader(namelist_root_path)
namelist_base = nlm_reader.parse()

# Parse base lctlibe path
lctlib_reader = LctlibReader(lctlib_root_path)
lctlib_base = lctlib_reader.parse()

#Obtain pft_id from namelist
pft_id = namelist_base.vegetation_ctl.plant_functional_type_id
pft = list(PftQuincy)[pft_id - 1]

# Main code to be modified
# One at a time sensitivity calculation
# First we pick a parameter for example psi50_xylem
# The standard value is -3.0 MPa
psi50_xylem =  -3.0

# We define min and max MPa
psi50_xylem_min = -6.0
psi50_xylem_max = -0.5

# Define the number of steps we want to slice
nslice = 10

# Now we can use numpy to create and array
psi50s = np.linspace(psi50_xylem_min, psi50_xylem_max, num=nslice)

#you could also do it manually:
#psi50s = np.array([-6.0, -3.0, -2.0, -1.0])

# We create a multi quincy run object
quincy_multi_run = Quincy_Multi_Run(setup_root_path)

# We loop through the number of slice
for i in range(0, nslice):
    # We create a copy of the lctlibfile...
    lctlib = deepcopy(lctlib_base)

    #... and change the value of psi50
    # the float conversion in necessary to convert from a numpy numeric type to standard numeric python
    lctlib[pft].psi50_xylem = float(psi50s[i])

    #Create one QUINCY setup
    quincy_setup = Quincy_Setup(folder = os.path.join(setup_root_path, str(i)), namelist = namelist_base, lctlib = lctlib, forcing_path=forcing_file)

    # Add to the setup creation
    quincy_multi_run.add_setup(quincy_setup)

# Generate quincy setups
quincy_multi_run.generate_files()

#Important: we need to save the psi50s so that we can later identify which simulation belongs to which file
df_parameter_setup = pd.DataFrame(psi50s)
df_parameter_setup.columns = ['psi50_xylem']
df_parameter_setup['id'] = np.arange(0, nslice)


df_parameter_setup.to_csv(os.path.join(setup_root_path, "parameters.csv"), index=False)

