from src.quincy.base.NamelistTypes import *

def Generate_CTL_Categories(ctl_category):
    if ctl_category == NamelistCategories.DIST_FIRE_CTL:
        return DIST_FIRE_CTL()
    elif ctl_category == NamelistCategories.ASSIMILATION_CTL:
        return ASSIMILATION_CTL()
    elif ctl_category == NamelistCategories.PHENOLOGY_CTL:
        return PHENOLOGY_CTL()
    elif ctl_category == NamelistCategories.VEGETATION_CTL:
        return VEGETATION_CTL()
    elif ctl_category == NamelistCategories.PHYD_CTL:
        return PHYD_CTL()
    elif ctl_category == NamelistCategories.RADIATION_CTL:
        return RADIATION_CTL()
    elif ctl_category == NamelistCategories.GRID_CTL:
        return GRID_CTL()
    elif ctl_category == NamelistCategories.SPQ_CTL:
        return SPQ_CTL()
    elif ctl_category == NamelistCategories.SOIL_BIOGEOCHEMISTRY_CTL:
        return SOIL_BIOGEOCHEMISTRY_CTL()
    elif ctl_category == NamelistCategories.BASE_CTL:
        return BASE_CTL()
    elif ctl_category == NamelistCategories.JSB_FORCING_CTL:
        return JSB_FORCING_CTL()
    else:
        print(f"Unknown CTL: {ctl_category}")
        return 0

class VEGETATION_CTL:
    def __init__(self):
        self.veg_bnf_scheme             = VegBnfScheme.DYNAMIC
        self.veg_dynamics_scheme        = VegDynamicsScheme.POPULATION
        self.biomass_alloc_scheme       = BiomasAllocScheme.FIXED
        self.leaf_stoichom_scheme       = LeafStoichomScheme.FIXED
        self.plant_functional_type_id   = 4
        # site specific cohort harvest each x years
        self.cohort_harvest_interval    = 80
        # roots across soil layers: fixed after init or dynamic over time
        self.flag_dynamic_roots         = True
        self.flag_dynroots_h2o_n_limit  = False

class PHENOLOGY_CTL:
    def __init__(self):
        # LAI at the site, used to set pheno:lai_max
        self.lai_max=3.0

class DIST_FIRE_CTL:
    def __init__(self):
        # flags for the disturbance fire process
        self.flag_dfire = False
        self.lightning_frequency = 0.1
        self.dfire_modelname = DfireModelname.SPITFIRE
        self.density_human_population = 0.5

class ASSIMILATION_CTL:
    def __init__(self):
        # flags
        self.flag_optimal_Nfraction  = False
        self.flag_t_resp_acclimation = False
        self.flag_t_jmax_acclimation = False
        # number of canopy layers [int value, may default to 20]
        self.ncanopy = 8
        # canopy layer depth
        # calculation[standard = 0.5, fapar]
        self.canopy_layer_scheme = CanopyLayerScheme.FAPAR
        # calculation of gs_cl following Medlyn [default] or Ball/Berry
        self.canopy_conductance_scheme = CanopyConductanceScheme.MEDLYN

class PHYD_CTL:
    def __init__(self):
        self.use_plant_hydraulics = False

class RADIATION_CTL:
    def __init__(self):
        # No values here, yet
        dummy = 0

class GRID_CTL:
    def __init__(self):
        self.longitude = 0.0
        self.latitude  = 50.0

class SPQ_CTL:
    def __init__(self):
        self.flag_snow     = False
        self.nsoil_energy  = 5
        self.nsoil_water   = 5
        self.soil_depth    = 5.7
        self.soil_awc_prescribe     = 300.0
        self.soil_theta_prescribe   = 1.0
        
        self.soil_sand    = 0.4
        self.soil_silt    = 0.3
        self.soil_clay    = 0.3
        self.bulk_density = 1500.0

class SOIL_BIOGEOCHEMISTRY_CTL:
    def __init__(self):
        self.sb_model_scheme  = SbModelScheme.SIMPLE_1D
        self.sb_nloss_scheme  = SbNlossScheme.FIXED
        self.sb_bnf_scheme    = SbBnfScheme.DYNAMIC
        self.sb_adsorp_scheme = SbAdsorbScheme.ECA_FULL
        # N & P flags
        self.flag_sb_prescribe_nh4 = False
        self.flag_sb_prescribe_no3 = False
        self.flag_sb_prescribe_po4 = False
        # mycorrhiza flags
        self.flag_mycorrhiza       = False
        self.flag_mycorrhiza_org   = False
        self.flag_mycorrhiza_prim  = False
        # JSM flags
        self.flag_sb_jsm_transport    = False
        self.flag_sb_jsm_litter_input = False
        self.flag_sb_jsm_OM_sorption  = False
        # soil flags
        self.flag_sb_double_langmuir  = False
        # parameter values
        self.usda_taxonomy_class    = 1
        self.nwrb_taxonomy_class    = 1
        self.soil_ph                = 6.5
        self.soil_p_depth           = 0.5
        self.soil_p_labile          = 50.0
        self.soil_p_slow            = 70.0
        self.soil_p_occluded        = 150.0
        self.soil_p_primary         = 100.0
        self.qmax_org_fine_particle = 6.5537

class BASE_CTL:
    def __init__(self):
        # basic model config
        self.dtime_step_length_sec = 1800.0
        #  QUINCY model: land plant soil canopy test_canopy test_radiation
        self.quincy_model_name = QuincyModelName.LAND
        # git repository commit
        self.git_branch = "not_set"
        self.git_commit_SHA = "not_set"
        self.code_has_changed_since_SHA = True
        # author
        self.simulation_run_by = "not_set"
        # first and last year of forcing data available from the forcing file
        self.forcing_file_start_yr = 1500
        self.forcing_file_last_yr = 1500
        # model output
        self.output_interval_pool = OutputIntervalPool.WEEKLY
        self.output_interval_flux = OutputIntervalFlux.WEEKLY
        self.output_interval_pool_spinup = OutputIntervalPool.YEARLY
        self.output_interval_flux_spinup = OutputIntervalFlux.YEARLY
        self.output_start_first_day_year = 1
        self.output_end_last_day_year = 30
        #  transient simulations with a fluxnet-type site-set
        #  timestep-output for last full forcing period of the transient simulation after spinup, with a fluxnet-type site-set
        self.fluxnet_type_transient_timestep_output = False
        # years with static forcing available (site specific)
        self.fluxnet_static_forc_start_yr = 1500
        self.fluxnet_static_forc_last_yr = 1500
        # site-set specific simulation, e.g., transient with EucFACE
        self.sim_siteset_specific = "none"
        # generate forcing file for the standalone soil model (veg%litterfall pool plus rate modifiers) per timestep [FALSE TRUE]
        self.flag_generate_soil_forcing_stat  = False
        self.flag_generate_soil_forcing_trans = False
        # write sb/veg output - only possible for netcdf output [FALSE TRUE]
        self.flag_write_sb_output  = False
        self.flag_write_veg_output = False
        # set parameter values from file [FALSE TRUE] and use absolute (new) values or make proportional changes
        self.set_parameter_values_from_file = False
        self.set_parameter_values_proportional = False
        # use only the 1st year of climate input [FALSE TRUE]
        self.flag_climate_forcing_one_year = False
        # site specific stand harvest
        self.flag_stand_harvest = False
        self.stand_replacing_year = 1500
        # flag for site-set SPP_1685; soil layer specific texture information for simple_1d and jsm
        self.flag_spp1685 = False
        # element variables (infrastructure) used in bgc_material (carbon is assumed to be always TRUE)
        self.include_nitrogen   = True
        self.include_phosphorus = True
        self.include_carbon13   = True
        self.include_carbon14   = True
        self.include_nitrogen15 = True
        # File (with path) to a file containing a list of selected output variables (only used for NetCDF output)
        self.file_sel_output_variables = "not_set"

class JSB_FORCING_CTL:
    def __init__(self):
        # mo_jsb4_forcing
        # options
        self.n_deposition_scheme = "none"
        self.p_deposition_scheme = "none"
        self.forcing_mode = ForcingMode.STATIC
        # use daily or timestep forcing; in case of daily forcing the weather generator is used
        self.is_daily_forcing = False
        # flags
        self.flag_read_dC13 = False
        self.flag_read_DC14 = False
        # simulation length
        # units: y years, w weeks, d days
        self.simulation_length_unit = SimulationLengthUnit.Y
        # integer values
        self.simulation_length_number = 30
        # options for transient forcing mode (as compared to static)
        self.transient_spinup_start_year = 1901
        self.transient_spinup_end_year = 1930
        self.transient_spinup_years = 500
        self.transient_simulation_start_year = 1901
        self.flag_forcing_co2_const = False

class Namelist:
    def __init__(self):
        # Initialise namelist categories with defaults
        self.dist_fire_ctl             = DIST_FIRE_CTL()
        self.assimilation_ctl          = ASSIMILATION_CTL()
        self.phenology_ctl             = PHENOLOGY_CTL()
        self.vegetation_ctl            = VEGETATION_CTL()
        self.phyd_ctl                  = PHYD_CTL()
        self.radiation_ctl             = RADIATION_CTL()
        self.spq_ctl                   = SPQ_CTL()
        self.soil_biogeochemistry_ctl  = SOIL_BIOGEOCHEMISTRY_CTL()
        self.base_ctl                  = BASE_CTL()
        self.jsb_forcing_ctl           = JSB_FORCING_CTL()
        self.grid_ctl                  = GRID_CTL()


