from enum import Enum


class ProjectionScenario(Enum):
    RCP126 = 1
    RCP585 = 2

class Verbosity(Enum):
    Error = 1
    Warning = 2
    Info = 3
    Full = 4

class Settings:
    def __init__(self):
        self.root_pdep_path = ""
        self.root_ndep_path = ""
        self.ndep_projection_scenario = ProjectionScenario.RCP585

        self.co2_concentration_file = ""
        self.co2_dC13_file = ""
        self.co2_DC14_file = ""

        self.soil_grid_database_path = ""
        self.phosphorus_input_path = ""
        self.qmax_file = ""
        self.verbosity = Verbosity.Info

        self.root_output_path = ""
        self.transient_forcing_folder_name = "transient"
        self.static_forcing_folder_name = "static"
        self.analysis_folder_name = "analysis"
        self.lithology_map_path = ""

        self.first_transient_forcing_year = 1901

        # Fluxnet Variables according to jnelson naming conventions
        self.fluxnet_forcing_columns = ['SWdown', 'LWdown', 'Tair', 'Precip', 'Qair', 'Psurf', 'Wind']


