

#print(colored('hello', 'red'), colored('world', 'green'))
#from src.lib.QNC_std_output_factory import QNC_std_output_factory

import sys
import glob
import subprocess

sys.path.append("/Users/pp/Documents/Repos/qn-lib")
# sys.path.append("/Users/pp/Documents/Repos/qn-lib/src/cal_parsing/build")
# so_paths = glob.glob('/Users/pp/Documents/Repos/qn-lib/src/cal_parsing/build/*.so')
# if len(so_paths) > 0:
#     print("yes")
# else:
#     command = "cmake ~/Documents/Repos/qn-lib/src/cal_parsing/CMakeLists.txt -B~/Documents/Repos/qn-lib/src/cal_parsing/build"
#     process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
#     output, error = process.communicate()
#
#     command = "make -C ~/Documents/Repos/qn-lib/src/cal_parsing/build"
#     process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
#     output, error = process.communicate()


from src.postprocessing.qnc_std_output_factory import Output_format
from src.postprocessing.qnc_std_output_factory import QNC_std_output_factory

exp_path = '/Users/pp/data/Simulations/QUINCY_local_global/testbed'
# exp_path = '/Users/pp/data/Simulations/QUINCY_local_global/usecase82/AT-Neu'
# exp_path = '/Users/pp/data/Simulations/QUINCY_local_global/usecase82/BR-Ma2'
#exp_path = '/Users/pp/data/Simulations/QUINCY_local_global/usecase82/FR-Pue'

target_categories = []

format = Output_format.Single
output_factory = QNC_std_output_factory(exp_path, output_format=format, target_categories=target_categories)
output_factory.Calculate_std_output()
output_factory.Calculate_fluxnet_stat()

print("Finished!")