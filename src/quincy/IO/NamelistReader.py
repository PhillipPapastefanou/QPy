from src.quincy.base.Namelist import Generate_CTL_Categories
from src.quincy.base.Namelist import Namelist
from src.quincy.base.NamelistTypes import *


class NamelistReader:
    def __init__(self, filepath):
        self.filepath = filepath
        self.raw_input_lines = self.iread(filepath=filepath)

    def parse(self):
        return self.iparse(self.raw_input_lines)

    def iread(self, filepath):
        raw_input_lines = []
        file = open(filepath, "r")
        while True:
            line = file.readline()
            if not line:
                break
            # Treat each line individually
            # Remove whitespaces
            line= line.strip()
            
            # Ignore lines that are empty
            if line == '':
                continue
            
            # Ignore all lines with a comment and no content at all
            if (len(line) > 0) & (line[0] != '!'):
                raw_input_lines.append(line)
        file.close()
        return raw_input_lines

    def iparse(self, raw_input_lines):
        namelist = Namelist()
        # Initialise class with zero or null
        ctl_class = 0

        for line in raw_input_lines:
            # beginning of ctl
            if line[0] in '&':
                ctl_str = line[1:]
                # Because of inconsistencies in the naming lets make all categories upper in python
                ctl_str = ctl_str.upper()
                try:
                    ctl_enum = NamelistCategories[ctl_str]
                except:
                    print(f"Unimplemented category {ctl_str}")
                    continue
                ctl_class = Generate_CTL_Categories(ctl_enum)

            # end of category
            elif line[0] == "/":
                # Pass information to Namelist file
                x = type(ctl_class).__name__
                setattr(namelist, x.lower(), ctl_class)
                # Reset class
                ctl_class = 0

            # Parse information of class
            else:
                if ctl_class != 0:
                    arr = line.split('=')
                    name = arr[0]
                    #Remove whitespaces
                    name = name.strip()

                    value = arr[1]
                    #Remove the redundant quotes
                    value = value.strip('\"')
                    try:
                        item_type = type(getattr(ctl_class, name))
                    except:
                        print(f"Could not find {name} in {ctl_class}")
                        continue
                    
                    if item_type is not NamelistItem:
                        print(f"Invalid item {item_type}.")
                        continue
                        
                    item = getattr(ctl_class, name)
                    var_type = type(item.value)

                    # Parsing primitive types
                    if var_type is bool:
                        if value == ".TRUE.":
                            item.value = True
                        else:
                            item.value = False

                    elif var_type is float:
                        item.value = float(value)

                    elif var_type is int:
                        item.value = int(value)

                    elif var_type is str:
                        item.value = value



                    # Parsing QUINCY specific enum types
                    elif var_type == CanopyConductanceScheme:
                        self.iparse_enum(item, CanopyConductanceScheme, value)
                    elif var_type == CanopyLayerScheme:
                        self.iparse_enum(item, CanopyLayerScheme, value)

                    elif var_type == GsBetaType:
                        self.iparse_enum(item, GsBetaType, value)

                    elif var_type == DfireModelname:
                        self.iparse_enum(item, DfireModelname, value)

                    elif var_type == VegBnfScheme:
                        self.iparse_enum(item, VegBnfScheme, value)
                    elif var_type == VegDynamicsScheme:
                        self.iparse_enum(item, VegDynamicsScheme, value)
                    elif var_type == BiomassAllocScheme:
                        self.iparse_enum(item, BiomassAllocScheme, value)
                    elif var_type == LeafStoichomScheme:
                        self.iparse_enum(item, LeafStoichomScheme, value)

                    elif var_type == SbModelScheme:
                        self.iparse_enum(item, SbModelScheme, value)
                    elif var_type == SbNlossScheme:
                        self.iparse_enum(item, SbNlossScheme,  value)
                    elif var_type == SbBnfScheme:
                        self.iparse_enum(item, SbBnfScheme,  value)
                    elif var_type == SbAdsorbScheme:
                        self.iparse_enum(item, SbAdsorbScheme,  value)

                    elif var_type == QuincyModelName:
                        self.iparse_enum(item, QuincyModelName,  value)
                    elif var_type == ForcingMode:
                        self.iparse_enum(item, ForcingMode,  value)
                    elif var_type == SimulationLengthUnit:
                        self.iparse_enum(item, SimulationLengthUnit,  value)
                    elif var_type == OutputIntervalPool:
                        self.iparse_enum(item, OutputIntervalPool,  value)
                    elif var_type == OutputIntervalFlux:
                        self.iparse_enum(item, OutputIntervalFlux,  value)
                        
                    elif var_type == JSBSoilHydModelType:
                        self.iparse_enum(item, JSBSoilHydModelType,  value)

                    else:
                        print(f"Could not determine type {var_type} of {name} in class {ctl_class}")
                        
                    item.parsed = True

        return namelist

    def iparse_enum(self, item, enum_type, value):
        try:
            item.value =  enum_type[value.upper()]
            return True
        except:
            print(f"Could not parse {value}")
            return False

        