from src.quincy.base.LctlibTypes import *
from src.quincy.base.PFTTypes import PftQuincy

class Lctlib:
    def __init__(self):
        # Generate PFT Lct items and initialize with dummies
        self.data = {i : Lctlib_Item(i) for i in PftQuincy}

        self.title_string = "not_set"

    def __getitem__(self, key):
        return self.data[key]
    def __setitem__(self, key, value):
        self.data[key] = value

    def set_row(self, variable , values):
        if len(values) == len(PftQuincy):
            var_type = type(getattr(self.data[PftQuincy.BED], variable))
            i = 0
            for pft in PftQuincy:

                if var_type == int:
                    setattr(self.data[pft], variable, int(values[i]))
                elif var_type == float:
                    setattr(self.data[pft], variable, float(values[i]))

                elif var_type == LandcoverClass:
                    setattr(self.data[pft], variable, LandcoverClass(int(values[i])))
                elif var_type == Growthform:
                    setattr(self.data[pft], variable, Growthform(int(values[i])))
                elif var_type == PsPathway:
                    setattr(self.data[pft], variable, PsPathway(int(values[i])))
                elif var_type == PhenologyType:
                    setattr(self.data[pft], variable, PhenologyType(int(values[i])))
                else:
                    print(f"Could not parse {variable} of type {var_type}. Unkown type.")
                i+=1
        else:
            print(f"Could not set {values} to {variable}. Unequal lenght!")

class Lctlib_Item:

    #set Arbitrary defaults
    def __init__(self, pft: PftQuincy):

        self.name = pft.name


        # LctNumber: Landcover type index numbers (not used in the model)
        self.LctNumber = 0
        self.LandcoverClass = LandcoverClass.GLACIER
        self.growthform = Growthform.ITREE
        self.ps_pathway = PsPathway.IC3PHOT
        self.phenology_type = PhenologyType.ISUMMERGREEN

        # lai_max: maximum leaf area index (--) only used for CANOPY mode
        self.lai_max = 0.0
        # vegetation_height: Vegetation height [m] only used for CANOPY mode
        self.vegetation_height = 0.0
        # sla: specific leaf area (mm / mgDW)
        # From Kattge et al. 2011, Table 5, converted internally from (mm/mgDW) to (m2/mol C)
        self.sla = 0.0
        # sigma_vis: single leaf scattering albedo in the visible range
        # extrapolated from Otto, 2014, BG for trees and Spitter et al. 1986 for grasses
        self.sigma_vis = 0.0
        # sigma_nir: single leaf scattering albedo in the near infrared range
        # extrapolated from Otto, 2014, BG for trees and Spitter et al. 1986 for grasses
        self.sigma_nir = 0.0
        # omega_clumping: canopy clumping factor
        self.omega_clumping = 0.0
        # crown_shape_factor: crown shape factor = 3.8 - 0.46 * crown depth / crown diameter, limited to range 1-3.34
        # based on Campell and Norman 1998, eq. 15.35
        self.crown_shape_factor = 0.0
        # cn_leaf: default leaf nitrogen concentration (mgN/gDW)
        # From Kattge et al. 2011, Table 5, converted internally from nitrogen concentration (mg/gDW) to CN mol C / mol N
        self.cn_leaf = 0.0
        # cn_leaf_min: Minimum leaf N for dynamic stoichiometry  (mgN/gDW)
        # Tuned from OCN
        self.cn_leaf_min = 0.0
        # cn_leaf_min: Minimum leaf N for dynamic stoichiometry  (mgN/gDW)
        # Tuned from OCN
        self.cn_leaf_min = 0.0
        # cn_leaf_max: Maximum leaf N for dynamic stoichiometry  (mgN/gDW)
        # Tuned from OCN
        self.cn_leaf_max = 0.0
        # np_leaf: default leaf phosphorus concentration (mgP/gDW)
        # From Kattge et al. 2011, Table 5, converted internally from phosphorus concentration (mg/gDW) to NP mol N / mol P
        self.np_leaf = 0.0
        # np_leaf_min: minimum leaf phosphorus concentration (mgP/gDW)
        # Set to 0.5 of fixed np_leaf value, converted internally from phosphorus concentration (mg/gDW) to NP mol N / mol P
        self.np_leaf_min = 0.0
        # np_leaf_max: maximum leaf phosphorus concentration (mgP/gDW)
        # Set to 1.5 of fixed np_leaf value, converted internally from phosphorus concentration (mg/gDW) to NP mol N / mol P
        self.np_leaf_max = 0.0
        # k0_fn_struc: fraction of leaf N not used for photosynthesis (Friend 1997)
        # temporarily tuned to match Amax/N in Kattge etal. 2012, Table 5
        self.k0_fn_struc = 0.0
        # fn_oth_min: minimum fraction of non-photosynthetic leaf N. Calculated using range of leaf N values from GLOPNET
        # Le Maire et al. 2012 (derived from grasses, does not give plausble results for needles)
        # Note: 0.0 is just a placeholder see Read_lctlib() for calculation of actual values
        self.fn_oth_min = 0.0

        # t_jmax_opt: initial value of the temperature optimum of electron transport and its shape parameter (deg C)
        self.t_jmax_opt = 0.0
        # t_jmax_omega:
        self.t_jmax_omega = 18.0

        # g0: intercept and slope of the An ~gs relationship (mmol/micro-mol)
        self.g0 = 0.0
        # g1:
        # g1 in kPa^0.5 as in Lin et al. 2015, Nat CC. OBS: no values for Larches - assigned broad leaved value!
        # g1 values used with the canopy_conductance_scheme=medlyn [default scheme]
        self.g1_medlyn = 0.0
        # g1 in Ball & Berry relationship, tuned to get similar Amax/N values as with Lin et al. g1, canopy_conductance_scheme=ballberry
        self.g1_bberry = 0.0
        # gmin: minimum stomatal conductance (m/s)
        self.gmin = 0.0

        # turnover times

        # tau_leaf: average turnover time of a leaf (months)
        # From Kattge et al. 2011, Table 5, converted internally from month to years
        self.tau_leaf = 0.0
        # tau_fine_root: average turnover time of a fine root (years), Ahrens et al. 2014, NP
        self.tau_fine_root = 0.0
        # tau_coarse_root: average turnover time of a coarse root (years), Ahrens et al. 2014, NP
        self.tau_coarse_root = 0.0
        # tau_branch: turnover time of the fraction of sapwood that is in branches (years)
        self.tau_branch = 0.0
        # tau_sap_wood: turnover time of the sapwood pool (years)
        self.tau_sap_wood = 0.0
        # tau_fruit: turnover time of the fruit pool (years)
        self.tau_fruit = 0.0
        # tau_seed_litter: turnover time of the seed bed to litter (years)
        self.tau_seed_litter = 0.0
        # tau_seed_est: turnover time of the seed bed to establishment (years)
        self.tau_seed_est = 0.0
        # tau_mycorrhiza: turnover time of mycorrhizal fungi (years)
        self.tau_mycorrhiza = 0.0

        # N uptake parameters

        # vmax_uptake_n: vmax of N uptake (~micro-mol N / mol C / s) [714.28_wp ? old value]
        # tuned from OCN's 1.5 gN/gC/1800s
        self.vmax_uptake_n = 0.0
        # vmax_uptake_p: vmax of P uptake (~micro-mol P / mol C / s)
        # tuned from OCN's 1.5 gN/gC/1800s plus changes by Lin following Kavka and Polle 2016 (0.01  micro-mol P / g fine root / min)
        self.vmax_uptake_p = 0.0
        # bnf_base: base nitrogen fixation rate (g N / m2 / year)
        # converted internally to mumol N m-2 s-1
        self.bnf_base = 0.0

        # Vegetation dynamics parameters

        # lambda_est_light: parameter in the Weibull function controlling light-limited establishment
        self.lambda_est_light = 0.0
        # k_est_light: parameter in the Weibull function controlling light-limited establishment
        self.k_est_light = 0.0
        # seed_size: seed size (mol C)
        self.seed_size = 0.0
        # k1_mort_greff: asymptotic growth efficiency mortality rate (1/yr)
        self.k1_mort_greff = 0.0

        # Phenology parameters

        # beta_soil_flush: soil moisture limitation factor on stomatal conductance inducing leaf flushing
        self.beta_soil_flush = 0.0
        # beta_soil_senescence: soil moisture limitation factor on stomatal conductance inducing leaf senescence
        self.beta_soil_senescence = 0.0
        # gdd_req_max: maximum GDD requirement (degC days) in the absence of chilling
        self.gdd_req_max = 0.0
        # k_gdd_dormance: scaling factor in the GDD to number of dormant days relationship (days -1)
        self.k_gdd_dormance = 0.0
        # t_air_senescence: weekly air temperature threshold inducing senescence of leaves ( degC)
        # converted internally to K
        self.t_air_senescence = 0.0
        # min_leaf_age: minimum leaf age before senescence is permitted (days)
        self.min_leaf_age = 0.0

        # Allocation paramters

        # frac_sapwood_branch: fraction of sapwood that is in branches
        self.frac_sapwood_branch = 0.0
        # wood_density: wood density (g C / cm3)
        # converted internally from g/cm3 to mol C m-3
        self.wood_density = 0.0
        # k_latosa: leaf area to sapwood area ratio
        self.k_latosa = 0.0
        # k_crtos: coarse root to sapwood mass ratio
        self.k_crtos = 0.0
        # k_rtos: trade-off parametr for hydraulic investment into sapwood or fine roots
        # Note: 0.0 is just a placeholder see Read_lctlib() for calculation of actual values
        self.k_rtos = 0.0
        # k2_fruit_alloc: maximum fraction of biomass growth going to fruits
        self.k2_fruit_alloc = 0.0

        # allom_k1: paramter in height diameter relationship
        self.allom_k1 = 0.0
        # allom_k2: paramter in height diameter relationship
        self.allom_k2 = 0.0
        # phi_leaf_min: minimum leaf water potential (MPa)
        self.phi_leaf_min = 0.0
        # k_root: fine root hydraulic conductance (10^10 m3 mol-1 s-1 MPa-1)
        # converted internally to m3 mol-1 s-1 MPa-1
        self.k_root = 0.0
        # k_sapwood: sapwood hydraulic conductance (10^3 m2 s-1 MPa-1)
        # converted internally to m2 s-1 MPa-1
        self.k_sapwood = 0.0
        # c0_allom: hydraulic trade-off parameter for fine root growth
        # Note: 0.0 is just a placeholder see Read_lctlib() for calculation of actual values
        self.c0_allom = 0.0
        # fstore_target: the fraction of annual leaf+fine_root biomass production that is the target for the size of the long-term reserve pool
        self.fstore_target = 0.0

        # Soil

        # k_root_dist:
        # tuned according to Jackson et al. 1996, Oecologia, to reproduce their cummulative root distribution profiles
        # only making use of the contrast sclerophyllic, tree, grass
        self.k_root_dist = 0.0
        # k_som_fast_init: fast pools SOM init value, empirically calibrated values to equilibrium soil profiles (unitless)
        self.k_som_fast_init = 0.0
        # k_som_slow_init: slow pools SOM init value, empirically calibrated values to equilibrium soil profiles (unitless)
        self.k_som_slow_init = 0.0


        # Albedo parameters

        # AlbedoLitterVIS: Albedo of litter in the visible range
        self.AlbedoLitterVIS = 0.0
        # AlbedoLitterNIR: Albedo of litter in the near infrared range
        self.AlbedolitterNIR = 0.0

        # Plant hydraulics

        # (MPa)
        self.psi50_xylem = 0.0
        # (1)
        self.slope50_xylem = 0.0
        # (MPa)
        self.psi50_leaf_close = 0.0
        # (1)
        self.slope_leaf_close = 0.0
        # (mol m-1 s-1 MPa-1)
        self.k_xylem_sat = 0.0
        # (1)
        self.root_area_index = 0.0
        # (1?)
        self.eta_stem = 0.0
        # (mol m-2 MPa-1)
        self.kappa_leaf = 0.0
        # (mol m-3 MPa-1)
        self.kappa_stem = 0.0
        # Root scaler
        self.root_scale = 1.0
        # Residual hydraulic conductivity (kg H2O m-2 s-1)
        self.g_res = 0.0