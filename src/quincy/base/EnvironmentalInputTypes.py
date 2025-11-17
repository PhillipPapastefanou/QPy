from enum import Enum

class ForcingDataset(Enum):
    FLUXNET2 = 0
    FLUXNET3 = 1
    GLOBAL   = 2
    CRUNCEP  = 3
    
class CruNcepSiteType(Enum):
    ALL = 0
    CUE = 1
    SPP = 2

class SimulationSiteType(Enum):
    ALL = 0
    CUSTOM = 1