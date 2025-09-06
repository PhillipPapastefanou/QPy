import sys
import os

sys.path.append("/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy")

from src.forcing.site_derived.converter.atto_forcing import Quincy_ATTO_Forcing
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
forcing_file = '/Net/Groups/BSI/work_scratch/ppapastefanou/atto_summerschool_25/data/ATTO_merged_gapfilled_2000_2023.csv'


quincy_atto_forcing = Quincy_ATTO_Forcing(settings=set)

quincy_atto_forcing.Parse_forcing(atto_lat, atto_lon, forcing_file)

#quincy_atto_forcing.Export_static_forcing()
quincy_atto_forcing.Export_transient_forcing()