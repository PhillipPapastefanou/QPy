import os.path

from src.postprocessing.py.qnc_output_parser import QNC_output_parser
from src.postprocessing.py.qnc_defintions import Output_format
from src.postprocessing.py.qnc_std_output_plotting import QNC_std_output_plotting
from src.postprocessing.py.qnc_obs_model_comparer import Obs_Model_Var_List
from src.postprocessing.py.qnc_obs_model_comparer import QNC_Obs_Model_Variable_Pair
from src.postprocessing.py.qnc_obs_model_comparer import QNC_Variable
from src.postprocessing.py.qnc_fluxnet_diagnostics import QNC_Std_Fluxnet_Diagnostics
from src.quincy.base.NamelistTypes import ForcingMode

class QNC_std_output_factory:
    def __init__(self, root_path, output_format,
                 target_categories = []):

        self.root_path = root_path
        self.output_format = output_format

        self.output_Parser = QNC_output_parser(self.root_path)
        self.output_Parser.Read()

        if len(target_categories) > 0:
            self.output_Parser.check_target_categories(target_categories)


    def Calculate_std_output(self):

        self.plotter = QNC_std_output_plotting(
                                    self.output_Parser.output_files_path,
                                    self.output_Parser.post_processing_path,
                                    self.output_format,
                                    self.output_Parser.Available_outputs,
                                    self.output_Parser.Basic_info)

        if self.output_format == Output_format.Single:
            self.plotter.Plot_single_1D()
        elif self.output_format == Output_format.Combined:
            self.plotter.Plot_all_1D()

        if not self.plotter.parsing_success:
            return
        self.plotter.Plot_2d_split()

    def Calculate_fluxnet_stat(self):

        if self.output_Parser.forcing_mode == ForcingMode.STATIC:
            print("Static output does not need to be compared to FLUXNET output.")
            return


        fluxnet_path = os.path.join(self.output_Parser.output_files_path, 'obs.nc')
        if not os.path.exists(fluxnet_path):
            print("Could not find any fluxnet path: ")
            print(fluxnet_path)
            print("Not performing fluxnet analysis")
            exit(-1)

        #Defining standard fluxnet output
        target_variable_list = Obs_Model_Var_List()

        omp = QNC_Obs_Model_Variable_Pair(name="Gc")
        omp.Plus_model_var(QNC_Variable("gc_avg", "Q_ASSIMI"))
        omp.Plus_obs_var(QNC_Variable("Gc"))
        target_variable_list.Add(omp)

        omp = QNC_Obs_Model_Variable_Pair(name="GPP")
        omp.Plus_model_var(QNC_Variable("gpp_avg", "Q_ASSIMI"))
        omp.Plus_obs_var(QNC_Variable("GPP"))
        target_variable_list.Add(omp)

        omp = QNC_Obs_Model_Variable_Pair(name="NEE")
        omp.Plus_model_var(QNC_Variable("het_respiration_avg", "SB"))
        omp.Substract_model_var(QNC_Variable("npp_avg", "VEG"))
        omp.Plus_obs_var(QNC_Variable("NEE"))
        target_variable_list.Add(omp)

        omp = QNC_Obs_Model_Variable_Pair(name="Ga")
        omp.Plus_model_var(QNC_Variable("ga_avg", "A2L"))
        omp.Plus_obs_var(QNC_Variable("Ga"))
        target_variable_list.Add(omp)

        omp = QNC_Obs_Model_Variable_Pair(name="LE")
        omp.Substract_model_var(QNC_Variable("qle_avg", "SPQ"))
        omp.Plus_obs_var(QNC_Variable("LE"))
        target_variable_list.Add(omp)

        omp = QNC_Obs_Model_Variable_Pair(name="H")
        omp.Substract_model_var(QNC_Variable("qh_avg", "SPQ"))
        omp.Plus_obs_var(QNC_Variable("H"))
        target_variable_list.Add(omp)

        omp = QNC_Obs_Model_Variable_Pair(name="Reco")
        omp.Plus_model_var(QNC_Variable("het_respiration_avg", "SB"))
        omp.Plus_model_var(QNC_Variable("gpp_avg", "Q_ASSIMI"))
        omp.Substract_model_var(QNC_Variable("npp_avg", "VEG"))

        omp = QNC_Obs_Model_Variable_Pair(name="PPFD")
        omp.Plus_model_var(QNC_Variable("appfd_avg", "Q_RAD"))
        omp.Plus_obs_var(QNC_Variable("PPFD"))
        target_variable_list.Add(omp)

        fluxnet_diagnostics = QNC_Fluxnet_Diagnostics(rt_path=self.root_path, target_variable_list=target_variable_list)

        # Only perform analysis when we have data
        if fluxnet_diagnostics.Have_fluxnet_variables:
            fluxnet_diagnostics.parse_env_variables()
            fluxnet_diagnostics.Check_output_variables()
            fluxnet_diagnostics.Analyse_and_plot()
