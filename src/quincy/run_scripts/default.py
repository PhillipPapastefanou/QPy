from src.quincy.base.Namelist import Namelist
from src.quincy.base.NamelistTypes import *


def ApplyDefaultTestbed(namelist : Namelist):
           
    namelist.lnd_phyd_nml.use_plant_hydraulics.value = False
    namelist.lnd_q_assimi_nml.gs_beta_type.value = GsBetaType.SOIL

    namelist.lnd_sb_nml.sb_model_scheme.value = SbModelScheme.SIMPLE_1D
    namelist.lnd_sb_nml.sb_nloss_scheme.value = SbNlossScheme.DYNAMIC
    namelist.lnd_sb_nml.flag_sb_prescribe_nh4.value = False
    namelist.lnd_sb_nml.flag_sb_prescribe_no3.value = False
    namelist.lnd_sb_nml.flag_sb_prescribe_po4.value = True

    namelist.lnd_veg_nml.veg_bnf_scheme.value = VegBnfScheme.DYNAMIC
    namelist.lnd_sb_nml.flag_mycorrhiza.value        = False
    namelist.lnd_sb_nml.flag_mycorrhiza_org.value    = False
    namelist.lnd_sb_nml.flag_mycorrhiza_prim.value   = False

    namelist.lnd_q_assimi_nml.flag_t_resp_acclimation.value  = True
    namelist.lnd_q_assimi_nml.flag_t_jmax_acclimation.value  = True
    namelist.lnd_q_assimi_nml.flag_optimal_Nfraction.value   = False
    namelist.lnd_q_assimi_nml.ncanopy.value                  = 10
    namelist.lnd_q_assimi_nml.canopy_layer_scheme.value      = CanopyLayerScheme.FAPAR
    namelist.lnd_q_assimi_nml.canopy_conductance_scheme_string.value= CanopyConductanceScheme.MEDLYN

    namelist.lnd_veg_nml.biomass_alloc_scheme.value = BiomassAllocScheme.DYNAMIC
    namelist.lnd_veg_nml.leaf_stoichom_scheme.value = LeafStoichomScheme.DYNAMIC
    namelist.lnd_veg_nml.flag_dynamic_roots.value= True
    namelist.lnd_veg_nml.flag_dynroots_h2o_n_limit.value = False
    namelist.lnd_veg_nml.flag_herbivory.value = False

    namelist.lnd_sb_nml.sb_adsorp_scheme.value = SbAdsorbScheme.ECA_PART
    namelist.base_ctl.flag_slow_sb_pool_spinup_accelerator.value = False

    namelist.lnd_dist_fire_nml.flag_dfire.value = False
    namelist.jsb_forcing_ctl.flag_forcing_with_snow_data.value = False
    namelist.jsb_forcing_ctl.simulation_length_number.value = 20
    namelist.base_ctl.output_end_last_day_year.value = 1
    namelist.base_ctl.output_end_last_day_year.value = 20
    namelist.base_ctl.output_interval_flux.value  = OutputIntervalFlux.DAILY
    namelist.base_ctl.output_interval_pool.value  = OutputIntervalPool.DAILY
    
    namelist.jsb_rad_nml.use_alb_mineralsoil_const.value = True

def ApplyDefaultSiteLevel(namelist : Namelist):
           
    namelist.lnd_phyd_nml.use_plant_hydraulics.value = False
    namelist.lnd_q_assimi_nml.gs_beta_type.value = GsBetaType.SOIL

    namelist.lnd_sb_nml.sb_model_scheme.value = SbModelScheme.SIMPLE_1D
    namelist.lnd_sb_nml.sb_nloss_scheme.value = SbNlossScheme.DYNAMIC
    namelist.lnd_sb_nml.flag_sb_prescribe_nh4.value = False
    namelist.lnd_sb_nml.flag_sb_prescribe_no3.value = False
    namelist.lnd_sb_nml.flag_sb_prescribe_po4.value = False

    namelist.lnd_veg_nml.veg_bnf_scheme.value = VegBnfScheme.DYNAMIC
    namelist.lnd_sb_nml.flag_mycorrhiza.value        = False
    namelist.lnd_sb_nml.flag_mycorrhiza_org.value    = False
    namelist.lnd_sb_nml.flag_mycorrhiza_prim.value   = False

    namelist.lnd_q_assimi_nml.flag_t_resp_acclimation.value  = True
    namelist.lnd_q_assimi_nml.flag_t_jmax_acclimation.value  = True
    namelist.lnd_q_assimi_nml.flag_optimal_Nfraction.value   = False
    namelist.lnd_q_assimi_nml.ncanopy.value                  = 10
    namelist.lnd_q_assimi_nml.canopy_layer_scheme.value      = CanopyLayerScheme.FAPAR
    namelist.lnd_q_assimi_nml.canopy_conductance_scheme_string.value= CanopyConductanceScheme.MEDLYN

    namelist.lnd_veg_nml.biomass_alloc_scheme.value = BiomassAllocScheme.DYNAMIC
    namelist.lnd_veg_nml.leaf_stoichom_scheme.value = LeafStoichomScheme.DYNAMIC
    namelist.lnd_veg_nml.flag_dynamic_roots.value= True
    namelist.lnd_veg_nml.flag_dynroots_h2o_n_limit.value = False
    namelist.lnd_veg_nml.flag_herbivory.value = False

    namelist.jsb_hydro_nml.quincy_nsoil_w.value = 15
    namelist.jsb_hydro_nml.qs_soil_depth.value = 9.5
     
    namelist.lnd_sb_nml.sb_adsorp_scheme.value = SbAdsorbScheme.ECA_PART
    namelist.lnd_sb_nml.flag_sb_interactive_n.value = False
    namelist.base_ctl.flag_slow_sb_pool_spinup_accelerator.value = True

    namelist.lnd_dist_fire_nml.flag_dfire.value = False
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
    namelist.jsb_forcing_ctl.flag_forcing_with_snow_data.value = False

            