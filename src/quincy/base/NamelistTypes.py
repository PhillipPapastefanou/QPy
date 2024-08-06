from enum import Enum
class NamelistCategories(Enum):
    VEGETATION_CTL      = 0
    DIST_FIRE_CTL       = 1
    ASSIMILATION_CTL    = 2
    PHENOLOGY_CTL       = 3
    PHYD_CTL            = 4
    RADIATION_CTL       = 5
    GRID_CTL            = 6
    SPQ_CTL             = 7
    SOIL_BIOGEOCHEMISTRY_CTL = 8
    BASE_CTL            = 9
    JSB_FORCING_CTL     = 10

class GsBetaType(Enum):
    PLANT = 0
    SOIL = 1
class CanopyConductanceScheme(Enum):
    MEDLYN = 0
    BALLBERRY = 1
class DfireModelname(Enum):
    SPITFIRE = 0
class CanopyLayerScheme(Enum):
    FAPAR = 0
class VegBnfScheme(Enum):
    DYNAMIC = 0
    UNLIMITED = 1
class VegDynamicsScheme(Enum):
    POPULATION = 0
class BiomassAllocScheme(Enum):
    FIXED = 0
    DYNAMIC = 1
class LeafStoichomScheme(Enum):
    FIXED = 0
class SbModelScheme(Enum):
    SIMPLE_1D = 0
class SbNlossScheme(Enum):
    FIXED = 0
    DYNAMIC = 1
class SbBnfScheme(Enum):
    DYNAMIC = 0
    FIXED   = 1
    UNLIMITED = 2
class SbAdsorbScheme(Enum):
    ECA_FULL = 0
    ECA_PART = 1
class ForcingMode(Enum):
    STATIC    = 0
    TRANSIENT = 1
class SimulationLengthUnit(Enum):
    Y    = 0
    W    = 1
    D    = 2

class OutputIntervalPool(Enum):
    TIMESTEP = 0
    DAILY    = 1
    WEEKLY   = 2
    YEARLY   = 3

class OutputIntervalFlux(Enum):
    TIMESTEP = 0
    DAILY    = 1
    WEEKLY   = 2
    YEARLY   = 3

class QuincyModelName(Enum):
    LAND = 0
    CANOPY = 1
