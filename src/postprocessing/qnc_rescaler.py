import os
import pandas as pd
import numpy as np

from src.postprocessing.qnc_obs_reader import QNC_obs_reader
from src.postprocessing.qnc_ncdf_reader import QNC_ncdf_reader
from src.postprocessing.qnc_defintions import Time_Reduction_Type

class QNC_Rescaler:

    def __init__(self, mod_reader: QNC_ncdf_reader, obs_reader = None):
        self.obs_reader = obs_reader
        self.mod_reader = mod_reader
            
    
    def Get_reduced_1D_dataframe(self, cat_mod,
                                 varname_mod, 
                                 time_reduction : Time_Reduction_Type, 
                                 varname_obs = None):      
        
        df_obs = None
        
        if (varname_obs != None) & (self.obs_reader == None):
            print("Obs variable set, but no observational datase has been specified")
            exit(99)
        if (varname_obs != None) & (self.obs_reader != None):
            df_obs = self.obs_reader.Read_data(var_name = varname_obs)

           
        df_mod = self.mod_reader.Datasets_1D[cat_mod][['date', varname_mod]]
       
        if time_reduction == Time_Reduction_Type.ThirtyMinSeries:
            df_mod_rescale =  df_mod.set_index('date')
        elif time_reduction == Time_Reduction_Type.DailySeries:
            df_mod_rescale =  df_mod.groupby(pd.Grouper(key='date', freq='d')).mean()
        elif time_reduction == Time_Reduction_Type.MonthlySeries:
            df_mod_rescale =  df_mod.groupby(pd.Grouper(key='date', freq='1ME')).mean()
        elif time_reduction == Time_Reduction_Type.YearlySeries:
            df_mod_rescale =  df_mod.groupby(pd.Grouper(key='date', freq='1YE')).mean()
        
        elif time_reduction == Time_Reduction_Type.ThirtyMinOfDay:
            df_mod_rescale = df_mod
            df_mod_rescale['hour'] = df_mod_rescale['date'].dt.hour
            df_mod_rescale['minute'] = df_mod_rescale['date'].dt.minute
            df_mod_rescale = df_mod_rescale.groupby(['hour', 'minute']).mean()
            #df_mod_rescale = df_mod_rescale.to_dataframe()
            df_mod_rescale.reset_index(drop=True, inplace=True)
            df_mod_rescale['hour'] = np.arange(0, 24, 0.5) 
        elif time_reduction == Time_Reduction_Type.HourOfDay:
            df_mod_rescale = df_mod
            df_mod_rescale['hour'] = df_mod_rescale['date'].dt.hour
            df_mod_rescale = df_mod_rescale.groupby('hour').mean()
            df_mod_rescale.reset_index(drop=True, inplace=True)
            df_mod_rescale['hour'] = np.arange(0, 24)

        elif time_reduction == Time_Reduction_Type.DayOfYear:
            df_mod_rescale = df_mod
            df_mod_rescale['dayofyear'] = df_mod_rescale['date'].dt.dayofyear
            df_mod_rescale = df_mod_rescale.groupby('dayofyear').mean()
            df_mod_rescale.reset_index(drop=True, inplace=True)
            df_mod_rescale['dayofyear'] = np.arange(0, 366)
            
        elif time_reduction == Time_Reduction_Type.MonthOfYear:
            df_mod_rescale = df_mod
            df_mod_rescale['monthofyear'] = df_mod_rescale['date'].dt.month
            df_mod_rescale = df_mod_rescale.groupby('monthofyear').mean()
            df_mod_rescale.reset_index(drop=True, inplace=True)
            df_mod_rescale['monthofyear'] = np.arange(0, 12)
        else:
            print(f"Invalid time reduction type: {time_reduction.name}")
            exit(99)
            
        
        if df_obs is not None:            
            if time_reduction == Time_Reduction_Type.ThirtyMinSeries:
                df_mod_rescale = pd.merge(df_mod_rescale, df_obs[varname_obs],
                                          left_index=True, right_index=True, how='outer')
            elif time_reduction == Time_Reduction_Type.DailySeries:
                df_obs_rescale =  df_obs.groupby(pd.Grouper(freq='d')).mean()
                df_mod_rescale = pd.merge(df_mod_rescale, df_obs_rescale[varname_obs],
                                          left_index=True, right_index=True, how='outer')
            elif time_reduction == Time_Reduction_Type.MonthlySeries:
                df_obs_rescale =  df_obs.groupby(pd.Grouper(freq='1ME')).mean()
                df_mod_rescale = pd.merge(df_mod_rescale, df_obs_rescale[varname_obs],
                                          left_index=True, right_index=True, how='outer')
            elif time_reduction == Time_Reduction_Type.YearlySeries:
                df_obs_rescale =  df_obs.groupby(pd.Grouper(freq='1YE')).mean()
                df_mod_rescale = pd.merge(df_mod_rescale, df_obs_rescale[varname_obs],
                                          left_index=True, right_index=True, how='outer')
            
            elif time_reduction == Time_Reduction_Type.ThirtyMinOfDay:
                df_obs_rescale = df_obs
                df_obs_rescale['hour'] = df_obs_rescale.index.hour
                df_obs_rescale['minute'] = df_obs_rescale.index.minute
                df_obs_rescale = df_obs_rescale.groupby(['hour', 'minute']).mean()
                #df_mod_rescale = df_mod_rescale.to_dataframe()
                df_obs_rescale.reset_index(drop=True, inplace=True)
                df_obs_rescale['hour'] = np.arange(0, 24, 0.5)
                df_mod_rescale = pd.merge(df_mod_rescale, df_obs_rescale[varname_obs],
                                        left_index=True, right_index=True, how='outer')
            elif time_reduction == Time_Reduction_Type.HourOfDay:
                df_obs_rescale = df_obs
                df_obs_rescale['hour'] = df_obs_rescale.index.hour
                df_obs_rescale = df_obs_rescale.groupby('hour').mean()
                #df_mod_rescale = df_mod_rescale.to_dataframe()
                df_obs_rescale.reset_index(drop=True, inplace=True)
                df_obs_rescale['hour'] = np.arange(0, 24, 1.0)
                df_mod_rescale = pd.merge(df_mod_rescale, df_obs_rescale[varname_obs],
                                        left_index=True, right_index=True, how='outer')

            elif time_reduction == Time_Reduction_Type.DayOfYear:
                df_obs_rescale = df_obs
                df_obs_rescale.index = pd.to_datetime(df_obs_rescale.index)
                df_obs_rescale['dayofyear'] = df_obs_rescale.index.dayofyear
                df_obs_rescale = df_obs_rescale.groupby('dayofyear').mean()
                df_obs_rescale.reset_index(drop=True, inplace=True)
                df_obs_rescale['dayofyear'] = np.arange(0, 366)
                df_mod_rescale = pd.merge(df_mod_rescale, df_obs_rescale[varname_obs],
                                        left_index=True, right_index=True, how='outer')
                
            elif time_reduction == Time_Reduction_Type.MonthOfYear:
                df_obs_rescale = df_obs
                df_obs_rescale.index = pd.to_datetime(df_obs_rescale.index)
                df_obs_rescale['monthofyear'] = df_obs_rescale.index.month
                df_obs_rescale = df_obs_rescale.groupby('monthofyear').mean()
                df_obs_rescale.reset_index(drop=True, inplace=True)
                df_obs_rescale['monthofyear'] = np.arange(0, 12)
                df_mod_rescale = pd.merge(df_mod_rescale, df_obs_rescale[varname_obs],
                                        left_index=True, right_index=True, how='outer')
            else:
                print(f"Invalid time reduction type: {time_reduction.name}")
                exit(99)
                       
            
            
        return df_mod_rescale
            
        
        
        
        