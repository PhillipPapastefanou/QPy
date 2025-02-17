

#print(colored('hello', 'red'), colored('world', 'green'))
#from src.lib.QNC_std_output_factory import QNC_std_output_factory

import sys
import glob
import subprocess

sys.path.append("/Users/pp/Documents/Repos/qn-lib")
sys.path.append("/Users/pp/Documents/Repos/qn-lib/src/cal_parsing/build")
print(sys.path)

so_paths = glob.glob('/Users/pp/Documents/Repos/qn-lib/src/cal_parsing/build/*.so')

if len(so_paths) > 0:
    print("yes")
else:
    command = "cmake ~/Documents/Repos/qn-lib/src/cal_parsing/CMakeLists.txt -B~/Documents/Repos/qn-lib/src/cal_parsing/build"
    process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    print(output)

    command = "make -C ~/Documents/Repos/qn-lib/src/cal_parsing/build"
    process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    print(output)


from src.lib.QNC_obs_model_comparer  import Obs_Model_Var_List
from src.lib.QNC_obs_model_comparer  import QNC_Obs_Model_Variable_Pair
from src.lib.QNC_obs_model_comparer  import QNC_Variable
from src.lib.QNC_fluxnet_diagnostics import QNC_Fluxnet_Diagnostics



exp_path = '/Users/pp/data/Simulations/QUINCY/U80/DE-Hai/'

target_variable_list = Obs_Model_Var_List()

omp = QNC_Obs_Model_Variable_Pair(name="Gc")
omp.Plus_model_var(QNC_Variable("gc_avg", "ASSIMI"))
omp.Plus_obs_var(QNC_Variable("Gc"))
target_variable_list.Add(omp)

omp = QNC_Obs_Model_Variable_Pair(name= "GPP")
omp.Plus_model_var(QNC_Variable("gpp_avg", "ASSIMI"))
omp.Plus_obs_var(QNC_Variable("GPP"))
target_variable_list.Add(omp)


omp = QNC_Obs_Model_Variable_Pair(name= "NEE")
omp.Plus_model_var(QNC_Variable("het_respiration_avg", "SB"))
omp.Substract_model_var(QNC_Variable("npp_avg", "VEG"))
omp.Plus_obs_var(QNC_Variable("NEE"))
target_variable_list.Add(omp)


omp = QNC_Obs_Model_Variable_Pair(name= "Ga")
omp.Plus_model_var(QNC_Variable("ga_avg", "A2L"))
omp.Plus_obs_var(QNC_Variable("Ga"))
target_variable_list.Add(omp)

omp = QNC_Obs_Model_Variable_Pair(name= "LE")
omp.Substract_model_var(QNC_Variable("qle_avg", "SPQ"))
omp.Plus_obs_var(QNC_Variable("LE"))
target_variable_list.Add(omp)


omp = QNC_Obs_Model_Variable_Pair(name= "H")
omp.Substract_model_var(QNC_Variable("qh_avg", "SPQ"))
omp.Plus_obs_var(QNC_Variable("H"))
target_variable_list.Add(omp)

omp = QNC_Obs_Model_Variable_Pair(name= "Reco")
omp.Plus_model_var(QNC_Variable("het_respiration_avg", "SB"))
omp.Plus_model_var(QNC_Variable("gpp_avg", "ASSIMI"))
omp.Substract_model_var(QNC_Variable("npp_avg", "VEG"))


omp = QNC_Obs_Model_Variable_Pair(name= "PPFD")
omp.Plus_model_var(QNC_Variable("appfd_avg", "RAD"))
omp.Plus_obs_var(QNC_Variable("PPFD"))
target_variable_list.Add(omp)



fluxnet_diagnostics = QNC_Fluxnet_Diagnostics(rt_path= exp_path, target_variable_list = target_variable_list)
fluxnet_diagnostics.parse_env_variables()
fluxnet_diagnostics.Check_output_variables()
fluxnet_diagnostics.Analyse_and_plot()

