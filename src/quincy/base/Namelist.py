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
    elif ctl_category == NamelistCategories.JSB_RAD_NML:
        return JSB_RAD_NML()
    elif ctl_category == NamelistCategories.Q_SH_CTL:
        return Q_SH_CTL()
    else:
        print(f"Unknown CTL: {ctl_category}")
        return 0

class VEGETATION_CTL:
    def __init__(self):        
        self.veg_bnf_scheme             = NamelistItem(VegBnfScheme.DYNAMIC)
        self.veg_dynamics_scheme        = NamelistItem(VegDynamicsScheme.POPULATION)        
        self.biomass_alloc_scheme       = NamelistItem(BiomassAllocScheme.FIXED)
        self.leaf_stoichom_scheme       = NamelistItem(LeafStoichomScheme.FIXED)
        self.plant_functional_type_id   = NamelistItem(4)
        # roots across soil layers: fixed after init or dynamic over time
        self.flag_dynamic_roots         = NamelistItem(True)
        self.flag_dynroots_h2o_n_limit  = NamelistItem(False)
        self.l_use_product_pools        = NamelistItem(False)
        self.flag_herbivory             = NamelistItem(False)

class PHENOLOGY_CTL:
    def __init__(self):
        # LAI at the site, used to set pheno:lai_max
        self.lai_max    =   NamelistItem(3.0)

class DIST_FIRE_CTL:
    def __init__(self):
        # flags for the disturbance fire process
        self.flag_dfire                 = NamelistItem(False)
        self.lightning_frequency        = NamelistItem(0.1)
        self.dfire_modelname            = NamelistItem(DfireModelname.SPITFIRE)
        self.density_human_population   = NamelistItem(0.5)

class ASSIMILATION_CTL:
    def __init__(self):
        # flags
        self.flag_optimal_Nfraction  = NamelistItem(False)
        self.flag_t_resp_acclimation = NamelistItem(False)
        self.flag_t_jmax_acclimation = NamelistItem(False)
        # number of canopy layers [int value, may default to 20]
        self.ncanopy = NamelistItem(8)
        # canopy layer depth
        # calculation[standard = 0.5, fapar]
        self.canopy_layer_scheme        = NamelistItem(CanopyLayerScheme.FAPAR)
        # calculation of gs_cl following Medlyn [default] or Ball/Berry
        self.canopy_conductance_scheme  = NamelistItem(CanopyConductanceScheme.MEDLYN)
        # Determines if stomatal conductances should be regulated by the plant or the soil
        self.gs_beta_type               = NamelistItem(GsBetaType.PLANT)

class PHYD_CTL:
    def __init__(self):
        self.use_plant_hydraulics = NamelistItem(False)

class RADIATION_CTL:
    def __init__(self):
        # No values here, yet
        dummy = 0

class GRID_CTL:
    def __init__(self):
        self.longitude = NamelistItem(0.0)
        self.latitude  = NamelistItem(50.0)

class SPQ_CTL:
    def __init__(self):
        self.flag_snow     = NamelistItem(False)
        self.nsoil_energy  = NamelistItem(5)
        self.nsoil_water   = NamelistItem(5)
        self.soil_depth    = NamelistItem(5.7)
        self.soil_awc_prescribe     = NamelistItem(300.0)
        self.soil_theta_prescribe   = NamelistItem(1.0)
        self.elevation = NamelistItem(0.0)
        
        self.soil_sand    = NamelistItem(0.4)
        self.soil_silt    = NamelistItem(0.3)
        self.soil_clay    = NamelistItem(0.3)
        
        self.bulk_density = NamelistItem(1500.0)
        
        self.saxtonA = NamelistItem(-0.2E-4)
        self.saxtonB    = NamelistItem(-10.0)
        self.kdiff_sat_sl    = NamelistItem(1E-6)
        self.theta_sat_sl    = NamelistItem(0.5)

class Q_SH_CTL:
    def __init__(self):
        self.active                = NamelistItem(True)
        self.flag_stand_harvest    = NamelistItem(False)
        self.stand_replacing_year  = NamelistItem(1500)
        self.harvest_fraction      = NamelistItem(1.0)
        self.harvest_active_in_qs  = NamelistItem(False)
class SOIL_BIOGEOCHEMISTRY_CTL:
    def __init__(self):
        self.sb_model_scheme  = NamelistItem(SbModelScheme.SIMPLE_1D)
        self.sb_nloss_scheme  = NamelistItem(SbNlossScheme.FIXED)
        self.sb_bnf_scheme    = NamelistItem(SbBnfScheme.DYNAMIC)
        self.sb_adsorp_scheme = NamelistItem(SbAdsorbScheme.ECA_FULL)
        # N & P flags
        self.flag_sb_prescribe_nh4 = NamelistItem(False)
        self.flag_sb_prescribe_no3 = NamelistItem(False)
        self.flag_sb_prescribe_po4 = NamelistItem(False)
        # mycorrhiza flags
        self.flag_mycorrhiza       = NamelistItem(False)
        self.flag_mycorrhiza_org   = NamelistItem(False)
        self.flag_mycorrhiza_prim  = NamelistItem(False)
        # JSM flags
        self.flag_sb_jsm_transport    = NamelistItem(False)
        self.flag_sb_jsm_litter_input = NamelistItem(False)
        self.flag_sb_jsm_OM_sorption  = NamelistItem(False)
        # soil flags
        self.flag_sb_double_langmuir  = NamelistItem(False)
        # parameter values
        self.usda_taxonomy_class    = NamelistItem(1)
        self.nwrb_taxonomy_class    = NamelistItem(1)
        self.soil_ph                = NamelistItem(6.5)
        self.soil_p_depth           = NamelistItem(0.5)
        self.soil_p_labile          = NamelistItem(50.0)
        self.soil_p_slow            = NamelistItem(70.0)
        self.soil_p_occluded        = NamelistItem(150.0)
        self.soil_p_primary         = NamelistItem(100.0)
        self.qmax_org_fine_particle = NamelistItem(6.5537)
class BASE_CTL:
    def __init__(self):
        # basic model config
        self.dtime_step_length_sec = NamelistItem(1800.0)
        #  QUINCY model: land plant soil canopy test_canopy test_radiation
        self.quincy_model_name = NamelistItem(QuincyModelName.LAND)
        # git repository commit
        self.git_branch = NamelistItem("not_set")
        self.git_commit_SHA = NamelistItem("not_set")
        self.code_has_changed_since_SHA = NamelistItem(True)
        # author
        self.simulation_run_by = NamelistItem("not_set")
        # first and last year of forcing data available from the forcing file
        self.forcing_file_start_yr = NamelistItem(1500)
        self.forcing_file_last_yr = NamelistItem(1500)
        # model output
        self.output_interval_pool = NamelistItem(OutputIntervalPool.WEEKLY)
        self.output_interval_flux = NamelistItem(OutputIntervalFlux.WEEKLY)
        self.output_interval_pool_spinup = NamelistItem(OutputIntervalPool.YEARLY)
        self.output_interval_flux_spinup = NamelistItem(OutputIntervalFlux.YEARLY)
        self.output_start_first_day_year = NamelistItem(1)
        self.output_end_last_day_year = NamelistItem(30)
        #  transient simulations with a fluxnet-type site-set
        #  timestep-output for last full forcing period of the transient simulation after spinup, with a fluxnet-type site-set
        self.fluxnet_type_transient_timestep_output = NamelistItem(False)
        # years with static forcing available (site specific)
        self.fluxnet_static_forc_start_yr = NamelistItem(1500)
        self.fluxnet_static_forc_last_yr = NamelistItem(1500)
        # site-set specific simulation, e.g., transient with EucFACE
        self.sim_siteset_specific = NamelistItem("none")
        # generate forcing file for the standalone soil model (veg%litterfall pool plus rate modifiers) per timestep [FALSE TRUE]
        self.flag_generate_soil_forcing_stat  = NamelistItem(False)
        self.flag_generate_soil_forcing_trans = NamelistItem(False)
        # write sb/veg output - only possible for netcdf output [FALSE TRUE]
        self.flag_write_sb_output  = NamelistItem(False)
        self.flag_write_veg_output = NamelistItem(False)
        # set parameter values from file [FALSE TRUE] and use absolute (new) values or make proportional changes
        self.set_parameter_values_from_file = NamelistItem(False)
        self.set_parameter_values_proportional = NamelistItem(False)
        # use only the 1st year of climate input [FALSE TRUE]
        self.flag_climate_forcing_one_year = NamelistItem(False)
        # flag for site-set SPP_1685; soil layer specific texture information for simple_1d and jsm
        self.flag_spp1685 = NamelistItem(False)
        # element variables (infrastructure) used in bgc_material (carbon is assumed to be always TRUE)
        self.include_nitrogen   = NamelistItem(True)
        self.include_phosphorus = NamelistItem(True)
        self.include_carbon13   = NamelistItem(True)
        self.include_carbon14   = NamelistItem(True)
        self.include_nitrogen15 = NamelistItem(True)
        # File (with path) to a file containing a list of selected output variables (only used for NetCDF output)
        self.file_sel_output_variables = NamelistItem("not_set")

        self.flag_slow_sb_pool_spinup_accelerator           = NamelistItem(True)
        self.slow_sb_pool_spinup_accelerator_frequency      = NamelistItem(100)
        self.slow_sb_pool_spinup_accelerator_length         = NamelistItem(1000)
        self.slow_sb_pool_spinup_accelerator_start_year     = NamelistItem(300)
        self.slow_sb_pool_spinup_accelerator_max_executions = NamelistItem(4)

class JSB_FORCING_CTL:
    def __init__(self):
        # mo_jsb4_forcing
        # options
        self.n_deposition_scheme = NamelistItem("none")
        self.p_deposition_scheme = NamelistItem("none")
        self.forcing_mode = NamelistItem(ForcingMode.STATIC)
        # use daily or timestep forcing; in case of daily forcing the weather generator is used
        self.is_daily_forcing = NamelistItem(False)
        # flags
        self.flag_read_dC13 = NamelistItem(False)
        self.flag_read_DC14 = NamelistItem(False)
        # simulation length
        # units: y years, w weeks, d days
        self.simulation_length_unit          = NamelistItem(SimulationLengthUnit.Y)
        # integer values
        self.simulation_length_number        = NamelistItem(30)
        # options for transient forcing mode (as compared to static)
        self.transient_spinup_start_year     = NamelistItem(1901)
        self.transient_spinup_end_year       = NamelistItem(1930)
        self.transient_spinup_years          = NamelistItem(500)
        self.transient_simulation_start_year = NamelistItem(1901)
        self.flag_forcing_co2_const          = NamelistItem(False)

class JSB_RAD_NML:
    def __init__(self):
        # Use TRUE for jsbach_lite, FALSE for jsbach_pfts/jsbach_jedi
        self.use_alb_veg_simple         = NamelistItem(False)
        #self.use_alb_canopy = False
        self.use_alb_mineralsoil_const  = NamelistItem(True)
        self.bc_filename                = NamelistItem('bc_land_phys.nc')
        self.ic_filename                = NamelistItem('ic_land_soil.nc')

class Namelist:
    def __init__(self):
        # Initialise namelist categories with defaults
        self.dist_fire_ctl             = DIST_FIRE_CTL()
        self.vegetation_ctl            = VEGETATION_CTL()
        self.assimilation_ctl          = ASSIMILATION_CTL()
        self.phenology_ctl             = PHENOLOGY_CTL()
        self.phyd_ctl                  = PHYD_CTL()
        self.grid_ctl                  = GRID_CTL()
        self.spq_ctl                   = SPQ_CTL()
        self.q_sh_ctl                  = Q_SH_CTL()
        self.soil_biogeochemistry_ctl  = SOIL_BIOGEOCHEMISTRY_CTL()
        self.base_ctl                  = BASE_CTL()
        self.jsb_forcing_ctl           = JSB_FORCING_CTL()
        self.jsb_rad_nml               = JSB_RAD_NML()


    def check_if_parsed(self):
        for cat_str in vars(self):
            cat = getattr(self, cat_str)
            
            for var_str in vars(cat):
                item = getattr(cat, var_str)
                if not item.parsed:
                    print(f"Cat {cat}, var {var_str} has note been parsed")


