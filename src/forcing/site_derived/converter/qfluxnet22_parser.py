import pandas as pd

from lib.converter.Quincy_fluxnet22_site_data_prev_factory import Quincy_Fluxnet22_Site_Data_Prev_Factory
from lib.converter.Quincy_fluxnet22_site_data_factory import Quincy_Fluxnet22_Site_Data_Factory
from lib.converter.Quincy_fluxnet22_forcing import Quincy_Fluxnet22_Forcing
from lib.converter.Quincy_fluxnet22_analysis import Quincy_Fluxnet22_Analysis

from lib.converter.Quincy_fluxnet22_site_data import Quincy_Fluxnet22_Site_Data
from lib.converter.Base_parsing import Base_Parsing
from lib.converter.Settings import Settings
from lib.base.Fluxnet22_Jake import Fluxnet2022_Jake

import os


class Quincy_Fluxnet22_Parser(Base_Parsing):

    def __init__(self, settings: Settings, root_fluxnet_path, sites):

        Base_Parsing.__init__(self, settings = settings)
        self.root_fluxnet_path = root_fluxnet_path
        self.sites = sites
        self.df_error = pd.DataFrame(columns=["site", "message"])

        rt_output_folder = self.settings.root_output_path
        static_folder = f"{rt_output_folder}/{self.settings.static_forcing_folder_name}"
        transient_folder = f"{rt_output_folder}/{self.settings.transient_forcing_folder_name}"
        analysis_folder = f"{rt_output_folder}/{self.settings.analysis_folder_name}"

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

    def parse(self):
        quincy_site_data_factory = Quincy_Fluxnet22_Site_Data_Prev_Factory(settings=self.settings)
        quincy_site_setup_factory = Quincy_Fluxnet22_Site_Data_Factory(settings=self.settings)

        n = len(self.sites)
        print(f"Parsing {n} fluxnet sites.")


        current_site = 1
        for site in self.sites:

            try:
                print(f"Parsing site: {site} ({current_site} out of {n}).")
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


                print("Reading Quincy site data")
                qsd = Quincy_Fluxnet22_Site_Data(fluxnet_file=fnet, settings=self.settings)
                qsd.Parse_Environmental_Data()
                qsd.Parse_PFT(qf=qf)
                qsd.Perform_sanity_checks()

                quincy_site_data_factory.Add_site(qsd=qsd)
                quincy_site_setup_factory.Add_site(qsd=qsd)
                print(f"Site {site} sucessfully parsed! ")


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

        print("Exporting site information")
        quincy_site_data_factory.Export()
        quincy_site_setup_factory.Export(fnet = fnet)
        self.df_error.to_csv(f"{self.settings.root_output_path}/Errors.csv", index=False)
        print("Parsing complete")








