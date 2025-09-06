import sys
import os
import shutil
import subprocess
from time import perf_counter

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir, os.pardir))
from copy import deepcopy
import numpy as np
import pandas as pd

from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.NamelistWriter import NamelistWriter
from src.quincy.base.EnvironmentalInputTypes import *
from src.quincy.base.NamelistTypes import *
from src.quincy.run_scripts.default import ApplyDefaultSiteLevel

if 'QUINCY' in os.environ:        
    QUINCY_ROOT_PATH = os.environ.get("QUINCY")
else:
    print("Environmental variable QUINCY is not defined")
    print("Please set QUINCY to the directory of your quincy root path")
    exit(99)

site = "ATTO"
# Use static forcing
forcing_mode = ForcingMode.TRANSIENT


# We need a base namelist and lctlib which we then modify accordingly
# This is the Manaus quincy generated namelist. We will override it with atto data
namelist_root_path = "/User/homes/ppapastefanou/ATTO-BR2_test/namelist_fluxnet_mao2.slm"


# Parse base namelist path
nlm_reader = NamelistReader(namelist_root_path)
namelist_base = nlm_reader.parse()


# Apply the testbed configuration 
ApplyDefaultSiteLevel(namelist=namelist_base)


from src.forcing.site_derived.converter.atto_site_data import Quincy_ATTO_Site_Data
from src.forcing.site_derived.converter.settings import ProjectionScenario, Settings, Verbosity

set = Settings()
set.co2_concentration_file = '/Net/Groups/BSI/people/ppapastefanou/climate_aux/co2/GCP2023_co2_global.dat'
set.co2_dC13_file = '/Net/Groups/BSI/people/ppapastefanou/climate_aux/co2/delta13C_in_air_input4MIPs_GM_1850-2021_extrapolated.txt'
set.co2_DC14_file = '/Net/Groups/BSI/people/ppapastefanou/climate_aux/co2/Delta14C_in_air_input4MIPs_SHTRNH_1850-2021_extrapolated.txt'

set.root_ndep_path = "/Net/Groups/BSI/data/OCN/input/gridded/NDEP/CESM-CAM"
set.ndep_projection_scenario = ProjectionScenario.RCP585
set.root_pdep_path ="/Net/Groups/BSI/work/quincy/model/InputDataSources/P-DEP"

set.lithology_map_path = "/Net/Groups/BSI/data/datastructure_bgi_cpy/grid/Global/0d50_static/GLiM/v1_0/Data/GLim.720.360.nc"
set.soil_grid_database_path = "/Net/Groups/BSI/data/datastructure_bgi_cpy/grid/Global/0d10_static/soilgrids/v0_5_1/Data"
set.phosphorus_input_path = "/Net/Groups/BSI/data/datastructure_bgi_cpy/grid/Global/0d50_static/Phosphorous/v2014_06/Data"
set.qmax_file = "/Net/Groups/BSI/people/ppapastefanou/data/qmax_org_values_per_nwrb_category_20180515.csv"

set.verbosity = Verbosity.Info
#set.root_output_path = "/Net/Groups/BSI/work_scratch/ppapastefanou/FLUXNET_QUINCY_test"
set.root_output_path = "/Net/Groups/BSI/work_scratch/ppapastefanou/ATTO_forcing"
set.first_transient_forcing_year = 1901

atto_lon = -59.005
atto_lat = -2.15
qsd = Quincy_ATTO_Site_Data(lon= atto_lon, lat = atto_lat, settings=set)
qsd.Parse_Environmental_Data()

namelist_base.soil_biogeochemistry_ctl.soil_p_labile.value = qsd.P_soil_labile.item()
namelist_base.soil_biogeochemistry_ctl.soil_p_slow.value = qsd.P_soil_slow.item()
namelist_base.soil_biogeochemistry_ctl.soil_p_occluded.value = qsd.P_soil_occlud.item()
namelist_base.soil_biogeochemistry_ctl.soil_p_primary.value = qsd.P_soil_primary.item()
namelist_base.soil_biogeochemistry_ctl.qmax_org_fine_particle.value = qsd.Q_max_org
namelist_base.soil_biogeochemistry_ctl.nwrb_taxonomy_class.value= qsd.Taxnwrb
namelist_base.soil_biogeochemistry_ctl.usda_taxonomy_class.value = qsd.Taxousda

nlm_writer = NamelistWriter(namelist_base)
nlm_writer.export( "/User/homes/ppapastefanou/ATTO-BR2_test/namelist_atto_base.slm")





