from src.forcing.misc_forcing_settings import Misc_Forcing_Settings
from src.forcing.misc_forcing_settings import ProjectionScenario
import pickle
from enum import Enum



class Ui_Settings(object):
    def __init__(self):
        #To be parsed
        self.successfull_setup = False


        # Libs
        self.make_binary_path = ""
        self.cmake_binary_path = ""
        self.fortran_binary_path = ""
        self.cpp_binary_path = ""
        self.python_binary_path = ""


        self.root_ui_directory= ""
        self.directory_QPy = ""
        self.directory_forcing = ""
        self.directory_quincy = ""

        self.binary_weather_generator = ""
        self.binary_quincy = ""

        self.quincy_namelist_path = ""
        self.quincy_lctlib_path = ""

        # Constants
        self.monthly_forcing_fname = "monthly_forcing.csv"
        self.subdaily_forcing_fname = "subdaily_forcing.csv"
        self.quincy_forcing_fname = "climate.dat"
        self.site_settings_fname = "site_data.csv"
        self.misc_input = Misc_Forcing_Settings()


class Ui_Settings_Parser:
    def __init__(self):
        self.settings = Ui_Settings()
        self.filename = "settings.bin"
    def open(self):
        self.settings = pickle.load(open(self.filename, "rb", -1))
    def save(self):
        with open(self.filename, "wb") as file_:
            pickle.dump(self.settings, file_, -1)

