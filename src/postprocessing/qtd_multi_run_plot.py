import xarray as xr
import numpy as np
import os
import pandas as pd
import matplotlib.pyplot as plt

class Quincy_Multi_Run_Plot:
    def __init__(self, run_directory):
        self.run_directory = run_directory
        
        # Create postprocessing directory
        os.makedirs(os.path.join(self.run_directory, os.pardir, "post_process"), exist_ok=True)
        
        self.base_path_output = os.path.join(self.run_directory, "output")
        self.subdirs = [int(d) for d in os.listdir(self.base_path_output) if os.path.isdir(os.path.join(self.base_path_output, d))]
        self.subdirs.sort()
        
        if not self.subdirs:
            print("Empty output. Stopping processing")
            return
    

    def plot_variable(self,cat, varname, res):
        
        fig = plt.figure(figsize=(12,8))
        ax= fig.add_subplot(1,1,1)
        
        for run in self.subdirs:      
               
            ds_mod = xr.open_dataset(os.path.join(self.base_path_output, str(run), f"{cat}_static_daily.nc"))
            
            df_mod = ds_mod[varname].to_pandas().to_frame()   
            df_mod['Year'] = df_mod.index.year
            df_mod['day_of_year_adj'] = df_mod.index.dayofyear
            df_mod['Hour'] = df_mod.index.hour
            df_mod['Minute'] = df_mod.index.minute
            
            
            df_mod['datetime'] = (
            pd.to_datetime(df_mod['Year'].astype(str), format='%Y')  # start of the year
            + pd.to_timedelta(df_mod['day_of_year_adj'], unit='D')  # adjust day of year
            + pd.to_timedelta(df_mod['Hour'], unit='h')
            + pd.to_timedelta(df_mod['Minute'], unit='m'))
            df_mod.set_index('datetime', inplace=True) 
            
            ds_mod.close()
            
            if res == 'D':
                dfg = df_mod.groupby([df_mod.index.day_of_year]).agg(
                var_mean_mod=(varname, "mean"),
                var_q25_mod=(varname, lambda x: x.quantile(0.25)),
                var_median_mod=(varname, "median"),
                var_q75_mod=(varname, lambda x: x.quantile(0.75)))
                
            elif res == 'M':
                dfg = df_mod.groupby([df_mod.index.month]).agg(
                var_mean_mod=(varname, "mean"),
                var_q25_mod=(varname, lambda x: x.quantile(0.25)),
                var_median_mod=(varname, "median"),
                var_q75_mod=(varname, lambda x: x.quantile(0.75)))
                
            elif res == 'YM':
                dfg = df_mod.groupby([df_mod.index.year, df_mod.index.month]).agg(
                var_mean_mod=(varname, "mean"),
                var_q25_mod=(varname, lambda x: x.quantile(0.25)),
                var_median_mod=(varname, "median"),
                var_q75_mod=(varname, lambda x: x.quantile(0.75)))
                
                dfg.index = pd.to_datetime({
                "year": dfg.index.get_level_values(0),
                "month": dfg.index.get_level_values(1),
                "day": 1})
                
            else:
                print("Error: Unsupported aggreation")
                return    
            
            ax.plot(dfg['var_mean_mod'], label = run)
        plt.legend()
        plt.savefig(os.path.join(self.run_directory, os.pardir, "post_process", f"{varname}.png"))
            
            
            