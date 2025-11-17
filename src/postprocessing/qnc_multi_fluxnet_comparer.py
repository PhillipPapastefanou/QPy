import os
import pandas as pd
import numpy as np

from src.postprocessing.qnc_obs_reader import QNC_obs_reader
from src.postprocessing.qnc_obs_model_comparer import Obs_Model_Var_List
from src.postprocessing.qnc_obs_model_comparer import QNC_Obs_Model_Variable_Pair
from src.postprocessing.qnc_obs_model_comparer import QNC_Variable 
from src.postprocessing.qnc_ncdf_reader import QNC_ncdf_reader


class QNC_Multi_Fluxnet_Comparer:
    
    def __init__(self, site): 
        self.list_rmse = []
        self.site = site
        
    def Set_target_list(self, target_variable_list : Obs_Model_Var_List ):
        self.target_variable_list = target_variable_list
        
    def Generate_Default_Fluxnet_Var_List(self):
        #Defining standard fluxnet output
        obs_var_collection = Obs_Model_Var_List()

        omp = QNC_Obs_Model_Variable_Pair(name="Gc")
        omp.Plus_model_var(QNC_Variable("gc_avg", "Q_ASSIMI"))
        omp.Plus_obs_var(QNC_Variable("Gc"))
        obs_var_collection.Add(omp)

        omp = QNC_Obs_Model_Variable_Pair(name="GPP")
        omp.Plus_model_var(QNC_Variable("gpp_avg", "Q_ASSIMI"))
        omp.Plus_obs_var(QNC_Variable("GPP"))
        obs_var_collection.Add(omp)

        omp = QNC_Obs_Model_Variable_Pair(name="NEE")
        omp.Plus_model_var(QNC_Variable("het_respiration_avg", "SB"))
        omp.Substract_model_var(QNC_Variable("npp_avg", "VEG"))
        omp.Plus_obs_var(QNC_Variable("NEE"))
        obs_var_collection.Add(omp)

        # omp = QNC_Obs_Model_Variable_Pair(name="Ga")
        # omp.Plus_model_var(QNC_Variable("ga_avg", "A2L"))
        # omp.Plus_obs_var(QNC_Variable("Ga"))
        # obs_var_collection.Add(omp)

        omp = QNC_Obs_Model_Variable_Pair(name="LE")
        omp.Substract_model_var(QNC_Variable("qle_avg", "SPQ"))
        omp.Plus_obs_var(QNC_Variable("LE"))
        obs_var_collection.Add(omp)

        omp = QNC_Obs_Model_Variable_Pair(name="H")
        omp.Substract_model_var(QNC_Variable("qh_avg", "SPQ"))
        omp.Plus_obs_var(QNC_Variable("H"))
        obs_var_collection.Add(omp)

        omp = QNC_Obs_Model_Variable_Pair(name="Reco")
        omp.Plus_model_var(QNC_Variable("het_respiration_avg", "SB"))
        omp.Plus_model_var(QNC_Variable("gpp_avg", "Q_ASSIMI"))
        omp.Substract_model_var(QNC_Variable("npp_avg", "VEG"))

        omp = QNC_Obs_Model_Variable_Pair(name="PPFD")
        omp.Plus_model_var(QNC_Variable("appfd_avg", "RAD"))
        omp.Plus_obs_var(QNC_Variable("PPFD"))
        obs_var_collection.Add(omp)
        
        return obs_var_collection
                
    def Parse_Obs(self, rt_path):        
        self.nc_obs = QNC_obs_reader(rt_path)
        self.nc_obs.Parse_env_and_variables()        
        
        self.Obs_ref_data = {}        
        for pair in self.target_variable_list.Target_variables:
            self.Obs_ref_data[pair.name] = self.get_obs_df(pair=pair)
            
            factor = 1.0        
            if self.site == "DE-Hai":
                if 'LE' in pair.obs_vars_plus:
                    factor = 1.2
                    
            self.Obs_ref_data[pair.name] *= factor     
                
            
    def Parse_Mod(self, nc_output : QNC_ncdf_reader):      
          
        rmse_data = []
        df_compare = {}   
        for pair in self.target_variable_list.Target_variables:
            df_compare[pair.name] = self.get_mod_df(nc_output = nc_output, pair=pair)
                
        for pair in self.target_variable_list.Target_variables: 
                       
            df_compare[pair.name] = self.get_mod_df(nc_output = nc_output, pair=pair)            
            df_compare[pair.name][f"{pair.name}_obs"] = self.Obs_ref_data[pair.name][pair.name]
            df_compare[pair.name].dropna(inplace=True)
            rmse_this  = self.rmse(df_compare[pair.name][pair.name], 
                                   df_compare[pair.name][f"{pair.name}_obs"])
            rmse_data.append(rmse_this)
        self.list_rmse.append(rmse_data)
            
                
    def rmse(self,predictions, targets):
        return np.sqrt(((predictions - targets) ** 2).mean())       
        
    def get_obs_df(self, pair : QNC_Obs_Model_Variable_Pair):
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
        return dfs_obs    
        
    def get_mod_df(self, nc_output : QNC_ncdf_reader , pair : QNC_Obs_Model_Variable_Pair):
        model_plus = []
        for var in pair.model_vars_plus:
            df = nc_output.Read_1D_flat(var.cat, var.name)
            df.set_index('date', inplace=True)
            model_plus.append(df)

        model_minus = []
        for var in pair.model_vars_minus:
            df = nc_output.Read_1D_flat(var.cat, var.name)
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
        return dfs_model