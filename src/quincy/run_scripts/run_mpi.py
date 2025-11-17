import sys
import os

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir, os.pardir))
sys.path.append("/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy")

if 'QUINCY' in os.environ:        
    QUINCY_ROOT_PATH = os.environ.get("QUINCY")
else:
    print("Environmental variable QUINCY is not defined")
    print("It is not enough to export it in the shell...")
    print("Please add it to the ~/.bash_profile")
    print("Please set QUINCY to the directory of your quincy root path")
    exit(99)

QUINCY_BIN = os.path.join(QUINCY_ROOT_PATH, "x86_64-gfortran", "bin", "land.x")   

setup_path = os.getcwd()

from mpi4py import MPI
from src.sens.run_mpi_cluster import ParallelSetup

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

setup = ParallelSetup(comm=comm, rank=rank, size=size)

setup.init(setup_path= setup_path, quincy_path=QUINCY_BIN)
setup.send_parameter_indexes()
setup.start_simulations()

print("All simulations finished")
