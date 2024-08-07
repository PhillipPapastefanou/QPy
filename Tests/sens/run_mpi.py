import sys
rt_lib_path = "/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy"
setup_path = "oaat_psi50_test"
quincy_path = "/Net/Groups/BSI/work_scratch/ppapastefanou/src/quincy/x86_64-gfortran/bin/land.x"

sys.path.append(rt_lib_path)

from mpi4py import MPI
from src.sens.run_mpi_cluster import ParallelSetup

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

setup = ParallelSetup(comm=comm, rank=rank, size=size)

setup.init(setup_path= setup_path, quincy_path=quincy_path)
setup.send_parameter_indexes()
setup.start_simulations()

print("All simulations finished")
