import os
import sys
import subprocess
from enum import Enum

class Library:
    name = ""
    path = ""
    version = ""
    found = False

class OS(Enum):
    WINDOWS = 1
    LINUX = 2
    MAC = 3


class BaseParser:
    def __init__(self, os: OS):
        self.os = os
        self.lib_make = Library()
        self.lib_cmake = Library()
        self.lib_fortran = Library()
        self.lib_cpp = Library()
        self.lib_python = Library()

        self.lib_weather_gen = Library()
        self.lib_quincy = Library()


        self.path_forcing_directory = ""
        self.path_QPy_directory = ""
        self.path_quincy_directory = ""

        self.quincy_namelist_path = ''
        self.quincy_lctlib_path = ""

        self.successfull_setup = False

    def is_valid(self, lib_path):
        if os.path.exists(lib_path):
            return True
        return False
    def parse_lib_make(self, lib :Library):
        raise NotImplementedError()
    def parse_lib_cmake(self, lib :Library):
        raise NotImplementedError()
    def parse_lib_fortran(self, lib :Library):
        raise NotImplementedError()
    def parse_lib_cpp(self, lib :Library):
        raise NotImplementedError()
    def parse_lib_python(self, lib :Library):
        if self.is_valid(lib.path):
            lib.path = sys.executable
            lib.version = "?"
            return

        lib.name = 'python'
        lib.path = sys.executable
        lib.version = sys.version.split('|')[0]
        #You can't run python without running python
        lib.found = True
    def parse_directory_QPy(self):
        this_file_path = os.path.dirname(os.path.realpath(__file__))
        if "QPy" in this_file_path:
            path_list = this_file_path.split(os.sep)
            temp = path_list.index("QPy")
            res = path_list[:temp+1]
            if (self.os == OS.MAC) | (self.os == OS.LINUX):
                res.insert(0, os.sep)
            else:
                res.insert(1,os.sep)

            self.path_QPy_directory = os.path.join(*res)
            self.found_QPy_directory = True
        else:
            self.found_QPy_directory = False
    def check_directory_QPy(self):
        self.found_QPy_directory =  self.is_valid(self.path_QPy_directory)
    def check_directory_forcing(self):
        self.found_forcing_directory = self.is_valid(self.path_forcing_directory)
    def parse_directory_forcing(self):
        self.found_forcing_directory = self.is_valid(self.path_forcing_directory)
        if not self.found_forcing_directory:
            self.path_forcing_directory = os.path.join(self.path_QPy_directory, "forcing")
            self.found_forcing_directory = self.is_valid(self.path_forcing_directory)
    def check_directory_quincy(self):
        found_dir= self.is_valid(self.path_quincy_directory)

        if found_dir:
            self.found_quincy_directory = self.is_valid(os.path.join(self.path_quincy_directory, "CMakeLists.txt"))
            if self.found_quincy_directory:
                print(f"Found quincy directory")
                self.quincy_namelist_path = os.path.join(self.path_quincy_directory, 'contrib', 'namelist',
                                                                     'namelist.slm')
                self.quincy_lctlib_path = os.path.join(self.path_quincy_directory, 'data', 'lctlib_quincy_nlct14.def')
            else:
                print(f"Could not find CMakeLists.txt in quincy directory. Did you checkout the wrong branch?")
        else:
            self.found_quincy_directory = False
    def check_quincy_binary(self):
        self.lib_quincy.name = "QUINCY"
        if (self.os == OS.MAC) | (self.os == OS.LINUX):
            self.lib_quincy.path = os.path.join(self.path_quincy_directory,"build_cmake", "quincy_run")
        else:
            self.lib_quincy.path = os.path.join(self.path_quincy_directory,"build_cmake", "quincy_run.exe")

        self.lib_quincy.found = self.is_valid(self.lib_quincy.path)

    def check_weather_generator_binary(self):
        self.lib_weather_gen.name = "weather generator"
        if (self.os == OS.MAC) | (self.os == OS.LINUX):
            self.lib_weather_gen.path = os.path.join(self.path_QPy_directory, "src", "weather_generator", "build", "generator")
        else:
            self.lib_weather_gen.path = os.path.join(self.path_QPy_directory, "src", "weather_generator", "build", "generator.exe")

        self.lib_weather_gen.found = self.is_valid(self.lib_weather_gen.path)
    def generate_weather_generator(self, sig_add_text):
        raise NotImplementedError()

    def build_weather_generator(self, sig_add_text):
        raise NotImplementedError()

    def generate_quincy(self,sig_add_text):
        raise NotImplementedError()
    def build_quincy(self):
        raise NotImplementedError()

class MacParser(BaseParser):
    def __init__(self, os: OS):
        BaseParser.__init__(self, os)


    def parse_lib_make(self, lib: Library):
        if self.is_valid(lib.path):
            return
        lib.name = "Make"
        p = subprocess.run(["which make"], capture_output=True, text=True, shell=True)

        if p.returncode != 0:
            lib.found = False
        else:
            lib.path = p.stdout
            lib.found = True

            p = subprocess.run(["make --version"], capture_output=True, text=True, shell=True)
            cmake_raw_path = p.stdout.split('\n')
            lib.version =  cmake_raw_path[0]

    def parse_lib_cmake(self, lib: Library):
        if self.is_valid(lib.path):
            return
        lib.name = "CMake"
        p = subprocess.run(["which cmake"], capture_output=True, text=True, shell=True)

        if p.returncode != 0:
            lib.found = False
        else:
            lib.path = p.stdout
            lib.found = True

            p = subprocess.run(["cmake --version"], capture_output=True, text=True, shell=True)
            cmake_raw_path = p.stdout.split('\n')
            cmake_raw_path = cmake_raw_path[0]
            cmake_raw_path = cmake_raw_path.split("cmake version")
            lib.version = cmake_raw_path[1]
    def parse_lib_cpp(self, lib :Library):
        if self.is_valid(lib.path):
            return
        lib.name = "Cpp"

        p1 = subprocess.run(["which clang"], capture_output=True, text=True, shell=True)

        if p1.returncode != 0:
            p2 = subprocess.run(["which gcc"], capture_output=True, text=True, shell=True)
            if p2.returncode != 0:
                lib.found = False

            else:
                lib.found = True
                lib.path = p2.stdout
                p2 = subprocess.run(["gcc --version"], capture_output=True, text=True, shell=True)
                cpp_raw_path = p2.stdout.split('\n')
                lib.version = cpp_raw_path[0]
        else:
            lib.found = True
            lib.path = p1.stdout
            p1 = subprocess.run(["clang --version"], capture_output=True, text=True, shell=True)
            cpp_raw_path = p1.stdout.split('\n')
            cpp_raw_path = cpp_raw_path[0]
            cpp_raw_path = cpp_raw_path.split("Apple clang version")
            lib.version = cpp_raw_path[1]
    def parse_lib_fortran(self, lib: Library):
        if self.is_valid(lib.path):
            return
        lib.name = "gfortran"
        p = subprocess.run(["which gfortran"], capture_output=True, text=True, shell=True)

        if p.returncode != 0:
            lib.found = False
        else:
            lib.path = p.stdout
            lib.found = True

            p = subprocess.run(["gfortran --version"], capture_output=True, text=True, shell=True)
            cpp_raw_path = p.stdout.split('\n')
            cpp_raw_path = cpp_raw_path[0]
            cpp_raw_path = cpp_raw_path.split("GNU Fortran ")
            lib.version = cpp_raw_path[1]

    def generate_weather_generator(self, sig_add_text):
        wg_root_dir = os.path.join(self.path_QPy_directory, "src", "weather_generator")
        wg_build_dir = os.path.join(self.path_QPy_directory, "src", "weather_generator", "build")
        p = subprocess.Popen([f"cmake -B {wg_build_dir} -S {wg_root_dir}"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)

        while p.poll() is None:
            while True:
                output = p.stdout.readline()
                if output:
                    sig_add_text.emit(p.stdout.readline())
                output_err = p.stderr.readline()
                if output_err:
                    sig_add_text.emit(p.stderr.readline())

                if (not output_err) & (not output):
                    break

        if p.returncode != 0:
            print("Could not generate weather generator build files")
        else:
            print("Successfully generated weather generator build files")
    def build_weather_generator(self, sig_add_text):

        wg_build_dir = os.path.join(self.path_QPy_directory, "src", "weather_generator", "build")
        wg_binary = os.path.join(self.path_QPy_directory, "src", "weather_generator", "build", "generator")
        p = subprocess.Popen([f"make -C {wg_build_dir}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             shell=True)

        while p.poll() is None:
            while True:
                output = p.stdout.readline()
                if output:
                    sig_add_text.emit(p.stdout.readline())
                output_err = p.stderr.readline()
                if output_err:
                    sig_add_text.emit(p.stderr.readline())

                if (not output_err) & (not output):
                    break

        if p.returncode != 0:
            print("Could not build weather generator")
        else:
            print("Successfully build weather generator")
            self.lib_weather_gen.path = wg_binary
            self.lib_weather_gen.found = True

    def generate_quincy(self, sig_add_text):

        if not self.found_quincy_directory:
            print(f"Quincy root path not specified or found")
            print(f"Stopping generation")
            return

        quincy_root_dir = self.path_quincy_directory
        # Create build directory
        quincy_build_dir = os.path.join(quincy_root_dir,"build_cmake")
        if not os.path.isdir(quincy_root_dir):
            os.makedirs(quincy_root_dir)

        p = subprocess.Popen([f"cmake -B {quincy_build_dir} -S {quincy_root_dir}"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)

        while p.poll() is None:
            while True:
                output = p.stdout.readline()
                if output:
                    sig_add_text.emit(p.stdout.readline())
                output_err = p.stderr.readline()
                if output_err:
                    sig_add_text.emit(p.stderr.readline())

                if (not output_err) & (not output):
                    break
        p.wait()

        if p.returncode != 0:
            print("Could not generate quincy build files")
        else:
            print("Successfully generated quincy build files")

    def build_quincy(self, sig_add_text):

        if not self.found_quincy_directory:
            print(f"Quincy root path not specified or found")
            print(f"Stopping generation")
            return

        quincy_root_dir = self.path_quincy_directory
        quincy_build_dir = os.path.join(quincy_root_dir,"build_cmake")

        p = subprocess.Popen([f"make -C {quincy_build_dir}"], stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                             shell=True)

        while p.poll() is None:
            while True:
                output = p.stdout.readline()
                if output:
                    sig_add_text.emit(p.stdout.readline())

                output_err = p.stderr.readline()
                if output_err:
                    sig_add_text.emit(p.stderr.readline())
                    #print(p.stderr.readline())
                if (not output_err) & (not output):
                    break

        p.wait()
        if p.returncode != 0:
            print("Could not build quincy")
        else:
            print("Successfully build quincy")
            quincy_binary  = os.path.join(quincy_build_dir, "quincy_run")
            self.lib_quincy.path = quincy_binary
            self.lib_quincy.found = True

        if self.lib_weather_gen.found & self.lib_quincy.found:
            self.successfull_setup  = True

class LinuxParser(BaseParser):
    def __init__(self, os: OS):
        BaseParser.__init__(self, os)

    def parse_lib_make(self, lib: Library):
        if self.is_valid(lib.path):
            return
        lib.name = "Make"
        p = subprocess.run(["which make"], capture_output=True, text=True, shell=True)

        if p.returncode != 0:
            lib.found = False
        else:
            lib.path = p.stdout
            lib.found = True

            p = subprocess.run(["make --version"], capture_output=True, text=True, shell=True)
            try:
                cmake_raw_path = p.stdout.split('\n')
                lib.version =  cmake_raw_path[0]
            except:
                lib.version =  p.stdout

    def parse_lib_cmake(self, lib: Library):
        if self.is_valid(lib.path):
            return
        lib.name = "CMake"
        p = subprocess.run(["which cmake"], capture_output=True, text=True, shell=True)

        if p.returncode != 0:
            lib.found = False
        else:
            lib.path = p.stdout
            lib.found = True

            p = subprocess.run(["cmake --version"], capture_output=True, text=True, shell=True)

            try:
                cmake_raw_path = p.stdout.split('\n')
                cmake_raw_path = cmake_raw_path[0]
                cmake_raw_path = cmake_raw_path.split("cmake version")
                lib.version = cmake_raw_path[1]
            except:
                lib.version =  p.stdout

    def parse_lib_cpp(self, lib :Library):
        if self.is_valid(lib.path):
            return
        lib.name = "Cpp"

        p1 = subprocess.run(["which gcc"], capture_output=True, text=True, shell=True)

        if p1.returncode != 0:
            lib.found = False

        else:
            lib.found = True
            lib.path = p1.stdout
            p = subprocess.run(["gcc --version"], capture_output=True, text=True, shell=True)
            try:
                cpp_raw_path = p.stdout.split('\n')
                lib.version = cpp_raw_path[0]
            except:
                lib.version =  p.stdout
    def parse_lib_fortran(self, lib: Library):
        if self.is_valid(lib.path):
            return
        lib.name = "gfortran"
        p = subprocess.run(["which gfortran"], capture_output=True, text=True, shell=True)

        if p.returncode != 0:
            lib.found = False
        else:
            lib.path = p.stdout
            lib.found = True

            p = subprocess.run(["gfortran --version"], capture_output=True, text=True, shell=True)
            try:
                cpp_raw_path = p.stdout.split('\n')
                cpp_raw_path = cpp_raw_path[0]
                cpp_raw_path = cpp_raw_path.split("GNU Fortran ")
                lib.version = cpp_raw_path[1]
            except:
                lib.version =  p.stdout

    def generate_weather_generator(self, sig_add_text):
        wg_root_dir = os.path.join(self.path_QPy_directory, "src", "weather_generator")
        wg_build_dir = os.path.join(self.path_QPy_directory, "src", "weather_generator", "build")
        p = subprocess.Popen([f"cmake -B {wg_build_dir} -S {wg_root_dir}"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)

        while p.poll() is None:
            while True:
                output = p.stdout.readline()
                if output:
                    sig_add_text.emit(p.stdout.readline())
                output_err = p.stderr.readline()
                if output_err:
                    sig_add_text.emit(p.stderr.readline())

                if (not output_err) & (not output):
                    break

        if p.returncode != 0:
            print("Could not generate weather generator build files")
        else:
            print("Successfully generated weather generator build files")
    def build_weather_generator(self, sig_add_text):

        wg_build_dir = os.path.join(self.path_QPy_directory, "src", "weather_generator", "build")
        wg_binary = os.path.join(self.path_QPy_directory, "src", "weather_generator", "build", "generator")
        p = subprocess.Popen([f"make -C {wg_build_dir}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             shell=True)

        while p.poll() is None:
            while True:
                output = p.stdout.readline()
                if output:
                    sig_add_text.emit(p.stdout.readline())
                output_err = p.stderr.readline()
                if output_err:
                    sig_add_text.emit(p.stderr.readline())

                if (not output_err) & (not output):
                    break

        if p.returncode != 0:
            print("Could not build weather generator")
        else:
            print("Successfully build weather generator")
            self.lib_weather_gen.path = wg_binary
            self.lib_weather_gen.found = True



    def generate_quincy(self, sig_add_text):

        if not self.found_quincy_directory:
            print(f"Quincy root path not specified or found")
            print(f"Stopping generation")
            return

        quincy_root_dir = self.path_quincy_directory
        # Create build directory
        quincy_build_dir = os.path.join(quincy_root_dir,"build_cmake")
        if not os.path.isdir(quincy_root_dir):
            os.makedirs(quincy_root_dir)

        p = subprocess.Popen([f"cmake -B {quincy_build_dir} -S {quincy_root_dir}"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)

        while p.poll() is None:
            while True:
                output = p.stdout.readline()
                if output:
                    sig_add_text.emit(p.stdout.readline())
                output_err = p.stderr.readline()
                if output_err:
                    sig_add_text.emit(p.stderr.readline())

                if (not output_err) & (not output):
                    break
        p.wait()

        if p.returncode != 0:
            print("Could not generate quincy build files")
        else:
            print("Successfully generated quincy build files")

    def build_quincy(self, sig_add_text):

        if not self.found_quincy_directory:
            print(f"Quincy root path not specified or found")
            print(f"Stopping generation")
            return

        quincy_root_dir = self.path_quincy_directory
        quincy_build_dir = os.path.join(quincy_root_dir,"build_cmake")

        p = subprocess.Popen([f"make -C {quincy_build_dir}"], stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                             shell=True)

        while p.poll() is None:
            while True:
                output = p.stdout.readline()
                if output:
                    sig_add_text.emit(p.stdout.readline())

                output_err = p.stderr.readline()
                if output_err:
                    sig_add_text.emit(p.stderr.readline())
                    #print(p.stderr.readline())
                if (not output_err) & (not output):
                    break

        p.wait()
        if p.returncode != 0:
            print("Could not build quincy")
        else:
            print("Successfully build quincy")
            quincy_binary  = os.path.join(quincy_build_dir, "quincy_run")
            self.lib_quincy.path = quincy_binary
            self.lib_quincy.found = True

        if self.lib_weather_gen.found & self.lib_quincy.found:
            self.successfull_setup  = True

class WindowsParser(BaseParser):
    def __init__(self, os: OS):
        BaseParser.__init__(self, os)

        self.powershell_path = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"

        #     if not os.path.exists(self.ui_settings.cmake_binary_path):
        #         p = subprocess.run([self.powershell_path, '(gcm cmake).Path'], shell=True, capture_output=True)
        #
        #         if p.returncode != 0:
        #             print("Could not find CMake")
        #             self.cmake_found = False
        #             self.cmake_version = ""
        #         else:
        #             print(f"Found CMake:{p.stdout}")
        #             self.ui_settings.cmake_binary_path = p.stdout.decode()
        #             self.ui_settings.cmake_binary_path = re.sub('\r', '', self.ui_settings.cmake_binary_path)
        #             self.ui_settings.cmake_binary_path = re.sub('\n', '', self.ui_settings.cmake_binary_path)
        #
        #             self.cmake_found = True
        #
        #             p = subprocess.run(["cmake", "--version"], capture_output=True, text=True, shell=True)
        #
        #             cmake_raw_path = p.stdout.split('\n')
        #             self.cmake_version = cmake_raw_path[0]
        #

        #
        #     p1 = subprocess.run([self.powershell_path, '(gcm g++).Path'], capture_output=True, text=True, shell=True)
        #     if p1.returncode != 0:
        #         self.cpp_found = False
        #
        #     else:
        #         self.cpp_found = True
        #         self.cpp_compiler_path = p1.stdout
        #         p1 = subprocess.run([self.powershell_path, "g++ --version"], capture_output=True, text=True, shell=True)
        #         cpp_raw_path = p1.stdout.split('\n')
        #         self.cpp_compiler_version = cpp_raw_path[0]
        #
        #     p1 = subprocess.run([self.powershell_path, '(gcm gfortran).Path'], capture_output=True, text=True, shell=True)
        #
        #     if p1.returncode != 0:
        #         self.fortran_found = False
        #
        #     else:
        #         self.fortran_found = True
        #         self.fortran_compiler_path = p1.stdout
        #         self.fortran_compiler_path = re.sub('\r', '', self.fortran_compiler_path)
        #         self.fortran_compiler_path = re.sub('\n', '', self.fortran_compiler_path)
        #
        #         p1 = subprocess.run([self.powershell_path, "gfortran --version"], capture_output=True, text=True, shell=True)
        #         cpp_raw_path = p1.stdout.split('\n')
        #         self.fortran_compiler_version = cpp_raw_path[0]

    def parse_lib_make(self, lib: Library):
        import re

        if self.is_valid(lib.path):
            return

        p = subprocess.run([self.powershell_path, '(gcm make).Path'], shell=True, capture_output=True)
        if p.returncode != 0:
            lib.found = False
        else:
            lib.found = True
            makepath = p.stdout.decode()
            makepath = re.sub('\r', '', makepath)
            makepath = re.sub('\n', '', makepath)
            lib.path = makepath

            p = subprocess.run([self.powershell_path, "make --version"], capture_output=True, text=True, shell=True)

            try:
                make_version = p.stdout.split('\n')
                lib.path = make_version[0]
            except:
                lib.path =  p.stdout

    def parse_lib_cmake(self, lib: Library):
        import re

        if self.is_valid(lib.path):
            return

        p = subprocess.run([self.powershell_path, '(gcm cmake).Path'], shell=True, capture_output=True)
        if p.returncode != 0:
            lib.found = False
        else:
            lib.found = True
            cmakepath = p.stdout.decode()
            cmakepath = re.sub('\r', '', cmakepath)
            cmakepath = re.sub('\n', '', cmakepath)
            lib.path = cmakepath

            p = subprocess.run([self.powershell_path, "cmake --version"], capture_output=True, text=True, shell=True)

            try:
                cmake_version = p.stdout.split('\n')
                lib.path = cmake_version[0]
            except:
                lib.path =  p.stdout

    def parse_lib_cpp(self, lib :Library):
        if self.is_valid(lib.path):
            return
        lib.name = "Cpp"

        p1 =  subprocess.run([self.powershell_path, '(gcm g++).Path'], capture_output=True, text=True, shell=True)

        if p1.returncode != 0:
            lib.found = False

        else:
            lib.found = True
            lib.path = p1.stdout
            p = subprocess.run([self.powershell_path, "g++ --version"], capture_output=True, text=True, shell=True)
            try:
                cpp_raw_path = p.stdout.split('\n')
                lib.version = cpp_raw_path[0]
            except:
                lib.version =  p.stdout
    def parse_lib_fortran(self, lib: Library):
        if self.is_valid(lib.path):
            return
        lib.name = "gfortran"
        p = subprocess.run([self.powershell_path, "which gfortran"], capture_output=True, text=True, shell=True)

        if p.returncode != 0:
            lib.found = False
        else:
            lib.path = p.stdout
            lib.found = True

            p = subprocess.run([self.powershell_path,"gfortran --version"], capture_output=True, text=True, shell=True)
            try:
                cpp_raw_path = p.stdout.split('\n')
                lib.version = cpp_raw_path[0]
            except:
                lib.version =  p.stdout

    def generate_weather_generator(self, sig_add_text):
        wg_root_dir = os.path.join(self.path_QPy_directory, "src", "weather_generator")
        wg_build_dir = os.path.join(self.path_QPy_directory, "src", "weather_generator", "build")

        command = f"{self.lib_cmake.path} -B {wg_build_dir} -S {wg_root_dir} -G \"Unix Makefiles\""
        # f" -DCMAKE_CXX_COMPILER={self.cpp_compiler_path}"
        p = subprocess.run(f"start /wait cmd /c {command}", text=True, shell=True, capture_output=True)

        if p.returncode != 0:
            print("Could not generate weather generator build files")
        else:
            print("Successfully generated weather generator build files")
    def build_weather_generator(self, sig_add_text):

        wg_build_dir = os.path.join(self.path_QPy_directory, "src", "weather_generator", "build")
        wg_binary = os.path.join(self.path_QPy_directory, "src", "weather_generator", "build", "generator.exe")

        command = f"{self.lib_make.path} -C {wg_build_dir}"
        p = subprocess.run(f"start /wait cmd /c {command}", text=True, shell=True, capture_output=True)

        if p.returncode != 0:
            print("Could not build weather generator")
        else:
            print("Successfully build weather generator")
            self.lib_weather_gen.path = wg_binary
            self.lib_weather_gen.found = True

    def generate_quincy(self, sig_add_text):

        if not self.found_quincy_directory:
            print(f"Quincy root path not specified or found")
            print(f"Stopping generation")
            return

        quincy_root_dir = self.path_quincy_directory
        # Create build directory
        quincy_build_dir = os.path.join(quincy_root_dir,"build_cmake")
        if not os.path.isdir(quincy_root_dir):
            os.makedirs(quincy_root_dir)

        command = f"{self.lib_cmake.path} -B {quincy_build_dir} -S {quincy_root_dir} -G \"Unix Makefiles\" -DPYTHON_EXECUTABLE={self.lib_python.path}"
        p = subprocess.run(f"start /wait cmd /c {command}", text=True, shell=True, capture_output=True)

        if p.returncode != 0:
            print("Could not generate quincy build files")
        else:
            print("Successfully generated quincy build files")

    def build_quincy(self, sig_add_text):

        if not self.found_quincy_directory:
            print(f"Quincy root path not specified or found")
            print(f"Stopping generation")
            return

        quincy_root_dir = self.path_quincy_directory
        quincy_build_dir = os.path.join(quincy_root_dir,"build_cmake")

        p = subprocess.run(f"start /wait cmd /c {self.lib_make.path} -C {quincy_build_dir}", text=True,
                           shell=True, capture_output=True)

        if p.returncode != 0:
            print("Could not build quincy")
        else:
            print("Successfully build quincy")
            quincy_binary  = os.path.join(quincy_build_dir, "quincy_run.exe")
            self.lib_quincy.path = quincy_binary
            self.lib_quincy.found = True

        if self.lib_weather_gen.found & self.lib_quincy.found:
            self.successfull_setup  = True