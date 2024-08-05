import pandas as pd
import numpy as np
from datetime import datetime
from src.mui.ui_settings import ModelOutputPlottingType
from src.mui.ui_settings import Ui_Settings

from src.mui.var_types import Scenario
class OutputPlotInterface:
    def __init__(self,
                 ui_settings: Ui_Settings,
                 scenario:Scenario,
                 output_txt_cat,
                 output_time_res,
                 is_spinup):
        self.ui_settings = ui_settings
        self.scenario = scenario
        self.cat = output_txt_cat
        self.res = output_time_res
        self.is_spinup = is_spinup


    def load_data(self):
        if self.is_spinup:
            spinup_suffix = "_spinup_"
        else:
            spinup_suffix = "_"

        filename = f"{self.ui_settings.root_ui_directory}/{self.ui_settings.scenario_output_path}/{self.cat}{spinup_suffix}{self.res}.txt"

        self.df = pd.read_csv(
            filename,
            sep='\s+')
        self.n_ts = self.df.shape[0]

        if self.is_spinup:
            first_year = self.scenario.first_year_spinup
        else:
            first_year = self.scenario.first_year_transient

        dates = np.array(f"{first_year}-01-01", 'datetime64[D]') + np.linspace(0,
                                                                                                    7 * self.n_ts,
                                                                                                    self.n_ts,
                                                                                                    dtype='timedelta64[D]')
        self.df["datetime"] = dates
        self.df["year"] = dates.astype('datetime64[Y]').astype(int) + 1970
        self.df["month"] = dates.astype('datetime64[M]').astype(int) % 12 + 1
        self.df["week"] = dates.astype('datetime64[W]').astype(int) % 53 + 1

    def update_plot(self, model_output_plotting_type: ModelOutputPlottingType,
                    var_str,
                    line_spinup):
        output_type = model_output_plotting_type

        # We only allow for weekly output at the moment. No need of average for the weekly output
        if output_type == ModelOutputPlottingType.Weekly:
            self.dfs = self.df

        elif output_type == ModelOutputPlottingType.Monthly:
            grouper = ['year', 'month']
            self.dfs = self.df.drop(['datetime'], axis=1).groupby(
                by= grouper).mean().reset_index()
            self.dfs['datetime'] = [
                np.datetime64(datetime(self.dfs['year'][i], self.dfs['month'][i], 1)) for i in
                range(self.dfs.shape[0])]

        elif output_type == ModelOutputPlottingType.Yearly:
            grouper = ['year']
            self.dfs = self.df.drop(['datetime'], axis=1).groupby(
                by= grouper).mean().reset_index()
            self.dfs['datetime'] = [
                np.datetime64(datetime(self.dfs['year'][i], 1, 1)) for i in
                range(self.dfs.shape[0])]

        elif output_type == ModelOutputPlottingType.Weekly_avg:
            grouper = ['week']
            self.dfs = self.df.drop(['datetime'], axis=1).groupby(
                by= grouper).mean().reset_index()
            self.dfs['datetime'] = [
                np.datetime64(datetime(self.dfs['week'][i], 1, 1)) for i in
                range(self.dfs.shape[0])]

        elif output_type == ModelOutputPlottingType.Weekly_avg:
            grouper = ['month']
            self.dfs = self.df.drop(['datetime'], axis=1).groupby(
                by= grouper).mean().reset_index()
            self.dfs['datetime'] = [
                np.datetime64(datetime(self.dfs['month'][i], 1, 1)) for i in
                range(self.dfs.shape[0])]

        line_spinup.set_xdata(self.dfs["datetime"])
        line_spinup.set_ydata(self.dfs[var_str])



    def update_plot_scenario(self, model_output_plotting_type: ModelOutputPlottingType,
                    var_str, last_year_scenario,
                    line_scenario_before, line_scenario_after):

        output_type = model_output_plotting_type



        # We only allow for weekly output at the moment. No need of average for the weekly output
        if output_type == ModelOutputPlottingType.Weekly:
            self.dfs = self.df

            self.dfb = self.dfs.loc[self.dfs['year'] <= last_year_scenario]
            self.dfa = self.dfs.loc[self.dfs['year'] > last_year_scenario]

            self.max_year = np.max(self.dfs['datetime'])

        elif output_type == ModelOutputPlottingType.Monthly:
            grouper = ['year', 'month']
            self.dfs = self.df.drop(['datetime'], axis=1).groupby(
                by= grouper).mean().reset_index()


            self.dfs['datetime'] = [
                np.datetime64(datetime(self.dfs['year'][i], self.dfs['month'][i], 1)) for i in
                range(self.dfs.shape[0])]

            self.max_year = np.max(self.dfs['datetime'])

            self.dfb = self.dfs.loc[self.dfs['year'] <= last_year_scenario]
            self.dfa = self.dfs.loc[self.dfs['year'] > last_year_scenario]


        elif output_type == ModelOutputPlottingType.Yearly:
            grouper = ['year']
            self.dfs = self.df.drop(['datetime'], axis=1).groupby(
                by= grouper).mean().reset_index()


            self.dfs['datetime'] = [
                np.datetime64(datetime(self.dfs['year'][i],1, 1)) for i in
                range(self.dfs.shape[0])]

            self.max_year = np.max(self.dfs['datetime'])
            self.dfb = self.dfs.loc[self.dfs['year'] <= last_year_scenario]
            self.dfa = self.dfs.loc[self.dfs['year'] > last_year_scenario]

        elif output_type == ModelOutputPlottingType.Weekly_avg:
            grouper = ['week']

            self.dfs = self.df.drop(['datetime'], axis=1)
            self.dfb = self.dfs.loc[self.dfs['year'] <= last_year_scenario]
            self.dfa = self.dfs.loc[self.dfs['year'] > last_year_scenario]

            self.dfb = self.dfb.groupby(
                by= grouper).mean().reset_index()
            self.dfa = self.dfa.groupby(
                by= grouper).mean().reset_index()

            self.dfb['datetime'] = [
                np.datetime64(datetime(self.dfb['week'][i], 1, 1)) for i in
                range(self.dfb.shape[0])]

            self.dfa['datetime'] = [
                np.datetime64(datetime(self.dfa['week'][i], 1, 1)) for i in
                range(self.dfa.shape[0])]
            # As this is per year it should be the same for scenario, spinup and change
            self.max_year = np.max(self.dfb['datetime'])

        elif output_type == ModelOutputPlottingType.Monthly_avg:
            grouper = ['month']
            self.dfs = self.df.drop(['datetime'], axis=1).groupby(
                by= grouper).mean().reset_index()
            self.dfs['datetime'] = [
                np.datetime64(datetime(self.dfs['month'][i], 1, 1)) for i in
                range(self.dfs.shape[0])]



        line_scenario_before.set_xdata(self.dfb["datetime"])
        line_scenario_before.set_ydata(self.dfb[var_str])

        line_scenario_after.set_xdata(self.dfa["datetime"])
        line_scenario_after.set_ydata(self.dfa[var_str])
