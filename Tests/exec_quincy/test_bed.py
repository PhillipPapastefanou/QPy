from src.run_scripts.SimulateTestBed import TestBedSim
from src.quincy.base.NamelistTypes import SbAdsorbScheme
from src.quincy.base.NamelistTypes import OutputIntervalPool
from src.quincy.base.NamelistTypes import OutputIntervalFlux
from src.quincy.base.PFTTypes import PftQuincy

quincy_root_path = "/Volumes/BSI/work_scratch/ppapastefanou/src/quincy"

tb_sim = TestBedSim(quincy_root_path)

output_folder = tb_sim.namelist.base_ctl.quincy_model_name
output_folder = "/Volumes/BSI/work_scratch/ppapastefanou/temp/"

# Change namelist parameters
tb_sim.namelist.base_ctl.output_interval_flux       = OutputIntervalFlux.DAILY
tb_sim.namelist.base_ctl.output_interval_pool       = OutputIntervalPool.DAILY
tb_sim.namelist.base_ctl.output_start_first_day_year= 10
tb_sim.namelist.base_ctl.output_end_last_day_year   = 20

tb_sim.namelist.assimilation_ctl.flag_t_jmax_acclimation  = True
tb_sim.namelist.assimilation_ctl.flag_t_resp_acclimation  = True

tb_sim.namelist.soil_biogeochemistry_ctl.flag_sb_prescribe_nh4 = False
tb_sim.namelist.soil_biogeochemistry_ctl.flag_sb_prescribe_no3 = False
tb_sim.namelist.soil_biogeochemistry_ctl.flag_sb_prescribe_po4 = True
tb_sim.namelist.soil_biogeochemistry_ctl.sb_adsorp_scheme      = SbAdsorbScheme.ECA_PART

# Change lctlib parameters
tb_sim.lctlib[PftQuincy.TeBS].g1_medlyn = 25.0

tb_sim.set_up(folder = output_folder)

tb_sim.run()