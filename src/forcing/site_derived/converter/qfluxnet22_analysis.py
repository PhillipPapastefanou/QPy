
from lib.converter.Base_parsing import Base_Parsing
from lib.converter.Settings import Settings
from lib.base.Fluxnet22_Jake import Fluxnet2022_Jake

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

class Quincy_Fluxnet22_Analysis(Base_Parsing):
    def __init__(self, settings: Settings):
        Base_Parsing.__init__(self, settings = settings)
        self.analysis_folder = f"{self.settings.root_output_path}/{self.settings.analysis_folder_name}"

    def _clalculate_plots(self, fnet : Fluxnet2022_Jake):

        df = fnet.df.copy()
        df = df.set_index('date')


        for var_name in self.settings.fluxnet_forcing_columns:
            col = 'tab:red'

            fig = plt.figure(figsize=(12, 8), constrained_layout=True)
            gs = fig.add_gridspec(3, 3)

            ax = fig.add_subplot(gs[0, 0])
            dfs = self._avg_timerange(df, freq='1D')
            ax.plot(dfs['date'], dfs[var_name], c=col)
            ax.set_title("Daily average")

            ax = fig.add_subplot(gs[0, 1])
            dfs = self._avg_timerange(df, freq='1W')
            ax.plot(dfs['date'], dfs[var_name], c=col)
            ax.set_title("Weekly average")

            ax = fig.add_subplot(gs[0, 2])
            dfs = self._avg_timerange(df, freq='1M')
            ax.plot(dfs['date'], dfs[var_name], c=col)
            ax.set_title("Monthly average")

            ax = fig.add_subplot(gs[1, 2])
            dfs = self._avg_timerange(df, freq='1Y')
            ax.plot(dfs['date'], dfs[var_name], c=col)
            ax.set_title("Yearly average")

            ax = fig.add_subplot(gs[1:3, :-1])
            dfs = self._overall_avg_day(df)

            ax.plot(dfs[var_name].values, c=col)
            # ax.fill_between( dfs[name_o].values - dfs_std[name_o].values, dfs[name_o].values + dfs_std[name_o].values,
            #                facecolor = self.col_obs, alpha = 0.2)
            # ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))
            ax.set_title("Subdaily distribution")
            fig.suptitle(var_name, fontsize=16)


            plt.savefig(f"{self.analysis_folder}/{fnet.sitename}_{var_name}.png")
            plt.close(fig)



    def _avg_timerange(self, df, freq):
        dfs = df.groupby(pd.Grouper(freq=freq)).mean().reset_index()
        return dfs

    def _overall_avg_day(self, df):
        dfs = df.groupby([df.index.hour, df.index.minute]).mean()
        return dfs