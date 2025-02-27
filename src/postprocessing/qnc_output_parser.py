from enum import Enum
import os
from pathlib import Path
from src.postprocessing.qnc_defintions import *
from src.quincy.base.NamelistTypes import ForcingMode
from src.postprocessing.qnc_basic_Information_parser import Basic_information_parser

class Output:
    def __init__(self, identifier, simulation_type):
        self.Identifier = identifier
        self.forcing_mode = simulation_type
        self.Files = []
        self.Categories = []
        self.Target_categories = []

        # To be determined during processing
        self.Time_resolution = Output_Time_Res.Invalid
        self.Output_type = Output_type.Invalid


class QNC_output_parser:
    def __init__(self, root_path):
        self.root_path = root_path
        self.Available_outputs = {}

        # Settings --------------------------
        self.sinfo_file = "binary_sinfo.txt"
        self.exp_info_file = "exp_info.txt"


        self.spinup_identifier = "spinup"
        self.scenario_identifier = "transient"
        self.static_identifier = "static"

        self.diagonstic_identifier_list = ["fluxnetdata", "eucfacedata"]
        # To be determind by diagnostic identifier
        # End of settings ------------------



        # Initialisation
        self.forcing_mode = ForcingMode.STATIC
        self.output_files_path = ""
        self.diagnostic_identifier = "unkown"
        self.folder_structure_type = Folder_structure_type.Invalid

    def Read(self):

        self.check_if_transient_or_static_output()
        self.get_diagnostic_identifier()
        self.populate_output_files()

        self.Basic_info = Basic_information_parser(self.root_path, self.folder_structure_type)
        self.Basic_info.Set_basic_file_names(self.sinfo_file, self.exp_info_file)
        self.Basic_info.Load_info()

    def check_target_categories(self, category_list):
        for identifier in self.Available_outputs:
            cats = self.Available_outputs[identifier].Categories

            missing_cats = set(category_list).difference(cats)
            if len(missing_cats) > 0:
                for elment in missing_cats:
                    print(f"Category {elment} appears not to be available the output and will be ignored.")

            self.Available_outputs[identifier].Target_categories = list(set(category_list).intersection(cats))

    def populate_output_files(self):

        files = os.listdir(self.output_files_path)
        transient_var_list = [self.spinup_identifier, self.scenario_identifier, self.diagnostic_identifier]

        # check which outputs are available and generate list entries
        for file in files:
            if '.nc' in file:
                if self.forcing_mode == ForcingMode.STATIC:
                    output = Output(self.static_identifier, ForcingMode.STATIC)
                    self.Available_outputs[self.static_identifier] = output

                elif self.forcing_mode == ForcingMode.TRANSIENT:
                    for identifier in transient_var_list:
                        if identifier in file:
                            output = Output(identifier, ForcingMode.TRANSIENT)
                            self.Available_outputs[identifier] = output
                            transient_var_list.remove(identifier)

                else:
                    print("Invalid simulation output type.")
                    exit(-1)

        # populate arrays with files
        for file in files:
            if '.nc' in file:
                identifier_list  =  [self.static_identifier, self.spinup_identifier, self.scenario_identifier, self.diagnostic_identifier]

                for identifier in identifier_list:
                    if identifier in file:
                        parts = file.split('_')

                        if parts[0] == 'Q':
                            parts = parts[1:]
                            parts[0] = 'Q_' + parts[0]

                        # Obtain category
                        cat = parts[0]

                        # Obtain time resolution
                        time_str = Path(parts[2]).stem
                        time_res  = self.get_time_res_from_string(time_str)

                        # Convert to identifier enum
                        identifier_enum = self.get_output_type_from_string(identifier)

                        self.Available_outputs[identifier].Files.append(file)
                        self.Available_outputs[identifier].Categories.append(cat)
                        # Duplicate categories in case we do not check for availability later
                        self.Available_outputs[identifier].Target_categories.append(cat)

                        # Todo: Add sanity checks for time resolutions
                        self.Available_outputs[identifier].Time_resolution = time_res
                        self.Available_outputs[identifier].Output_type  = identifier_enum

    def check_if_transient_or_static_output(self):

        # If the outputs are in the root root_path, we have a static forcing
        files = os.listdir(self.root_path)

        # Check if we have the standard quincy output structure
        if "output" in files:
            files_in_output = os.listdir(os.path.join(self.root_path ,'output'))
            self.output_files_path = os.path.join(self.root_path ,'output')
            self.post_processing_path = os.path.join(self.root_path, 'postprocessing')
            self.folder_structure_type = Folder_structure_type.Standard

            for file in files_in_output:
                if '.nc' in file:
                    if self.static_identifier in file:
                        self.forcing_mode = ForcingMode.STATIC
                        return

                    if self.scenario_identifier in file:
                        self.forcing_mode = ForcingMode.TRANSIENT
                        return

                    #in case we only have spinup
                    if self.spinup_identifier in file:
                        self.forcing_mode = ForcingMode.TRANSIENT

        for file in files:
            if '.nc' in file:
                self.folder_structure_type = Folder_structure_type.Test_bed
                self.output_files_path = self.root_path
                self.post_processing_path = self.root_path
                self.forcing_mode = ForcingMode.STATIC
                return

        if self.folder_structure_type == Folder_structure_type.Invalid:
            print("Could not determine folder structure of Quincy output. Available files:")
            print(files)
            exit(-1)

    def get_diagnostic_identifier(self):
        files = os.listdir(self.output_files_path)
        for file in files:
            for potential_identifier in self.diagonstic_identifier_list:
                if potential_identifier in file:
                    self.diagnostic_identifier = potential_identifier
                    return

    def get_time_res_from_string(self, time_str):
        return Output_Time_Res[time_str.capitalize()]

    def get_output_type_from_string(self, identifier_str):
        if identifier_str == self.static_identifier:
            return Output_type.Static
        elif identifier_str == self.spinup_identifier:
            return Output_type.Spinup
        elif identifier_str == self.scenario_identifier:
            return Output_type.Scenario
        elif identifier_str == self.diagnostic_identifier:
            return Output_type.Diagnostic
        else:
            print("Invalid output type identifier")

