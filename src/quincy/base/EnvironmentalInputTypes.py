from enum import Enum


class ForcingDataset(Enum):
    FLUXNET2 = 0
    FLUXNET3 = 1
    GLOBAL   = 2

class ForcingType(Enum):
    STATIC    = 0
    TRANSIENT = 1