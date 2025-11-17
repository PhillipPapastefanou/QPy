from enum import Enum


class LandcoverClass(Enum):
    BARE_SOIL                   = 0
    GLACIER                     = 1
    LAKE                        = 2
    NATURAL_FOREST              = 3
    NATURAL_GRASSLAND           = 4
    OTHER_NATURAL_VEGETATION    = 5
    CROPS                       = 6
    PASTURES                    = 7

class Growthform(Enum):
    ITREE                       = 1
    IGRASS                      = 2
    ICROP                       = 3

class PsPathway(Enum):
    IC3PHOT                     = 1
    IC4PHOT                     = 2

class PhenologyType(Enum):
    NONE                        = 0
    IEVERGREEN                  = 1
    ISUMMERGREEN                = 2
    IRAINGREEN                  = 3
    IPERENNIAL                  = 4
    ICROP_PHENOLOGY             = 5

