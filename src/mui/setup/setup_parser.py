from src.mui.ui_settings import Ui_Settings
from src.forcing.misc_forcing_settings import ProjectionScenario
import subprocess
import os
import sys
from enum import Enum
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QThread, QObject

class OS(Enum):
    WINDOWS = 1
    LINUX = 2
    MAC = 3

class SetupParser(QObject):
    sig_add_text = pyqtSignal(str)
    sig_qpy_path = pyqtSignal(str)
    sig_generator_bin = pyqtSignal(str)
    sig_quincy_dir = pyqtSignal(str)
    sig_quincy_bin = pyqtSignal(str)
    def __init__(self, ui_settings: Ui_Settings, *args, ** kwargs):
        QObject.__init__(self, *args, **kwargs)
        self.ui_settings = ui_settings

        if sys.platform.startswith("linux"):
            self.os = OS.LINUX
        elif sys.platform == "darwin":
            self.os = OS.MAC
        elif os.name == "nt":
            self.os = OS.WINDOWS

        if not ui_settings.successfull_setup:
            self.look_for_compilers()

    def look_for_compilers(self):

        if not os.path.exists(self.ui_settings.cmake_binary_path):
            p = subprocess.run(["which cmake"], capture_output=True, text=True, shell=True)

            if p.returncode != 0:
                print("Could not find CMake")
                self.cmake_found = False
                self.cmake_version = ""
            else:
                print(f"Found CMake:{p.stdout}")
                self.ui_settings.cmake_binary_path = p.stdout
                self.cmake_found = True

                p = subprocess.run(["cmake --version"], capture_output=True, text=True, shell=True)

                cmake_raw_path = p.stdout.split('\n')
                cmake_raw_path = cmake_raw_path[0]
                cmake_raw_path = cmake_raw_path.split("cmake version")
                self.cmake_version = cmake_raw_path[1]

        if self.os == OS.MAC:
            p1 = subprocess.run(["which clang"], capture_output=True, text=True, shell=True)

            if p1.returncode != 0:
                p2 = subprocess.run(["which gcc"], capture_output=True, text=True, shell=True)

                if p2.returncode != 0:
                    self.cpp_found = False

                else:
                    self.cpp_found = True
                    self.cpp_compiler_path = p2.stdout
                    p2 = subprocess.run(["gcc --version"], capture_output=True, text=True, shell=True)
                    cpp_raw_path = p2.stdout.split('\n')
                    self.cpp_compiler_version = cpp_raw_path[0]
            else:
                self.cpp_found = True
                self.cpp_compiler_path = p1.stdout
                p1 = subprocess.run(["clang --version"], capture_output=True, text=True, shell=True)
                cpp_raw_path = p1.stdout.split('\n')
                cpp_raw_path = cpp_raw_path[0]
                cpp_raw_path = cpp_raw_path.split("Apple clang version")
                self.cpp_compiler_version = cpp_raw_path[1]


                p1 = subprocess.run(["which gfortran"], capture_output=True, text=True, shell=True)

                if p1.returncode != 0:
                    self.fortran_found = False

                else:
                    self.fortran_found = True
                    self.fortran_compiler_path = p1.stdout
                    p1 = subprocess.run(["gfortran --version"], capture_output=True, text=True, shell=True)
                    cpp_raw_path = p1.stdout.split('\n')
                    cpp_raw_path = cpp_raw_path[0]
                    cpp_raw_path = cpp_raw_path.split("GNU Fortran ")
                    self.fortran_compiler_version = cpp_raw_path[1]

    def build(self):
        # Get the path of this file to obtain root directory
        this_file_path = os.path.dirname(os.path.realpath(__file__))

        if "QPy" in this_file_path:
            path_list = this_file_path.split(os.sep)
            temp = path_list.index("QPy")
            res = path_list[:temp+1]
            if (self.os == OS.MAC) | (self.os == OS.LINUX):
                res.insert(0, os.sep)
            self.ui_settings.root_qpy_directory = os.path.join(*res)
            print(f"Found QPy directory")
            self.sig_qpy_path.emit(self.ui_settings.root_qpy_directory)
        else:
            print(f"Could not determine root QPy directory")

        self.setup_weather_generator()
        self.build_quincy()

        self.ui_settings.root_ui_directory = os.getcwd()

        misc_input_path = os.path.join(self.ui_settings.root_qpy_directory, 'forcing', 'misc', '')
        misc_input_settings = self.ui_settings.misc_input
        misc_input_settings.co2_concentration_file = f'{misc_input_path}GCP2023_co2_global.dat'
        misc_input_settings.co2_dC13_file = f'{misc_input_path}delta13C_in_air_input4MIPs_GM_1850-2021_extrapolated.txt'
        misc_input_settings.co2_DC14_file = f'{misc_input_path}Delta14C_in_air_input4MIPs_SHTRNH_1850-2021_extrapolated.txt'
        misc_input_settings.root_pdep_path = f'{misc_input_path}P-DEP'
        misc_input_settings.root_ndep_path = f'{misc_input_path}CESM-CAM'
        misc_input_settings.ndep_projection_scenario = ProjectionScenario.RCP126



    def check_weather_generator_binary_path(self, path):
        if os.path.exists(path):
            print("Found weather generator binary.")
            return True
        else:
            print("Weather generator binary is invalid")
            return False

    def setup_weather_generator(self):
        # Setup weather generator
        # Create build directory
        wg_root_dir = os.path.join(self.ui_settings.root_qpy_directory, "src", "weather_generator")
        wg_build_dir = os.path.join(self.ui_settings.root_qpy_directory, "src", "weather_generator",  "build")
        wg_binary = os.path.join(self.ui_settings.root_qpy_directory, "src", "weather_generator",  "build", "generator")
        if not os.path.isdir(wg_build_dir):
            os.makedirs(wg_build_dir)

        # Creating make file for the generator
        p = subprocess.Popen([f"cmake -B {wg_build_dir} -S {wg_root_dir}"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
        while p.poll() is None:
            while True:
                output = p.stdout.readline()
                if output:
                    self.sig_add_text.emit(p.stdout.readline())
                else:
                    break

        if p.returncode != 0:
            self.sig_add_text.emit(p.stderr.readline())


        # Building weather generator
        p = subprocess.Popen([f"make -C {wg_build_dir}"],stdout=subprocess.PIPE, text=True, shell=True)
        while p.poll() is None:
            while True:
                output = p.stdout.readline()
                if output:
                    self.sig_add_text.emit(p.stdout.readline())
                else:
                    break

        self.ui_settings.forcing_generator_binary_path = wg_binary

        found = self.check_weather_generator_binary_path(self.ui_settings.forcing_generator_binary_path)
        if found:
            self.sig_generator_bin.emit(self.ui_settings.forcing_generator_binary_path)

    def build_quincy(self):
        if not os.path.exists(self.ui_settings.quincy_root_path):
            print(f"Quincy root path not specified or found")
            return
        else:
            print("Found quincy directory")
            self.sig_quincy_dir.emit(self.ui_settings.quincy_root_path)

        if not os.path.exists(os.path.join(self.ui_settings.quincy_root_path,"CMakeLists.txt")):
            print(f"Could not find CMakeLists.txt in quincy directory. Did you checkout the wrong branch?")

        quincy_root_dir = self.ui_settings.quincy_root_path
        # Create build directory
        quincy_build_dir = os.path.join(self.ui_settings.quincy_root_path,"build_cmake")
        if not os.path.isdir(quincy_root_dir):
            os.makedirs(quincy_root_dir)

        # Creating make file for QUINCY
        p = subprocess.Popen([f"cmake -B {quincy_build_dir} -S {quincy_root_dir}"],
                             stdout=subprocess.PIPE, text=True, shell=True)
        while p.poll() is None:
            while True:
                output = p.stdout.readline()
                if output:
                    self.sig_add_text.emit(p.stdout.readline())
                else:
                    break
        if p.returncode != 0:
            print("Could not generate build files")
            return

        # Building QUINCY
        p = subprocess.Popen([f"make -C {quincy_build_dir}"],stdout=subprocess.PIPE, text=True, shell=True)
        while p.poll() is None:
            while True:
                output = p.stdout.readline()
                if output:
                    self.sig_add_text.emit(p.stdout.readline())
                else:
                    break
        if p.returncode != 0:
            print("Could not generate build files")
            return
        else:
            self.ui_settings.quincy_binary_path = os.path.join(quincy_build_dir, "quincy_run")
            self.ui_settings.quincy_namelist_path = os.path.join(quincy_root_dir,'contrib', 'namelist', 'namelist.slm')
            self.ui_settings.quincy_lctlib_path = os.path.join(quincy_root_dir,'data', 'lctlib_quincy_nlct14.def')
            self.sig_quincy_bin.emit(self.ui_settings.quincy_binary_path)


class BuildingThread(QThread):

    finished = pyqtSignal()
    progressedChanged = pyqtSignal(int)
    progressBarReset = pyqtSignal(int, int)

    def __init__(self, parser: SetupParser):
        QThread.__init__(self)
        self.parser = parser
        # mark the thread is alive
        self.alive = True

    def run(self):
        self.parser.build()

