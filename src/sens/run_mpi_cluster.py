import numpy as np
import pandas as pd
import mpi4py.MPI as MPI
import os
from time import perf_counter
import subprocess
import time
class ParallelSetup:
    def __init__(self, comm, rank, size):
        self.comm = comm
        self.size = size
        self.rank = rank
        self.is_root = rank == 0

    def init(self,
             setup_path,
             quincy_path):
        self.setup_path = setup_path
        
        self.quincy_path = quincy_path

        if self.is_root:
            self._calculate_gridpoints()
        else:
            self._initialise_counts()

    def _calculate_gridpoints(self):

        # Get the length of the paramter input files
        df = pd.read_csv(os.path.join(self.setup_path,"parameters.csv"))

        if df.empty:
            print("Found empty dataset! Exiting...")
            exit(99)

        n = df.shape[0]
        self.sendbuf = np.linspace(0, n - 1, num=n).astype('i')

        print(f"found {n} combinations that will be distributed across {self.size} processes...")

        min_np = int(n / self.size)
        remaining = n - min_np * self.size
        n_per_process = np.zeros(self.size) + min_np

        offsets = np.zeros(self.size)
        for i in range(0, remaining):
            offsets[i] = 1
        n_per_process  += offsets

        # Initialise inter with array as send an int is not possible atm
        self.n_sims_total = np.arange(1).astype(int)
        self.n_sims_total[0] = n

        self.n_array_per_process = n_per_process.astype(int)

        ri = 0
        self.displ = np.zeros(self.size)
        
        # Create output directories
        os.makedirs(os.path.join(self.setup_path, "output"), exist_ok=True)

        for i in range(0, self.size):
            df_i = df.iloc[ri: ri + self.n_array_per_process[i]]
            df_i.to_csv(os.path.join(self.setup_path, "output",f"parameters.csv.{i}"), index = False)
            self.displ[i] = ri
            ri += self.n_array_per_process[i]

    def _initialise_counts(self):
        self.sendbuf = None
        # initialize count on worker processes
        self.n_array_per_process = np.zeros(self.size, dtype=int)
        self.n_sims_total =  np.zeros(1, dtype=int)
        self.displ = None

    def send_parameter_indexes(self):
        if self.is_root:
            print("Broadcasting parameter indices...", end = '')

        # broadcast The number of parameter files each process will get
        self.comm.Bcast(self.n_sims_total, root=0)
        self.comm.Bcast(self.n_array_per_process, root=0)
        self.n_sims_per_process = self.n_array_per_process[self.rank]

        # Initialize the memory according to that file size
        self.recvbuf = np.zeros(self.n_array_per_process[self.rank], dtype='i')
        
        # print('----')
        # print(f"recvbuf {type(self.recvbuf)}")
        # print(f"sendbuf {type(self.sendbuf)}")
        # print(f"narray {type(self.n_array_per_process)}")
        # print(f"displ {type(self.displ)}")
        # print('+++')
        # Send the indexes ot each process
        #self.comm.Scatterv([self.sendbuf, self.n_array_per_process, self.displ, MPI.INTEGER], self.recvbuf, root=0)

        # Print the chunk that was received by this process
        #print("Process {} received chunk with size ".format(self.rank, self.n_sims_per_process))
                
        time.sleep(10)
        
        self.comm.Barrier()

        
        # Read the filename containing the folder ids
        self.df_sel = pd.read_csv(os.path.join(self.setup_path, "output",f"parameters.csv.{self.rank}"))
        
        print(f"Chunk: {self.df_sel['fid']}")

        self.comm.Barrier()

    def start_simulations(self):
        if self.is_root:
            print("Starting simulations...")
            t1 = perf_counter()
            
        

        for fid in self.df_sel['fid']:
            p = subprocess.Popen(self.quincy_path,
                             cwd=os.path.join(self.setup_path,"output",
                                              str(fid)))
            p.communicate()

        self.comm.Barrier()
        if self.is_root:
            t2 = perf_counter()
            print(f"Simulation done ({np.round(t2 - t1, 1)}) sec.")