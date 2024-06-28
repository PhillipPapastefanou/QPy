from quinct_input_generator import QuincyInputGenerator
from misc_forcing_settings import Misc_Forcing_Settings
from misc_forcing_settings import ProjectionScenario

lon = 10.472944;
lat = 51.080587;


root_path = '/Users/pp/data/temp/forcing/'
settings = Misc_Forcing_Settings()
settings.co2_concentration_file = f'{root_path}GCP2023_co2_global.dat'
settings.co2_dC13_file = f'{root_path}delta13C_in_air_input4MIPs_GM_1850-2021_extrapolated.txt'
settings.co2_DC14_file = f'{root_path}Delta14C_in_air_input4MIPs_SHTRNH_1850-2021_extrapolated.txt'
settings.root_pdep_path = f'{root_path}P-DEP'
settings.root_ndep_path = f'{root_path}CESM-CAM'
settings.ndep_projection_scenario = ProjectionScenario.RCP126

forcing_generator = QuincyInputGenerator(settings)
forcing_generator.generate(lon=lon, lat=lat)
forcing_generator.Export_static_forcing()
