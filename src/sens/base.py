from src.quincy.base.Lctlib import  Lctlib
from src.quincy.base.Namelist import  Namelist
from src.quincy.IO.NamelistWriter import NamelistWriter
from src.quincy.IO.LctlibWriter import LctlibWriter
from os import path
import os
import shutil
class Quincy_Setup:
    def __init__(self,
                 folder,
                 lctlib: Lctlib,
                 namelist: Namelist,
                 forcing_path):

        self.folder = folder
        self.lctlib = lctlib
        self.namelist = namelist
        self.climate_forcing_path = forcing_path

    def export(self):
        if not os.path.exists(self.folder):
            os.mkdir(self.folder)

        nlm_writer = NamelistWriter(self.namelist)
        nlm_writer.export(path.join(self.folder, "namelist.slm"))

        lctlib_writer = LctlibWriter(self.lctlib)
        lctlib_writer.export(path.join(self.folder, "lctlib_quincy_nlct14.def"))

        #Create a link of the climate dat file
        os.symlink(self.climate_forcing_path, path.join(self.folder, "climate.dat"))


class Quincy_Multi_Run:
    def __init__(self, root_path):
        self.setups = []
        self.root_path = root_path
    def add_setup(self, setup: Quincy_Setup):
        self.setups.append(setup)
    def generate_files(self):
        if os.path.exists(self.root_path):
            shutil.rmtree(self.root_path)

        os.mkdir(self.root_path)

        for setup in self.setups:
            setup.export()

class Quincy_Single_Run:
    def __init__(self, root_path):
        self.setup = ""
        self.root_path = root_path
    def set_setup(self, setup: Quincy_Setup):
        self.setup = setup
    def generate_files(self):
        if os.path.exists(self.root_path):
            shutil.rmtree(self.root_path)
        os.mkdir(self.root_path)
        self.setup.export()

