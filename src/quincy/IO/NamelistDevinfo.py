from src.quincy.base.Namelist import Namelist
import os
class NamelistDevinfo:

    def __init__(self, quincy_root_path):
        self.quincy_root_path = quincy_root_path
        self.imakeInfoFile = f"{quincy_root_path}/build/make_compile-options.incl"

    def parse(self,  namelist: Namelist):

        self.namelist = namelist
        self.namelist.base_ctl.simulation_run_by = os.getlogin()

        file = open(self.imakeInfoFile, "r")
        while True:
            line = file.readline()
            if not line:
                print("Could not determine compiler")
                break
            if "COMP =" in line:
                str_arr = line.split("=")
                self.compiler = str_arr[1].strip()
                break
        file.close()

        #self.binGitInfoFile = f"/Volumes/BSI/work_scratch/ppapastefanou/src/quincy/{self.compiler}/binary_git_info.txt"
        #self.binGitInfoFile = f"./../../{self.compiler}/binary_git_info.txt"



        # if not os.path.exists(self.binGitInfoFile):
        #     print("NOTE: your binary is not accompanied by a short git info file (binary_git_info.txt)!")
        #     print("... thus info on commit and branch cannot be added to figures")
        #     print(".... consider recompiling with the quincy compile script.")
        #     print()
        #
        # else:
        #     file = open(self.binGitInfoFile, "r")
        #
        #     while True:
        #         line = file.readline()
        #         if not line:
        #             break
        #     file.close()

        self.binSInfoFile = f"{self.quincy_root_path}/{self.compiler}/binary_sinfo.txt"

        if not os.path.exists(self.binSInfoFile):
            print("NOTE: your binary is not accompanied by a short git info file (binary_git_info.txt)!")
            print("... thus info on commit and branch cannot be added to figures")
            print(".... consider recompiling with the quincy compile script.")
            print()

        else:
            file = open(self.binSInfoFile, "r")
            lines = file.readlines()
            str_input = lines[1].split(" ")
            self.namelist.base_ctl.git_commit_SHA = str_input[0]
            self.namelist.base_ctl.git_branch = str_input[1]
            modified = True if str_input[2].strip() == 'modified' else False
            self.namelist.base_ctl.code_has_changed_since_SHA = modified