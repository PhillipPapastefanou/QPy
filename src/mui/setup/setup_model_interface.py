from src.mui.ui_settings import Ui_Settings
from src.forcing.misc_forcing_settings import ProjectionScenario
import subprocess
import os
import sys
import re
from enum import Enum
from src.mui.setup.parser import MacParser, LinuxParser
from src.mui.setup.parser import BaseParser, OS
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QThread, QObject


class SetupParserInterface(QObject):
    sig_qpy_path = pyqtSignal(bool, str)
    sig_forcing_path = pyqtSignal(bool, str)
    sig_quincy_path = pyqtSignal(bool, str)
    sig_add_text = pyqtSignal(str)
    sig_generator_bin = pyqtSignal(bool,str)
    sig_quincy_bin = pyqtSignal(bool,str)
    def __init__(self, ui_settings: Ui_Settings, *args, ** kwargs):
        QObject.__init__(self, *args, **kwargs)
        self.ui_settings = ui_settings

        if sys.platform.startswith("linux"):
            self.os = OS.LINUX
            self.parser = LinuxParser(self.os)
        elif sys.platform == "darwin":
            self.os = OS.MAC
            self.parser = MacParser(self.os)
        elif os.name == "nt":
            self.os = OS.WINDOWS



    def look_for_compilers(self):
        self.parser.parse_lib_make(self.parser.lib_make)
        self.parser.parse_lib_cmake(self.parser.lib_cmake)
        self.parser.parse_lib_fortran(self.parser.lib_fortran)
        self.parser.parse_lib_cpp(self.parser.lib_cpp)
        self.parser.parse_lib_python(self.parser.lib_python)

    def build(self):

        self.parser.parse_directory_QPy()
        self.sig_qpy_path.emit(self.parser.found_QPy_directory, self.parser.path_QPy_directory)

        self.parser.check_directory_forcing()
        self.parser.parse_directory_forcing()
        self.sig_forcing_path.emit(self.parser.found_forcing_directory, self.parser.path_forcing_directory)

        self.ui_settings.root_ui_directory = os.getcwd()
        misc_input_path = os.path.join(self.parser.path_forcing_directory,  'misc', '')
        misc_input_settings = self.ui_settings.misc_input
        misc_input_settings.co2_concentration_file = f'{misc_input_path}GCP2023_co2_global.dat'
        misc_input_settings.co2_dC13_file = f'{misc_input_path}delta13C_in_air_input4MIPs_GM_1850-2021_extrapolated.txt'
        misc_input_settings.co2_DC14_file = f'{misc_input_path}Delta14C_in_air_input4MIPs_SHTRNH_1850-2021_extrapolated.txt'
        misc_input_settings.root_pdep_path = f'{misc_input_path}P-DEP'
        misc_input_settings.root_ndep_path = f'{misc_input_path}CESM-CAM'
        misc_input_settings.ndep_projection_scenario = ProjectionScenario.RCP126


        self.parser.generate_weather_generator(self.sig_add_text)
        self.parser.build_weather_generator(self.sig_add_text)
        self.sig_generator_bin.emit(self.parser.lib_weather_gen.found, self.parser.lib_weather_gen.path)

        self.parser.generate_quincy(self.sig_add_text)
        self.parser.build_quincy(self.sig_add_text)
        self.sig_quincy_bin.emit(self.parser.lib_quincy.found, self.parser.lib_quincy.path)


    def check_weather_generator_binary_path(self, path):
        if os.path.exists(path):
            print("Found weather generator binary.")
            return True
        else:
            print("Weather generator binary is invalid")
            return False

    def build_weather_generator(self):
        # Setup weather generator
        # Create build directory
        wg_root_dir = os.path.join(self.ui_settings.directory_QPy, "src", "weather_generator")
        wg_build_dir = os.path.join(self.ui_settings.directory_QPy, "src", "weather_generator", "build")
        if (self.os == OS.MAC) | (self.os == OS.LINUX):
            wg_binary = os.path.join(self.ui_settings.directory_QPy, "src", "weather_generator", "build", "generator")
        else:
            wg_binary = os.path.join(self.ui_settings.directory_QPy, "src", "weather_generator", "build",
                                     "generator.exe")
        if not os.path.isdir(wg_build_dir):
            os.makedirs(wg_build_dir)


        if (self.os == OS.MAC) | (self.os == OS.LINUX):
            # Creating make file for the generator
            p = subprocess.Popen([f"cmake -B {wg_build_dir} -S {wg_root_dir}"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
        else:
            y = f"{self.ui_settings.cmake_binary_path} -B {wg_build_dir} -S {wg_root_dir} -G \"Unix Makefiles\""
                                 #f" -DCMAKE_CXX_COMPILER={self.cpp_compiler_path}"
            p = subprocess.Popen(y, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)


        while p.poll() is None:
            while True:
                output = p.stdout.readline()
                if output:
                    self.sig_add_text.emit(p.stdout.readline())
                output_err = p.stderr.readline()
                if output_err:
                    self.sig_add_text.emit(p.stderr.readline())

                if (not output_err) & (not output):
                    break


        # Building weather generator
        if (self.os == OS.MAC) | (self.os == OS.LINUX):
            p = subprocess.Popen([f"make -C {wg_build_dir}"],stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
        else:
            p = subprocess.Popen(f"{self.ui_settings.make_binary_path} -C {wg_build_dir}", stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, shell=True)


        while p.poll() is None:
            while True:
                output = p.stdout.readline()
                if output:
                    self.sig_add_text.emit(p.stdout.readline())
                output_err = p.stderr.readline()
                if output_err:
                    self.sig_add_text.emit(p.stderr.readline())

                if (not output_err) & (not output):
                    break

        self.ui_settings.binary_weather_generator = wg_binary

        found = self.check_weather_generator_binary_path(self.ui_settings.binary_weather_generator)
        if found:
            self.sig_generator_bin.emit(self.ui_settings.binary_weather_generator)

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

        self.python_executable = f"C:\\Users\\Phillip\\anaconda3\\envs\\QPy\\python.exe"

        # Creating make file for QUINCY
        if (self.os == OS.MAC) | (self.os == OS.LINUX):
            p = subprocess.Popen([f"cmake -B {quincy_build_dir} -S {quincy_root_dir}"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)

            while p.poll() is None:
                while True:
                    output = p.stdout.readline()
                    if output:
                        self.sig_add_text.emit(p.stdout.readline())
                    output_err = p.stderr.readline()
                    if output_err:
                        self.sig_add_text.emit(p.stderr.readline())

                    if (not output_err) & (not output):
                        break
            p.wait()

        else:
            y = f"{self.ui_settings.cmake_binary_path} -B {quincy_build_dir} -S {quincy_root_dir} -G \"Unix Makefiles\" -DPYTHON_EXECUTABLE={self.python_executable}"
                                 #f" -DCMAKE_CXX_COMPILER={self.cpp_compiler_path}"
            #p = subprocess.Popen(y, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)

            p = subprocess.run(f"start /wait cmd /c {y}", text=True,  shell=True, capture_output=True)


        if p.returncode != 0:
            print("Could not generate build files")
            return

        # Building QUINCY

        # Creating make file for QUINCY
        if (self.os == OS.MAC) | (self.os == OS.LINUX):
            p = subprocess.Popen([f"make -C {quincy_build_dir}"], stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, shell=True)
            exit_code = p.returncode
        else:
            #p = subprocess.Popen(f"{self.ui_settings.make_binary_path} -C {quincy_build_dir}",
            #                     stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, shell=True)

            p = subprocess.run(f"start /wait cmd /c {self.ui_settings.make_binary_path} -C {quincy_build_dir}", text=True,  shell=True, capture_output=True)
            exit_code = p.returncode

        if exit_code != 0:
            print("Could not generate build files")
            return
        else:
            if (self.os == OS.MAC) | (self.os == OS.LINUX):
                self.ui_settings.quincy_binary_path = os.path.join(quincy_build_dir, "quincy_run")
            else:
                self.ui_settings.quincy_binary_path = os.path.join(quincy_build_dir, "quincy_run.exe")
            self.ui_settings.quincy_namelist_path = os.path.join(quincy_root_dir,'contrib', 'namelist', 'namelist.slm')
            self.ui_settings.quincy_lctlib_path = os.path.join(quincy_root_dir,'data', 'lctlib_quincy_nlct14.def')
            self.sig_quincy_bin.emit(self.ui_settings.quincy_binary_path)


class BuildingThread(QThread):

    finished = pyqtSignal()
    progressedChanged = pyqtSignal(int)
    progressBarReset = pyqtSignal(int, int)

    def __init__(self, parser: SetupParserInterface):
        QThread.__init__(self)
        self.parser = parser
        # mark the thread is alive
        self.alive = True

    def run(self):
        self.parser.build()

