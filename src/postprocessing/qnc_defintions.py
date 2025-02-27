from enum import Enum

class Output_format(Enum):
    Single = 0,
    Combined = 1

class Folder_structure_type(Enum):
    Standard = 0
    Test_bed = 1
    Invalid = 2

class Simuluation_type(Enum):
    Static = 0
    Transient = 1

class Output_Time_Res(Enum):
    Timestep = 0
    Daily = 1
    Weekly = 2
    Monthly = 3
    Yearly = 4
    Invalid = 6

class Output_type(Enum):
    Spinup = 0
    Scenario = 1
    Diagnostic = 2
    Static = 3
    Invalid = 4

class Second_dim_type(Enum):
    Soil_layer = 0
    Canopy_layer = 1
    Invalid = 2
