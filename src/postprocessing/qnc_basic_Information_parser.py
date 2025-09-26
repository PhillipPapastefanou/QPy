import os
import pandas as pd
import traceback
import re
from src.postprocessing.qnc_defintions import *


class Basic_information_parser:
    def __init__(self, root_path, folder_structure_type):
        self.root_path = root_path
        self.folder_structure_type = folder_structure_type

    def Set_basic_file_names(self, sinfo_file, exp_info_file):
        self.sinfo_file = sinfo_file
        self.exp_info_file = exp_info_file

    def Load_info(self):

        if self.folder_structure_type == Folder_structure_type.Standard:
            self.postprocess_subdir = "postprocessing/"
        elif self.folder_structure_type == Folder_structure_type.Test_bed:
            self.postprocess_subdir = ""
        else:
            print("Invalid simulation type")
            exit(-1)

        try:
            info_filename = os.path.join(self.root_path, self.postprocess_subdir, self.sinfo_file)
            info_f = open(info_filename)
            base_data = info_f.readlines()
            base_data = [line.rstrip('\n') for line in base_data]

            compiled_with_netcdf = False
            self.compiler_str = 'Unkown'

            for i in range(0, len(base_data)):
                str_clean = re.sub('[^A-Za-z0-9]+', '', base_data[i])
                if str_clean == 'compiledwithnetcdflibraries':
                    if base_data[i + 1] == 'TRUE':
                        compiled_with_netcdf = True
                if str_clean == 'compiler':
                    self.compiler_str = base_data[i + 1]
            
            
            if not compiled_with_netcdf:
                print("Not convinced that this is not NetCDF")
                print("Checking for NetCDF files... s")
                folder = os.path.join(self.root_path, self.postprocess_subdir)

                for root, dirs, files in os.walk(folder):
                    for f in files:
                        if f.lower().endswith(".nc"):
                            compiled_with_netcdf = True
                            break           
            
        except:
            
            print(f"Problme while parsing file {self.sinfo_file}. Error:")
            traceback.print_exc()

        # If we do not have the correct indication that the binaries were build with NetCDF we might
        # look at some old NetCDF files but new model output. Very dangerous. Abort! Help!
        if not compiled_with_netcdf:
            print("Output has not been compiled with NetCDF!")
            print("Check binaries of binary parsing")
            exit(-1)

        try:
            sinfo_data = pd.read_csv(os.path.join(self.root_path, self.postprocess_subdir, self.sinfo_file), sep=r'\s+', nrows=1)

            self.commit = sinfo_data['commit'].values.squeeze()
            self.branch = sinfo_data['branch'].values.squeeze()
            self.status = sinfo_data['status:'].values.squeeze()
        except:
            print(f"Error while parsing file {self.sinfo_file}. Error:")
            traceback.print_exc()

        try:
            exp_info_data = pd.read_csv(os.path.join(self.root_path, self.postprocess_subdir, self.exp_info_file), sep=r'\s+')

            self.sitename = exp_info_data['sitename'].values.squeeze()
            self.user = exp_info_data['user'].values.squeeze()
            self.date = exp_info_data['date'].values.squeeze()

            if self.folder_structure_type == Folder_structure_type.Test_bed:
                # For some reason static testbed forcing does not contain a PFT entry
                self.pft = "Unkown"
            else:
                self.pft = exp_info_data['pftname'].values.squeeze()

        except:
            print(f"Error while parsing file {self.exp_info_file}. Error:")
            self.pft = "Unkown"
            traceback.print_exc()

