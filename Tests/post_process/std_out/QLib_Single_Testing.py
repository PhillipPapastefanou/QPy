

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


from src.postprocessing.QNC_std_output_factory import OutputFormat
from src.postprocessing.QNC_std_output_factory import QNC_std_output_factory

#exp_path = '/Users/pp/data/Simulations/QUINCY/exp_t_spinup/DE-Hai/'
#exp_path = '/Users/pp/data/Simulations/QUINCY/land_std_nc_ts/'
exp_path = '/Users/pp/data/Simulations/QUINCY/test_bed_static/'
exp_path = '/Users/pp/data/Simulations/A09_QUINCY_Hydraulics/tests/online/'
exp_path = '/Users/pp/data/Simulations/A09_QUINCY_Hydraulics/tests/online_low_huber/'
exp_path = '/Users/pp/data/Simulations/A09_QUINCY_Hydraulics/tests/online_low_kappac/'
exp_path = '/Users/pp/data/Simulations/A09_QUINCY_Hydraulics/tests/online_early_closure/'
#exp_path = '/Users/pp/data/Simulations/A09_QUINCY_Hydraulics/tests/diag/'
#exp_path = '/Users/pp/data/Simulations/QUINCY/site_level_static/DE-Hai/'
#exp_path = '/Users/pp/data/Simulations/QUINCY/U80/DE-Hai/'
#exp_path = '/Users/pp/data/Simulations/QUINCY/U81/DE-Hai/'


target_categories = []

target_categories = ['Q_ASSIMI', 'SPQ', 'PHYD']

format = OutputFormat.Single

output_factory = QNC_std_output_factory(exp_path, output_format=format, target_categories=target_categories)

output_factory.calculate_std_output()

output_factory.calculate_fluxnet_stat()

print("Finished!")