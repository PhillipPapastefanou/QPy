import xarray as xr
import numpy as np
import os
import pandas as pd
import matplotlib.pyplot as plt
from enum import Enum

class SimPhase(Enum):
    STATIC=0
    SPINUP=1
    TRANSIENT=2
    FLUXNETDATA=3

class Quincy_Multi_Run_Plot:
    def __init__(self, run_directory, obs_path):
        self.run_directory = run_directory
        
        # Create postprocessing directory
        os.makedirs(os.path.join(self.run_directory, "post_process"), exist_ok=True)
        
        self.base_path_output = os.path.join(self.run_directory, "output")
        self.subdirs = [int(d) for d in os.listdir(self.base_path_output) if os.path.isdir(os.path.join(self.base_path_output, d))]
        self.subdirs.sort()
        
        if not self.subdirs:
            print("Empty output. Stopping processing")
            return
        
        files = os.listdir(os.path.join(self.base_path_output, str(self.subdirs[0])))
        for file in files:
            if 'static' in file:
                self.is_static = True
            else:
                self.is_static = False
                
        
        self.df_obs = pd.read_csv(obs_path)

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
                
            elif res == 'Y':
                dfg = df_mod.groupby([df_mod.index.year]).agg(
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
        plt.savefig(os.path.join(self.run_directory, "post_process", f"{varname}.png"))
        
        
        
    def plot_variable_multi_time(self, cat, varname, sim_phase = SimPhase.STATIC):   
                   
        if self.is_static:
            title = "STATIC"
            file_str = f"{title.lower()}_daily"
            
        else:
            if sim_phase == SimPhase.SPINUP:
                title = "SPINUP"
                file_str = f"{title.lower()}_yearly"   
            elif sim_phase == SimPhase.TRANSIENT:
                title = "TRANSIENT"  
                file_str = f"{title.lower()}_daily"   
            elif sim_phase == SimPhase.FLUXNETDATA:
                title = "FLUXNETDATA"
                file_str = f"{title.lower()}_timestep"
            else:
                print("Static or no simphase selected, switching to transient")
                title = "TRANSIENT"  
                file_str = f"{title.lower()}_daily"   
            
            

        # Create a figure with 4 subplots in a 2x2 grid
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        
        plt.suptitle(title, fontsize=16, fontweight='bold')
        
        df_p  = pd.read_csv(os.path.join(self.base_path_output, os.pardir, "parameters.csv"))
        
        
        for run in self.subdirs:      
               
            ds_mod = xr.open_dataset(os.path.join(self.base_path_output, str(run), f"{cat}_{file_str}.nc"))
            
            unitname = ds_mod[varname].units
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
            
            mask = (df_mod.index.strftime("%m-%d") >= "09-15") & (df_mod.index.strftime("%m-%d") <= "10-15")
            df_mod = df_mod[mask]
            
            row = df_p.loc[run]  # get row by index

            # drop id and fid, then format
            row_str = ", ".join(f"{col}:{row[col]}" for col in df_p.columns if col not in ["id", "fid"])
   
            if sim_phase == SimPhase.FLUXNETDATA:
            
                dfg = df_mod.groupby([df_mod.index.hour, df_mod.index.minute]).agg(
                var_mean_mod=(varname, "mean"),
                var_q25_mod=(varname, lambda x: x.quantile(0.25)),
                var_median_mod=(varname, "median"),
                var_q75_mod=(varname, lambda x: x.quantile(0.75)))
                
                axes[0, 0].plot(np.arange(0,24, 0.5), dfg['var_mean_mod'], label = row_str)
                axes[0, 0].set_ylabel(f'{varname}\n[{unitname}]')
                axes[0, 0].set_xlabel(f'hour of day')
                axes[0, 0].legend()
                
            else:
                dfg = df_mod.groupby([df_mod.index.day_of_year]).agg(
                var_mean_mod=(varname, "mean"),
                var_q25_mod=(varname, lambda x: x.quantile(0.25)),
                var_median_mod=(varname, "median"),
                var_q75_mod=(varname, lambda x: x.quantile(0.75)))
                
                axes[0, 0].plot(dfg['var_mean_mod'], label = row_str)
                axes[0, 0].set_ylabel(f'{varname}\n[{unitname}]')
                axes[0, 0].set_xlabel(f'day of year')
                axes[0, 0].legend()    
                
            dfg = df_mod.groupby([df_mod.index.month]).agg(
            var_mean_mod=(varname, "mean"),
            var_q25_mod=(varname, lambda x: x.quantile(0.25)),
            var_median_mod=(varname, "median"),
            var_q75_mod=(varname, lambda x: x.quantile(0.75)))
            
            axes[0, 1].plot(dfg['var_mean_mod'], label = run)
            axes[0, 1].set_ylabel(f'{varname}\n[{unitname}]')
            axes[0, 1].set_xlabel(f'month of year')
                

            dfg = df_mod.groupby([df_mod.index.year]).agg(
            var_mean_mod=(varname, "mean"),
            var_q25_mod=(varname, lambda x: x.quantile(0.25)),
            var_median_mod=(varname, "median"),
            var_q75_mod=(varname, lambda x: x.quantile(0.75)))
            
            axes[1, 0].plot(dfg['var_mean_mod'], label = run)
            axes[1, 0].set_ylabel(f'{varname}\n[{unitname}]')
            axes[1, 0].set_xlabel(f'year')                

            dfg = df_mod.groupby([df_mod.index.year, df_mod.index.month]).agg(
            var_mean_mod=(varname, "mean"),
            var_q25_mod=(varname, lambda x: x.quantile(0.25)),
            var_median_mod=(varname, "median"),
            var_q75_mod=(varname, lambda x: x.quantile(0.75)))
            
            dfg.index = pd.to_datetime({
            "year": dfg.index.get_level_values(0),
            "month": dfg.index.get_level_values(1),
            "day": 1})
                
            axes[1, 1].plot(dfg['var_mean_mod'], label = run)
            axes[1, 1].set_ylabel(f'{varname}\n[{unitname}]')
            axes[1, 1].set_xlabel(f'year')    
            axes[1, 1].legend()
           
        
        plt.legend()
        plt.subplots_adjust(wspace=0.2)
        plt.savefig(os.path.join(self.run_directory, "post_process", f"{varname}_{title.lower()}.png"))
                  
    def plot_against_NEE_variable_multi_time(self):
        
        # Create a figure with 4 subplots in a 2x2 grid
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        
        if self.is_static:
            print("Comparing against NEE obs does only work when using transient runs")
            return
        
        for run in self.subdirs:      
               
            ds_mod_ass = xr.open_dataset(os.path.join(self.base_path_output, str(run),"Q_ASSIMI_fluxnetdata_timestep.nc"))
            ds_mod_veg = xr.open_dataset(os.path.join(self.base_path_output, str(run), "VEG_fluxnetdata_timestep.nc"))
            ds_mod_sb  = xr.open_dataset(os.path.join(self.base_path_output, str(run), "SB_fluxnetdata_timestep.nc"))
            
            df_mod = ds_mod_veg['npp_avg'].to_pandas().to_frame()
            df_mod['gpp_avg'] = ds_mod_ass['gpp_avg']
            df_mod['nee_avg'] = -(ds_mod_veg['npp_avg'] -ds_mod_sb['het_respiration_avg'])

            df_mod['Year'] = df_mod.index.year
            df_mod['day_of_year_adj'] = df_mod.index.dayofyear
            df_mod['Hour'] = df_mod.index.hour
            df_mod['Minute'] = df_mod.index.minute
            
            
            df_merged = pd.merge(
            df_mod,
            self.df_obs,
            on=["Year", "day_of_year_adj", "Hour", "Minute"],
            how="inner"   # or "outer", "left", "right" depending on your need
                                )

            df_merged['datetime'] = (
                pd.to_datetime(df_merged['Year'].astype(str), format='%Y')  # start of the year
                + pd.to_timedelta(df_merged['day_of_year_adj'], unit='D')  # adjust day of year
                + pd.to_timedelta(df_merged['Hour'], unit='h')
                + pd.to_timedelta(df_merged['Minute'], unit='m')
            )
            df_merged.set_index('datetime', inplace=True)
                    
   

            
            
            
            dfm = df_merged.groupby([df_merged.index.day_of_year]).agg(
            nee_mean_mod=("nee_avg", "mean"),
            nee_q25_mod=("nee_avg", lambda x: x.quantile(0.25)),
            nee_median_mod=("nee_avg", "median"),
            nee_q75_mod=("nee_avg", lambda x: x.quantile(0.75)),
            
            nee_mean_obs=("NEE_U50_orig", "mean"),
            nee_q25_obs=("NEE_U50_orig", lambda x: x.quantile(0.25)),
            nee_median_obs=("NEE_U50_orig", "median"),
            nee_q75_obs=("NEE_U50_orig", lambda x: x.quantile(0.75))
            )
   
            # dfm.index = pd.to_datetime({
            # "year": dfm.index.get_level_values(0),
            # "month": dfm.index.get_level_values(1),
            # "day": 1})
            
  
            if run == 0: 
                axes[0, 0].plot(dfm['nee_mean_obs'], label = 'obs')
            axes[0, 0].plot(dfm['nee_mean_mod'], label = run)
            axes[0, 0].set_ylabel(f'NEE_avg\n[micro mol m-2 s-1]')
            axes[0, 0].set_xlabel(f'day of year')
                
                
                
            dfm = df_merged.groupby([df_merged.index.month]).agg(
            nee_mean_mod=("nee_avg", "mean"),
            nee_q25_mod=("nee_avg", lambda x: x.quantile(0.25)),
            nee_median_mod=("nee_avg", "median"),
            nee_q75_mod=("nee_avg", lambda x: x.quantile(0.75)),
            
            nee_mean_obs=("NEE_U50_orig", "mean"),
            nee_q25_obs=("NEE_U50_orig", lambda x: x.quantile(0.25)),
            nee_median_obs=("NEE_U50_orig", "median"),
            nee_q75_obs=("NEE_U50_orig", lambda x: x.quantile(0.75))
            )
   
            # dfm.index = pd.to_datetime({
            # "year": dfm.index.get_level_values(0),
            # "month": dfm.index.get_level_values(1),
            # "day": 1})
            
  
            if run == 0: 
                axes[0, 1].plot(dfm['nee_mean_obs'], label = 'obs')
            axes[0, 1].plot(dfm['nee_mean_mod'], label = run)
            axes[0, 1].set_ylabel(f'NEE_avg\n[micro mol m-2 s-1]')
            axes[0, 1].set_xlabel(f'month of year')
               







            dfm = df_merged.groupby([df_merged.index.year]).agg(
            nee_mean_mod=("nee_avg", "mean"),
            nee_q25_mod=("nee_avg", lambda x: x.quantile(0.25)),
            nee_median_mod=("nee_avg", "median"),
            nee_q75_mod=("nee_avg", lambda x: x.quantile(0.75)),
            
            nee_mean_obs=("NEE_U50_orig", "mean"),
            nee_q25_obs=("NEE_U50_orig", lambda x: x.quantile(0.25)),
            nee_median_obs=("NEE_U50_orig", "median"),
            nee_q75_obs=("NEE_U50_orig", lambda x: x.quantile(0.75))
            )
   
            # dfm.index = pd.to_datetime({
            # "year": dfm.index.get_level_values(0),
            # "month": dfm.index.get_level_values(1),
            # "day": 1})
            
  
            if run == 0: 
                axes[1, 0].plot(dfm['nee_mean_obs'], label = 'obs')
            axes[1, 0].plot(dfm['nee_mean_mod'], label = run)
            axes[1, 0].set_ylabel(f'NEE_avg\n[micro mol m-2 s-1]')
            axes[1, 0].set_xlabel(f'year')          





            dfm = df_merged.groupby([df_merged.index.year, df_merged.index.month]).agg(
            nee_mean_mod=("nee_avg", "mean"),
            nee_q25_mod=("nee_avg", lambda x: x.quantile(0.25)),
            nee_median_mod=("nee_avg", "median"),
            nee_q75_mod=("nee_avg", lambda x: x.quantile(0.75)),
            
            nee_mean_obs=("NEE_U50_orig", "mean"),
            nee_q25_obs=("NEE_U50_orig", lambda x: x.quantile(0.25)),
            nee_median_obs=("NEE_U50_orig", "median"),
            nee_q75_obs=("NEE_U50_orig", lambda x: x.quantile(0.75))
            )
   
            dfm.index = pd.to_datetime({
            "year": dfm.index.get_level_values(0),
            "month": dfm.index.get_level_values(1),
            "day": 1})
            
  
            if run == 0: 
                axes[1, 1].plot(dfm['nee_mean_obs'], label = 'obs')
            axes[1, 1].plot(dfm['nee_mean_mod'], label = run)
            axes[1, 1].set_ylabel(f'NEE_avg\n[micro mol m-2 s-1]')
            axes[1, 1].set_xlabel(f'year')    
            axes[1, 1].legend()
           
        
        plt.legend()
        plt.subplots_adjust(wspace=0.2)
        plt.savefig(os.path.join(self.run_directory, "post_process", f"NEE_obs_all_time.png"))
        
    def plot_against_PSILEAF_variable_multi_time(self, psi_leaf_path_obs, g):
        
        if self.is_static:
            print("Comparing against NEE obs does only work when using transient runs")
            return
        
        # Create a figure with 4 subplots in a 2x2 grid
        fig, axes = plt.subplots(1,2, figsize=(12, 8))
        
        plt.suptitle('PSI_LEAF', fontsize=16, fontweight='bold')
        
        

        df_p  = pd.read_csv(os.path.join(self.base_path_output, os.pardir, "parameters.csv"))
        
        
        df_leaf = pd.read_csv(psi_leaf_path_obs,
                        sep=";", decimal=",",   index_col=0)

        cols = [c for c in df_leaf.columns if f"spec_pl_{g}_" in c]
        mean_obs_pl, std_obs_pl = df_leaf[cols].mean(axis=1), df_leaf[cols].std(axis=1)
        
        df_leaf.index = pd.to_datetime(df_leaf.index, format="%H:%M").hour + pd.to_datetime(df_leaf.index, format="%H:%M").minute / 60

        
        for run in self.subdirs:      
               
            ds_mod = xr.open_dataset(os.path.join(self.base_path_output, str(run), f"PHYD_fluxnetdata_timestep.nc"))
            
            unitname = ds_mod['psi_leaf_avg'].units
            df_mod = ds_mod[['psi_leaf_avg','psi_stem_avg']].to_pandas()
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
            
            mask = (df_mod.index.strftime("%m-%d") >= "09-15") & (df_mod.index.strftime("%m-%d") <= "10-15")
            df_mod = df_mod[mask]
            
            row = df_p.loc[run]  # get row by index

            # drop id and fid, then format
            row_str = ", ".join(f"{col}:{row[col]}" for col in df_p.columns if col not in ["id", "fid"])
   
            dfg = df_mod.groupby([df_mod.index.hour, df_mod.index.minute]).agg(
            var_mean_mod=('psi_leaf_avg', "mean"),
            var_q25_mod=('psi_leaf_avg', lambda x: x.quantile(0.25)),
            var_median_mod=('psi_leaf_avg', "median"),
            var_q75_mod=('psi_leaf_avg', lambda x: x.quantile(0.75)),
            var_mean_mod_stem=('psi_stem_avg', "mean")
            
            )
            
            axes[0].plot(np.arange(0,24, 0.5), dfg['var_mean_mod'], label = str(run))
            axes[0].set_ylabel(f'psi_leaf_avg\n[{unitname}]')
            axes[0].set_xlabel(f'hour of day')
            axes[0].legend()
            
            axes[1].plot(np.arange(0,24, 0.5), dfg['var_mean_mod_stem'], label = row_str)
            axes[1].set_ylabel(f'psi_leaf_avg\n[{unitname}]')
            axes[1].set_xlabel(f'hour of day')
            axes[1].legend()
            
            
            
        axes[0].errorbar(df_leaf.index, mean_obs_pl, yerr=std_obs_pl, fmt='o', capsize=5, c= 'black')

                  
        plt.legend()
        plt.subplots_adjust(wspace=0.2)
        plt.savefig(os.path.join(self.run_directory, "post_process", f"psi_leaf_obs_sep_oct_spec_{g}.png"))

