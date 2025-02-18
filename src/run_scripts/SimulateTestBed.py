from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.NamelistDevinfo import NamelistDevinfo
from src.quincy.IO.NamelistWriter import NamelistWriter
from src.quincy.IO.LctlibReader import LctlibReader
from src.quincy.IO.LctlibWriter import LctlibWriter
from src.quincy.base.EnvironmentalInput import EnvironmentalInputSite
import os
import shutil

class TestBedSim:
    def __init__(self, quincy_root_path):
        self.quincy_root_path = quincy_root_path

        nlm_reader = NamelistReader(f"{quincy_root_path}/contrib/namelist/namelist.slm")
        self.nlm_devinfo = NamelistDevinfo(quincy_root_path)
        self.namelist =  nlm_reader.parse()
        self.nlm_devinfo.parse(self.namelist)

        lctlib_reader = LctlibReader(f"{quincy_root_path}/data/lctlib_quincy_nlct14.def")
        self.lctlib = lctlib_reader.parse()
        self.climate_forcing = EnvironmentalInputSite()


    def set_up(self, folder):

        self.climate_forcing.check()

        self.climate_forcing.parse(self.namelist)

        if len(self.climate_forcing.sitelist) > 1:
            print("Sitelist contains more than one site. This is currently not supported in test_bed mode.")
            exit(99)
        if len(self.climate_forcing.sitelist) == 0:
            print("Sitelist does not contain any sites.")
            exit(99)


        if not os.path.exists(folder):
            os.makedirs(folder)

        nlm_writer = NamelistWriter(namelist=self.namelist)
        nlm_writer.export(f"{folder}/namelist.slm")

        nlm_writer = LctlibWriter(lctlib=self.lctlib)
        nlm_writer.export(f"{folder}/lctlib_quincy_nlct8.def")

        shutil.copyfile(self.climate_forcing.isitelistFullPath[0] ,f"{folder}/climate.dat")

        exec_src_path = f"{self.quincy_root_path}/{self.nlm_devinfo.compiler}/bin/land.x"
        shutil.copy(exec_src_path, f"{folder}/")

        binS_path = self.nlm_devinfo.binSInfoFile
        shutil.copy(binS_path, f"{folder}/")

    def run(self):
        dummy = 42