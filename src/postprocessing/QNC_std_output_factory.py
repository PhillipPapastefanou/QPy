from src.postprocessing.QNC_output_parser import QNC_output_parser
from src.postprocessing.QNC_defintions import OutputFormat
from src.postprocessing.QNC_std_output_plotting import QNC_std_output_plotting
from src.postprocessing.QNC_obs_model_comparer import Obs_Model_Var_List
from src.postprocessing.QNC_obs_model_comparer import QNC_Obs_Model_Variable_Pair
from src.postprocessing.QNC_obs_model_comparer import QNC_Variable
from src.postprocessing.QNC_fluxnet_diagnostics import QNC_Fluxnet_Diagnostics

class QNC_std_output_factory:
    def __init__(self, root_path, output_format,
                 target_categories = []):

        self.root_path = root_path
        self.output_format = output_format

        self.Output_Parser = QNC_output_parser(self.root_path)
        self.Output_Parser.read()

        if len(target_categories) > 0:
            self.Output_Parser.check_target_categories(target_categories)


    def calculate_std_output(self):

        self.plotter = QNC_std_output_plotting(
                                    self.Output_Parser.output_files_path,
                                    self.output_format,
                                    self.Output_Parser.Available_outputs,
                                    self.Output_Parser.Basic_info)

        if self.output_format == OutputFormat.Single:
            self.plotter.plot_single_1D()
        elif self.output_format == OutputFormat.Combined:
            self.plotter.plot_all_1D()

        self.plotter.plot_2d_split()

    def calculate_fluxnet_stat(self):

        #Defining standard fluxnet output
        target_variable_list = Obs_Model_Var_List()

        omp = QNC_Obs_Model_Variable_Pair(name="Gc")
        omp.Plus_model_var(QNC_Variable("gc_avg", "ASSIMI"))
        omp.Plus_obs_var(QNC_Variable("Gc"))
        target_variable_list.Add(omp)

        omp = QNC_Obs_Model_Variable_Pair(name="GPP")
        omp.Plus_model_var(QNC_Variable("gpp_avg", "ASSIMI"))
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
        omp.Plus_model_var(QNC_Variable("gpp_avg", "ASSIMI"))
        omp.Substract_model_var(QNC_Variable("npp_avg", "VEG"))

        omp = QNC_Obs_Model_Variable_Pair(name="PPFD")
        omp.Plus_model_var(QNC_Variable("appfd_avg", "RAD"))
        omp.Plus_obs_var(QNC_Variable("PPFD"))
        target_variable_list.Add(omp)

        fluxnet_diagnostics = QNC_Fluxnet_Diagnostics(rt_path=self.root_path, target_variable_list=target_variable_list)

        # Only perform analysis when we have data
        if fluxnet_diagnostics.Have_fluxet_data:
            fluxnet_diagnostics.parse_env_variables()
            fluxnet_diagnostics.Check_output_variables()
            fluxnet_diagnostics.Analyse_and_plot()
