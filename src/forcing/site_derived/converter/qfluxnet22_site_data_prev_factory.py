import pandas as pd
import numpy  as np

from lib.converter.Settings import Settings
from lib.converter.Base_parsing import Base_Parsing
from lib.converter.Quincy_fluxnet22_site_data import Quincy_Fluxnet22_Site_Data
from lib.base.PFT import Quincy_Orchidee_PFT



class Quincy_Fluxnet22_Site_Data_Prev_Factory(Base_Parsing):

    def __init__(self, settings : Settings):

        Base_Parsing.__init__(self, settings)

        self.columns = ["site_id", "start", "end", "gmtref", "clay", "silt", "sand", "awc", "pH", "LAI", "Nleaf", "SLA", "Height", "Age", "BG"]

        for pft in Quincy_Orchidee_PFT:
            self.columns.append(pft.name)

        self.columns.append("origin")

        self.columns.append("temp_coldest_month")
        self.columns.append("temp_avg_yearly")
        self.columns.append("rain_sum_yearly")

        self.df = pd.DataFrame(columns = self.columns)

        self.size = 1


    def Add_site(self, qsd : Quincy_Fluxnet22_Site_Data):

        new_row = {'site_id': qsd.fnet.sitename,
                   'start': qsd.fnet.Year_min,
                   'end': qsd.fnet.Year_max,
                   'gmtref': qsd.Gmt_ref,
                   'clay': qsd.Clay_fraction,
                   'silt': qsd.Silt_fraction,
                   'sand': qsd.Sand_fraction,
                   'awc' : qsd.AWC,
                   'pH': qsd.PH,
                   'LAI': qsd.LAI,
                   'Nleaf': qsd.Nleaf,
                   'SLA': qsd.SLA,
                   'Height': qsd.Height,
                   'Age': qsd.Age,
                   'BG': qsd.BG,
                   'origin': 'fluxnet_2022'
                   }

        for pft in Quincy_Orchidee_PFT:
            new_row[pft.name] = qsd.PFT_list.Fractions[pft]

        new_row['temp_coldest_month'] = qsd.Temp_monthly_avg_min
        new_row['temp_avg_yearly'] = qsd.Temp_yearly_avg
        new_row['rain_sum_yearly'] = qsd.Rain_yearly_sum_avg


        self.df.loc[len(self.df)] = new_row


    def Export(self):

        # Pass reference
        df_export = self.df

        # Round values according to 4 significant figures
        for var in ["gmtref", "clay", "silt", "sand", "awc", "pH", "LAI"]:
            df_export[var] = df_export[var].astype(np.float64)
            df_export[var] = self.round(df_export[var], 4)
            df_export[var] = df_export[var].apply(pd.to_numeric, downcast='float').fillna(0)

        self.Export_filename = f"{self.settings.root_output_path}/generate_flxunet_2022_site_list.dat"

        # Export file acccording to QUINCY standards
        if self.size == 1:
            df_export.to_csv(self.Export_filename, header=True, sep=" ", index=None)
        else:
            df_export.to_csv(f"{self.Export_filename}{self.rank}", header=True, sep=" ", index=None)



