from enum import Enum

class NamelistItem:
    def __init__(self, value):
        self.value = value
        self.default = value
        self.parsed = False

# Category names double as the namelist group name quincy's Fortran position_nml()
# actually searches for (case-insensitive literal text match, see mo_namelist.f90),
# so these must match the real quincy namelist group names, not arbitrary labels.
class NamelistCategories(Enum):
    LND_VEG_NML         = 0   # was VEGETATION_CTL
    LND_DIST_FIRE_NML   = 1   # was DIST_FIRE_CTL
    LND_Q_ASSIMI_NML    = 2   # was ASSIMILATION_CTL
    LND_Q_PHENO_NML     = 3   # was PHENOLOGY_CTL
    LND_PHYD_NML        = 4   # was PHYD_CTL
    GRID_CTL            = 6
    LND_SB_NML          = 8   # was SOIL_BIOGEOCHEMISTRY_CTL; also used by Paramlist's SB_CTL (same real group)
    BASE_CTL            = 9
    JSB_FORCING_CTL     = 10
    JSB_RAD_NML         = 12  # also used by Paramlist's JSB_RAD_NML (same real group)
    QS_SHARED_NML       = 14 #For Paramlist; was SHARED_CTL
    LND_Q_SYL_NML       = 17  # was Q_SYL_CTL
    LND_Q_AGR_NML       = 18  # was Q_AGR_CTL
    JSB_TURB_NML        = 19
    JSB_HYDRO_NML       = 20
    JSB_SSE_NML         = 21
    JSB_SEB_NML         = 22

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
    DYNAMIC = 1
class SbModelScheme(Enum):
    SIMPLE_1D = 0
    JSM = 1
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

class JSBSoilHydModelType(Enum):
    VANGENUCHTEN = 0
    BROOKSCOREY = 1
    CAMPBELL = 2

# Namelist group names as previously (incorrectly) used by QPy, mapped to the
# current, correct NamelistCategories member. Namelist.slm files written by older
# QPy versions contain these old spellings (e.g. "&VEGETATION_CTL") in their
# group headers; NamelistReader falls back to this table so such files - often
# used as "base" templates by run scripts - still parse correctly.
LEGACY_NAMELIST_CATEGORY_ALIASES = {
    "DIST_FIRE_CTL":            "LND_DIST_FIRE_NML",
    "VEGETATION_CTL":           "LND_VEG_NML",
    "ASSIMILATION_CTL":         "LND_Q_ASSIMI_NML",
    "PHENOLOGY_CTL":            "LND_Q_PHENO_NML",
    "PHYD_CTL":                 "LND_PHYD_NML",
    "Q_AGR_CTL":                "LND_Q_AGR_NML",
    "Q_SYL_CTL":                "LND_Q_SYL_NML",
    "SOIL_BIOGEOCHEMISTRY_CTL": "LND_SB_NML",
}