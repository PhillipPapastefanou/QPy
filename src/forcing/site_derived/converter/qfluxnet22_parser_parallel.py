import pandas as pd
import numpy as np

from lib.converter.Quincy_fluxnet22_site_data_prev_factory import Quincy_Fluxnet22_Site_Data_Prev_Factory
from lib.converter.Quincy_fluxnet22_site_data_factory import Quincy_Fluxnet22_Site_Data_Factory
from lib.converter.Quincy_fluxnet22_forcing import Quincy_Fluxnet22_Forcing
from lib.converter.Quincy_fluxnet22_analysis import Quincy_Fluxnet22_Analysis

from lib.converter.Quincy_fluxnet22_site_data import Quincy_Fluxnet22_Site_Data
from lib.converter.Base_parsing import Base_Parsing
from lib.converter.Settings import Settings
from lib.base.Fluxnet22_Jake import Fluxnet2022_Jake

import os
import mpi4py.MPI as MPI

class Quincy_Fluxnet22_Parser_Parallel(Base_Parsing):

    def __init__(self, settings: Settings, root_fluxnet_path, sites,  comm, rank, size):

        self.comm = comm
        self.size = size
        self.rank = rank
        self.is_root = rank == 0


        Base_Parsing.__init__(self, settings = settings)
        self.root_fluxnet_path = root_fluxnet_path

        self.all_sites = sites
        # Convert list to np array to be able ot use indices
        self.all_sites = np.array(self.all_sites)


        rt_output_folder = self.settings.root_output_path
        static_folder = f"{rt_output_folder}/{self.settings.static_forcing_folder_name}"
        transient_folder = f"{rt_output_folder}/{self.settings.transient_forcing_folder_name}"
        analysis_folder = f"{rt_output_folder}/{self.settings.analysis_folder_name}"


        self.df_error = pd.DataFrame(columns=["site", "message"])

        if self.is_root:

            # Check if directory exists and create otherwise
            if not os.path.exists(rt_output_folder):
                os.mkdir(rt_output_folder)

            if not os.path.exists(analysis_folder):
                os.mkdir(analysis_folder)

            # Do the same for static and transient forcing
            if not os.path.exists(static_folder):
                os.mkdir(static_folder)
            if not os.path.exists(transient_folder):
                os.mkdir(transient_folder)

        if self.is_root:
            self._calculate_gridpoints()
        else:
            self._initialise_counts()

    def send_parameter_indexes(self):

        if self.is_root:
            print("Broadcasting location indices...", end = '')

        # broadcast The number of parameter files each process will get
        self.comm.Bcast(self.count, root=0)

        # Initialize the memory according to that file size
        self.recvbuf = np.zeros(self.count[self.rank], dtype='i')

        # Send the indexes ot each process
        self.comm.Scatterv([self.sendbuf, self.count, self.displ, MPI.INTEGER], self.recvbuf, root=0)
        # Print the chunk that was received by this process
        # print("Process {} received chunk {}".format(self.rank, recvbuf))

        self.comm.Barrier()

        if self.is_root:
            print(f"Done.")

        # Overwriting file list with indicies
        self.sites = self.all_sites[self.recvbuf]

    def parse(self):
        quincy_site_data_prev_factory = Quincy_Fluxnet22_Site_Data_Prev_Factory(settings=self.settings)
        quincy_site_data_factory = Quincy_Fluxnet22_Site_Data_Factory(settings=self.settings)

        quincy_site_data_prev_factory.rank  = self.rank
        quincy_site_data_factory.rank  = self.rank

        n = len(self.sites)
        print(f"Parsing {n} fluxnet sites.")


        current_site = 1
        for site in self.sites:

            try:
                print(f"Rank {self.rank} parsing site: {site} ({current_site} out of {n}).")
                print(f"Opening fluxnet site")
                fnet = Fluxnet2022_Jake(rtpath=self.root_fluxnet_path, sitename=site)
                self.dprint("Parsing fluxnet time variable.. ", lambda: fnet.Read_And_Parse_Time())

                # Reading variables from fluxnet site
                self.dprint("Reading fluxnet forcing..",
                            lambda: fnet.Read_forcing_variables(self.settings.fluxnet_forcing_columns))


                analysis_fnet = Quincy_Fluxnet22_Analysis(settings=self.settings)
                self.dprint("Analysing fluxnet output..", lambda: analysis_fnet._clalculate_plots(fnet))


                print("Creating Quincy fluxnet22 file:")
                qf = Quincy_Fluxnet22_Forcing(settings=self.settings)
                qf.Connect_to_fluxnet(fnet=fnet)
                qf.Parse_forcing()

                # Generate transient forcing based on the input data
                qf.Export_transient_forcing()
                # Generate static forcing based on the input data
                qf.Export_static_forcing()

                print("Reading Quincy site data information")
                qsd = Quincy_Fluxnet22_Site_Data(fluxnet_file=fnet, settings=self.settings)
                qsd.Parse_Environmental_Data()
                qsd.Parse_PFT(qf=qf)
                qsd.Perform_sanity_checks()

                quincy_site_data_prev_factory.Add_site(qsd=qsd)
                quincy_site_data_factory.Add_site(qsd=qsd)
                print(f"Site {site} sucessfully parsed!")


            except Exception as e:
                print(f"ERROR parsing site {site}.")
                print(e)
                self.df_error.loc[-1] = pd.Series({"site": site,  "message": e})
                self.df_error.index = self.df_error.index + 1
                self.df_error = self.df_error.sort_index()

            print("----------------------------------")
            print("")
            print("")
            current_site += 1

        if n > 0:
            print("Exporting site information")
            quincy_site_data_prev_factory.size = self.size
            quincy_site_data_prev_factory.Export()
            quincy_site_data_factory.size = self.size
            quincy_site_data_factory.Export(fnet = fnet)

        if self.size == 1:
            self.df_error.to_csv(f"{self.settings.root_output_path}/Errors.csv", index=False)
        else:
            self.df_error.to_csv(f"{self.settings.root_output_path}/Errors.csv{self.rank}", index=False)

        # Wait until all processes are finished
        self.comm.Barrier()
        if self.is_root & (not self.size == 1):
            self._aggregate_files(f"{self.settings.root_output_path}/Errors.csv")
            self._aggregate_files(quincy_site_data_factory.Export_filename_static)
            self._aggregate_files(quincy_site_data_factory.Export_filename_transient)
            self._aggregate_files(quincy_site_data_prev_factory.Export_filename)

        print("Parsing complete")


    def _calculate_gridpoints(self):

        n = self.all_sites.shape[0]
        self.sendbuf = np.linspace(0, n - 1, num=n).astype('i')

        ave, res = divmod(self.sendbuf.size, self.size)
        self.count = [ave + 1 if p < res else ave for p in range(self.size)]
        self.count = np.array(self.count)

        # displacement: the starting index of each sub-task
        self.displ = [sum(self.count[:p]) for p in range(self.size)]
        self.displ = np.array(self.displ)

    def _initialise_counts(self):
        self.sendbuf = None
        # initialize count on worker processes
        self.count = np.zeros(self.size, dtype=int)
        self.displ = None


    def _aggregate_files(self, fpath):
        bpath = fpath
        # Todo make sure root is always getting something!
        df = pd.read_csv(f"{bpath}{0}")
        for i in range(1, self.size):
            if os.path.exists(f"{bpath}{i}"):
                df_r = pd.read_csv(f"{bpath}{i}")
                df = pd.concat([df, df_r])
        df.to_csv(f"{bpath}", index=None)
        #Remove old files
        for i in range(0, self.size):
            if os.path.exists(f"{bpath}{i}"):
               os.remove(f"{bpath}{i}")



