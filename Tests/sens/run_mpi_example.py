import sys
rtpath ="/Users/pp/Documents/Repos/QPy"
sys.path.append(rtpath)

from mpi4py import MPI
from src.sens.run_mpi_cluster import ParallelSetup

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

setup = ParallelSetup(comm=comm, rank=rank, size=size)

setup_path = "oaat_psi50_test"
quincy_path = "/Users/pp/Documents/Repos/quincy/build_cmake/quincy_run"

setup.init(setup_path= setup_path, quincy_path=quincy_path)
setup.send_parameter_indexes()
setup.start_simulations()

print("All simulations finished")