import sys
rtpath ="/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy"
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
from src.quincy.base.NamelistTypes import GsBetaType
from src.quincy.base.NamelistTypes import SbModelScheme
from src.quincy.base.NamelistTypes import SbNlossScheme

from src.quincy.base.NamelistTypes import VegBnfScheme
from src.quincy.base.NamelistTypes import CanopyLayerScheme
from src.quincy.base.NamelistTypes import CanopyConductanceScheme
from src.quincy.base.NamelistTypes import BiomassAllocScheme
from src.quincy.base.NamelistTypes import LeafStoichomScheme
from src.quincy.base.NamelistTypes import SbAdsorbScheme

rtpath = '/Net/Groups/BSI/work_scratch/ppapastefanou/src/quincy'

# Exemplary forcing file
forcing_file =  '/Net/Groups/BSI/work_scratch/ppapastefanou/data/quincy_hydraulics_setup/clim/climate.dat'
# Classic sensitivity analysis where we are apply differnt Namelist or Lctlib files to ONE climate file
# The basic forcing path
# We need a base namelist and lctlib which we then modify accordingly
namelist_root_path = os.path.join(rtpath,'contrib', 'namelist' ,'namelist.slm')
lctlib_root_path = os.path.join(rtpath,'data', 'lctlib_quincy_nlct14.def')
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


# Dummy change to be reset to 500-1000 years
#namelist_base.jsb_forcing_ctl.transient_spinup_years = 500
namelist_base.base_ctl.file_sel_output_variables = os.path.join(rtpath,'data', 'basic_output_variables.txt')
namelist_base.phyd_ctl.use_plant_hydraulics = True
namelist_base.assimilation_ctl.gs_beta_type = GsBetaType.PLANT

namelist_base.soil_biogeochemistry_ctl.sb_model_scheme = SbModelScheme.SIMPLE_1D
namelist_base.soil_biogeochemistry_ctl.sb_nloss_scheme = SbNlossScheme.DYNAMIC
namelist_base.soil_biogeochemistry_ctl.flag_sb_prescribe_nh4 = False
namelist_base.soil_biogeochemistry_ctl.flag_sb_prescribe_no3 = False
namelist_base.soil_biogeochemistry_ctl.flag_sb_prescribe_po4 = True

namelist_base.vegetation_ctl.veg_bnf_scheme = VegBnfScheme.DYNAMIC
namelist_base.soil_biogeochemistry_ctl.flag_mycorrhiza = False
namelist_base.soil_biogeochemistry_ctl.flag_mycorrhiza_org = False
namelist_base.soil_biogeochemistry_ctl.flag_mycorrhiza_prim = False

namelist_base.assimilation_ctl.flag_t_resp_acclimation  = True
namelist_base.assimilation_ctl.flag_t_jmax_acclimation  = True
namelist_base.assimilation_ctl.flag_optimal_Nfraction   = False
namelist_base.assimilation_ctl.ncanopy                  = 10
namelist_base.assimilation_ctl.canopy_layer_scheme      = CanopyLayerScheme.FAPAR
namelist_base.assimilation_ctl.canopy_conductance_scheme= CanopyConductanceScheme.MEDLYN

namelist_base.vegetation_ctl.biomass_alloc_scheme = BiomassAllocScheme.FIXED
namelist_base.vegetation_ctl.leaf_stoichom_scheme = LeafStoichomScheme.FIXED
namelist_base.vegetation_ctl.flag_dynamic_roots= True
namelist_base.vegetation_ctl.flag_dynroots_h2o_n_limit = False
namelist_base.vegetation_ctl.flag_herbivory = False

namelist_base.spq_ctl.soil_depth = 5.7
namelist_base.spq_ctl.nsoil_water = 5
namelist_base.spq_ctl.nsoil_energy = 5

namelist_base.soil_biogeochemistry_ctl.sb_adsorp_scheme = SbAdsorbScheme.ECA_PART
namelist_base.base_ctl.flag_slow_sb_pool_spinup_accelerator = False

namelist_base.dist_fire_ctl.flag_dfire = False
namelist_base.base_ctl.forcing_file_start_yr = 1901
namelist_base.base_ctl.forcing_file_last_yr = 2012



# Main code to be modified
# One at a time sensitivity calculation
# First we pick a parameter for example psi50_xylem
# The standard value is -3.0 MPa
psi50_xylem =  -3.0

# We define min and max MPa
psi50_xylem_min = -6.0
psi50_xylem_max = -0.5

# Define the number of steps we want to slice
nslice = 4

# Now we can use numpy to create and array
#psi50s = np.linspace(psi50_xylem_min, psi50_xylem_max, num=nslice)

#you could also do it manually:
psi50s = np.array([-6.0, -3.0, -2.0, -1.0])

# We create a multi quincy run object
quincy_multi_run = Quincy_Multi_Run(setup_root_path)

# We loop through the number of slice
for i in range(0, nslice):
    # We create a copy of the lctlibfile...
    lctlib = deepcopy(lctlib_base)

    #... and change the value of psi50
    # the float conversion in necessary to convert from a numpy numeric type to standard numeric python
    lctlib[pft].psi50_xylem = float(psi50s[i])

    lctlib[pft].k_xylem_sat = 10.0

    lctlib[pft].kappa_leaf = 1.0

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