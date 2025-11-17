import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from src.postprocessing.py.qnc_obs_reader import QNC_obs_reader
from src.postprocessing.py.qnc_obs_model_comparer import Obs_Model_Var_List
from src.postprocessing.py.qnc_obs_model_comparer import QNC_Obs_Model_Variable_Pair
from src.postprocessing.py.qnc_output_parser import QNC_output_parser
from src.postprocessing.py.qnc_ncdf_reader import QNC_ncdf_reader


class QNC_Std_Fluxnet_Diagnostics:

    def __init__(self, rt_path, target_variable_list : Obs_Model_Var_List):
        # Fluxnet output should always have this folder structure as it is not static
        parser = QNC_output_parser(rt_path)

        parser.check_target_categories([])
        parser.Read()

        # We must have fluxnetdata otherwise it will not work
        self.identifier = 'fluxnetdata'

        if not self.identifier in parser.Available_outputs:
            self.Target_variable_list = []
            self.Have_fluxnet_variables = False
            print("No fluxnet type output found. Skipping fluxnet statistics")
            return


        print("Calculating fluxnet statistics...")
        self.Have_fluxnet_variables = True

        output_file = parser.Available_outputs[self.identifier]
        self.cats = output_file.Target_categories
        self.sim_type = output_file.Simulation_type
        self.time_res = output_file.Time_resolution

        self.output_path = os.path.join(rt_path, "output")
        self.post_processing_path = os.path.join(rt_path, "postprocessing")
        self.Target_variable_list = target_variable_list
        self.col_obs = 'tab:red'
        self.col_mod = 'tab:blue'


    def parse_env_variables(self):

        self.nc_obs = QNC_obs_reader(self.output_path)
        self.nc_obs.Parse_env_and_variables()


        self.nc_output = QNC_ncdf_reader(self.output_path,
                                    self.cats,
                                    self.identifier,
                                    self.time_res
                                    )
        self.nc_output.Parse_env_and_variables()

    def Check_output_variables(self):

        obs_variables_found = self.nc_obs.Check_variables(self.Target_variable_list.Get_obs_var_list())
        mods_variables_found = self.nc_output.check_1D_variables(self.Target_variable_list.Get_model_var_list())

        # Reducing all checked variables for the once that are available in both obs and model
        self.Target_variable_list.Reduce_available_variables(found_obs_list=obs_variables_found,
                                                             founds_model_list=mods_variables_found)

    def Read_data(self, pair: QNC_Obs_Model_Variable_Pair):

        model_plus = []
        for var in pair.model_vars_plus:
            df = self.nc_output.Read_1D_flat(var.cat, var.name)
            df.set_index('date', inplace=True)
            model_plus.append(df)

        model_minus = []
        for var in pair.model_vars_minus:
            df = self.nc_output.Read_1D_flat(var.cat, var.name)
            df.set_index('date', inplace=True)
            model_minus.append(df)

        i = 0
        for var in pair.model_vars_plus:
            if i == 0:
                dfs_model = model_plus[0]
                dfs_model[pair.name] = dfs_model[var.name]
            else:
                dfs_model[pair.name] += model_plus[i][var.name]
            i += 1

        i = 0

        for var in pair.model_vars_minus:
            if (i == 0) & (len(pair.model_vars_plus) == 0):
                dfs_model = model_minus[0]
                dfs_model[pair.name] = -dfs_model[var.name]
            else:
                dfs_model[pair.name] -= model_minus[i][var.name]
            i += 1

        obs_plus = []
        for var in pair.obs_vars_plus:
            df = self.nc_obs.Read_data(var.name)
            obs_plus.append(df)

        obs_minus = []
        for var in pair.obs_vars_minus:
            df = self.nc_obs.Read_data(var.name)
            obs_minus.append(df)

        i = 0
        for var in pair.obs_vars_plus:
            if i == 0:
                dfs_obs = obs_plus[0]
                dfs_obs[pair.name] = dfs_obs[var.name]
            else:
                dfs_obs[pair.name] += obs_plus[i][var.name]
            i += 1

        i = 0
        for var in pair.obs_vars_minus:
            dfs_obs[pair.name] -= obs_minus[i][var.name]
            i += 1

        dfs_model[f"{pair.name}_obs"] = dfs_obs[pair.name]
        dfs_model.rename(columns={f"{pair.name}": f"{pair.name}_mod"},inplace=True)

        dfs_model.dropna(inplace=True)

        return dfs_model


    def Analyse_and_plot(self):

        for pair in self.Target_variable_list.Available_variables:

            df = self.Read_data(pair)
            name_m = pair.name +"_mod"
            name_o = pair.name +"_obs"

            fig = plt.figure(figsize = (12,8), constrained_layout = True)
            gs = fig.add_gridspec(3, 3)

            ax = fig.add_subplot(gs[0,0])
            dfs= self.avg_timerange(df, freq='1D')
            ax.plot(dfs['date'], dfs[name_m], c = self.col_mod, alpha = 0.8)
            ax.plot(dfs['date'], dfs[name_o], c = self.col_obs, alpha = 0.8)
            ax.tick_params(labelrotation=45)
            ax.set_title("Daily average")

            ax = fig.add_subplot(gs[0, 1])
            dfs= self.avg_timerange(df, freq='1W')
            ax.plot(dfs['date'], dfs[name_m], c = self.col_mod, alpha = 0.8)
            ax.plot(dfs['date'], dfs[name_o], c = self.col_obs, alpha = 0.8)
            ax.tick_params(labelrotation=45)
            ax.set_title("Weekly average")

            ax = fig.add_subplot(gs[0, 2])
            dfs= self.avg_timerange(df, freq='1ME')
            ax.plot(dfs['date'], dfs[name_m], c = self.col_mod, alpha = 0.8)
            ax.plot(dfs['date'], dfs[name_o], c = self.col_obs, alpha = 0.8)
            ax.tick_params(labelrotation=45)
            ax.set_title("Monthly average")

            ax = fig.add_subplot(gs[1:3, :-1])
            dfs, dt = self.overall_avg_day(df)
            dfs_02 = self.overall_q_day(df, 0.2)
            dfs_08 = self.overall_q_day(df, 0.8)

            x_multi = dfs.index
            float_times = []
            for hour, minute in x_multi:
                float_time = hour + minute / 60
                float_times.append(float_time)

            ax.plot(float_times, dfs[name_m].values, c = self.col_mod, label = 'model mean')

            ax.plot( float_times, dfs_02[name_m].values,
                     c = self.col_mod, alpha = 0.5, label = 'model q02')
            ax.plot( float_times, dfs_08[name_m].values,
                     c = self.col_mod, alpha = 0.5, label = 'model q08')

            ax.plot(float_times, dfs[name_o].values, c = self.col_obs, label = 'obs mean')
            ax.plot(float_times, dfs_02[name_o].values,
                     c = self.col_obs, alpha = 0.5, label = 'obs q02')
            ax.plot(float_times, dfs_08[name_o].values,
                     c = self.col_obs, alpha = 0.5, label = 'obs q08')

            ax.set_title("Subdaily distribution")
            ax.legend()
            ax.set_xlabel("Hour")
            fig.suptitle(pair.name, fontsize=16)

            dfd = pd.DataFrame()
            dfd['RMSE'] = [np.round(self.rmse(df[name_m], df[name_o]), 3)]
            dfd['R'] = [np.round(self.corrcoef(df[name_m], df[name_o])[0,1],3)]
            dfd['R2'] = [np.round(self.rsquared(df[name_m], df[name_o])[0,1],3)]
            dfd['NSE'] = [np.round(self.nse(df[name_m], df[name_o]),3)]
            dfd['RSR'] = [np.round(self.rsr(df[name_m], df[name_o]),3)]
            dfd['pbias'] = [np.round(self.pbias(df[name_m], df[name_o]), 3)]

            ax = fig.add_subplot(gs[1:3, 2])
            table = ax.table(cellText=dfd.values.T, rowLabels=dfd.columns, loc='center left', cellLoc ='center',
                             colWidths=[0.4], bbox=[0.25,0.25,0.4,0.4])
            ax.set_axis_off()

            table.auto_set_font_size(False)
            table.set_fontsize(14)

            plt.savefig(os.path.join(self.post_processing_path, f"{pair.name}.png"),
                        bbox_inches='tight', pad_inches=0)




    def avg_timerange(self, df, freq):

        dfs= df.groupby(pd.Grouper(freq=freq)).mean().reset_index()
        return dfs


    def overall_avg_day(self, df):
        dfs = df.groupby([df.index.hour, df.index.minute]).mean()
        tx = pd.date_range('2000-01-01', periods=48, freq='30min')
        return dfs, tx
    def overall_q_day(self, df, q):
        dfs = df.groupby([df.index.hour, df.index.minute]).quantile(q = q)
        return dfs

    def rmse(self, predictions, targets):
        return np.sqrt(((predictions - targets) ** 2).mean())
    def corrcoef(self, predictions, targets):
        return np.corrcoef(predictions, targets)
    def rsquared(self, predictions, targets):
        return self.corrcoef(predictions, targets)**2
    def nse(self, predictions, targets):
        return 1.0 - np.sum((targets-predictions)**2) / np.sum((targets- np.mean(predictions)) **2)
    def rsr(self, predictions, targets):
        return np.sqrt(np.sum((targets - predictions)**2))/np.sqrt(np.sum((targets- np.mean(predictions)) **2))
    def pbias(self, predictions, targets):
        return np.sum(predictions-targets)*100.0 /np.sum(targets)