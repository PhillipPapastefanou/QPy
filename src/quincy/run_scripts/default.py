from src.quincy.base.Namelist import Namelist
from src.quincy.base.NamelistTypes import *


def ApplyDefaultTestbed(namelist : Namelist):
           
    namelist.phyd_ctl.use_plant_hydraulics.value = False
    namelist.assimilation_ctl.gs_beta_type.value = GsBetaType.PLANT

    namelist.soil_biogeochemistry_ctl.sb_model_scheme.value = SbModelScheme.SIMPLE_1D
    namelist.soil_biogeochemistry_ctl.sb_nloss_scheme.value = SbNlossScheme.DYNAMIC
    namelist.soil_biogeochemistry_ctl.flag_sb_prescribe_nh4.value = False
    namelist.soil_biogeochemistry_ctl.flag_sb_prescribe_no3.value = False
    namelist.soil_biogeochemistry_ctl.flag_sb_prescribe_po4.value = True

    namelist.vegetation_ctl.veg_bnf_scheme.value = VegBnfScheme.DYNAMIC
    namelist.soil_biogeochemistry_ctl.flag_mycorrhiza.value        = False
    namelist.soil_biogeochemistry_ctl.flag_mycorrhiza_org.value    = False
    namelist.soil_biogeochemistry_ctl.flag_mycorrhiza_prim.value   = False

    namelist.assimilation_ctl.flag_t_resp_acclimation.value  = True
    namelist.assimilation_ctl.flag_t_jmax_acclimation.value  = True
    namelist.assimilation_ctl.flag_optimal_Nfraction.value   = False
    namelist.assimilation_ctl.ncanopy.value                  = 10
    namelist.assimilation_ctl.canopy_layer_scheme.value      = CanopyLayerScheme.FAPAR
    namelist.assimilation_ctl.canopy_conductance_scheme.value= CanopyConductanceScheme.MEDLYN

    namelist.vegetation_ctl.biomass_alloc_scheme.value = BiomassAllocScheme.FIXED
    namelist.vegetation_ctl.leaf_stoichom_scheme.value = LeafStoichomScheme.FIXED
    namelist.vegetation_ctl.flag_dynamic_roots.value= True
    namelist.vegetation_ctl.flag_dynroots_h2o_n_limit.value = False
    namelist.vegetation_ctl.flag_herbivory.value = False

    namelist.spq_ctl.soil_depth.value = 5.7
    namelist.spq_ctl.nsoil_water.value = 5
    namelist.spq_ctl.nsoil_energy.value = 5

    namelist.soil_biogeochemistry_ctl.sb_adsorp_scheme.value = SbAdsorbScheme.ECA_PART
    namelist.base_ctl.flag_slow_sb_pool_spinup_accelerator.value = False

    namelist.dist_fire_ctl.flag_dfire.value = False
    namelist.jsb_forcing_ctl.simulation_length_number.value = 20
    namelist.base_ctl.output_end_last_day_year.value = 1
    namelist.base_ctl.output_end_last_day_year.value = 20
    namelist.base_ctl.output_interval_flux.value  = OutputIntervalFlux.TIMESTEP
    namelist.base_ctl.output_interval_pool.value  = OutputIntervalPool.TIMESTEP

def ApplyDefaultSiteLevel(namelist : Namelist):
           
    namelist.phyd_ctl.use_plant_hydraulics.value = False
    namelist.assimilation_ctl.gs_beta_type.value = GsBetaType.SOIL

    namelist.soil_biogeochemistry_ctl.sb_model_scheme.value = SbModelScheme.SIMPLE_1D
    namelist.soil_biogeochemistry_ctl.sb_nloss_scheme.value = SbNlossScheme.DYNAMIC
    namelist.soil_biogeochemistry_ctl.flag_sb_prescribe_nh4.value = False
    namelist.soil_biogeochemistry_ctl.flag_sb_prescribe_no3.value = False
    namelist.soil_biogeochemistry_ctl.flag_sb_prescribe_po4.value = False

    namelist.vegetation_ctl.veg_bnf_scheme.value = VegBnfScheme.DYNAMIC
    namelist.soil_biogeochemistry_ctl.flag_mycorrhiza.value        = False
    namelist.soil_biogeochemistry_ctl.flag_mycorrhiza_org.value    = False
    namelist.soil_biogeochemistry_ctl.flag_mycorrhiza_prim.value   = False

    namelist.assimilation_ctl.flag_t_resp_acclimation.value  = True
    namelist.assimilation_ctl.flag_t_jmax_acclimation.value  = True
    namelist.assimilation_ctl.flag_optimal_Nfraction.value   = False
    namelist.assimilation_ctl.ncanopy.value                  = 10
    namelist.assimilation_ctl.canopy_layer_scheme.value      = CanopyLayerScheme.FAPAR
    namelist.assimilation_ctl.canopy_conductance_scheme.value= CanopyConductanceScheme.MEDLYN

    namelist.vegetation_ctl.biomass_alloc_scheme.value = BiomassAllocScheme.DYNAMIC
    namelist.vegetation_ctl.leaf_stoichom_scheme.value = LeafStoichomScheme.DYNAMIC
    namelist.vegetation_ctl.flag_dynamic_roots.value= False
    namelist.vegetation_ctl.flag_dynroots_h2o_n_limit.value = False
    namelist.vegetation_ctl.flag_herbivory.value = False

    namelist.spq_ctl.soil_depth.value = 9.5
    namelist.spq_ctl.nsoil_water.value = 15
    namelist.spq_ctl.nsoil_energy.value = 15
    
    

    namelist.soil_biogeochemistry_ctl.sb_adsorp_scheme.value = SbAdsorbScheme.ECA_PART
    namelist.base_ctl.flag_slow_sb_pool_spinup_accelerator.value = False

    namelist.dist_fire_ctl.flag_dfire.value = False
    namelist.jsb_forcing_ctl.simulation_length_number.value = 20
    namelist.base_ctl.output_end_last_day_year.value = 1
    namelist.base_ctl.output_end_last_day_year.value = 20
    namelist.base_ctl.output_interval_flux.value  = OutputIntervalFlux.DAILY
    namelist.base_ctl.output_interval_pool.value  = OutputIntervalPool.DAILY
    

    namelist.jsb_forcing_ctl.forcing_mode.value = ForcingMode.TRANSIENT
    namelist.jsb_forcing_ctl.n_deposition_scheme.value = "dynamic"
    namelist.jsb_forcing_ctl.p_deposition_scheme.value = "dynamic"
    namelist.jsb_forcing_ctl.flag_read_dC13.value = True
    namelist.jsb_forcing_ctl.flag_read_DC14.value = True
    
    namelist.jsb_rad_nml.use_alb_mineralsoil_const.value = True
            