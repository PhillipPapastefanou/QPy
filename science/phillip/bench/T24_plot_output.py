# %%
import os
import glob
import sys
import subprocess
import xarray as xr
import numpy as np
import pandas as pd
from time import perf_counter
import matplotlib.pyplot as plt

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

sys.path.append("/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy")
from src.postprocessing.qnc_defintions import Time_Reduction_Type
from src.postprocessing.qnc_output_parser import QNC_output_parser
from src.postprocessing.qnc_ncdf_reader import QNC_ncdf_reader
from src.postprocessing.qnc_rescaler import QNC_Rescaler
from src.postprocessing.qnc_obs_reader import QNC_obs_reader
from science.phillip.bench.ouput_bench_types import OutputBenchType


def rescale(df, time_reduction: Time_Reduction_Type):
        if time_reduction == Time_Reduction_Type.ThirtyMinSeries:
            # do nothing for now
            df_mod_rescale =  df
        elif time_reduction == Time_Reduction_Type.DailySeries:
            df_mod_rescale =  df.groupby(pd.Grouper(freq='d')).mean()
        elif time_reduction == Time_Reduction_Type.MonthlySeries:
            df_mod_rescale =  df.groupby(pd.Grouper(freq='1ME')).mean()
        elif time_reduction == Time_Reduction_Type.YearlySeries:
            df_mod_rescale =  df.groupby(pd.Grouper(freq='1YE')).mean()
        
        elif time_reduction == Time_Reduction_Type.ThirtyMinOfDay:
            df_mod_rescale = df
            df_mod_rescale['hour'] = df_mod_rescale.index.hour
            df_mod_rescale['minute'] = df_mod_rescale.index.minute
            df_mod_rescale = df_mod_rescale.groupby(['hour', 'minute']).mean()
            #df_mod_rescale = df_mod_rescale.to_dataframe()
            df_mod_rescale.reset_index(drop=True, inplace=True)
            #df_mod_rescale['hour'] = np.arange(0, 24, 24/df_mod_rescale.shape[0]) 
        elif time_reduction == Time_Reduction_Type.HourOfDay:
            df_mod_rescale = df
            df_mod_rescale['hour'] = df_mod_rescale.index.hour
            df_mod_rescale = df_mod_rescale.groupby('hour').mean()
            df_mod_rescale.reset_index(drop=True, inplace=True)
            #df_mod_rescale['hour'] = np.arange(0, 24)

        elif time_reduction == Time_Reduction_Type.DayOfYear:
            df_mod_rescale = df
            df_mod_rescale['dayofyear'] = df_mod_rescale.index.dayofyear
            df_mod_rescale = df_mod_rescale.groupby('dayofyear').mean()
            df_mod_rescale.reset_index(drop=True, inplace=True)
            #df_mod_rescale['dayofyear'] = np.arange(0, 366)
            
        elif time_reduction == Time_Reduction_Type.MonthOfYear:
            df_mod_rescale = df
            df_mod_rescale['monthofyear'] = df_mod_rescale.index.month
            df_mod_rescale = df_mod_rescale.groupby('monthofyear').mean()
            df_mod_rescale.reset_index(drop=True, inplace=True)
            #df_mod_rescale['monthofyear'] = np.arange(0, 12)
        else:
            print(f"Invalid time reduction type: {time_reduction.name}")
            exit(99)
        
        return df_mod_rescale

    
OUTPUT_DIR = '/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/11_transient_latin_hypercube_with_std_HAINICH_data'
OUTPUT_DIR = '/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/23_transient_latin_hypercube_with_std_HAINICH_data_full_2024_rs_work_high_gammastem'
post_dir = os.path.join(OUTPUT_DIR, 'post')
os.makedirs(post_dir, exist_ok=True)


rtobspath = '/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed'
df22fnet = pd.read_csv(os.path.join(rtobspath, "Fluxnet2000_2021_eval.csv"),  index_col=0, parse_dates=True)
df22fnet['LE'] = - df22fnet['LE']
df24fnet = pd.read_csv(os.path.join(rtobspath, "Fluxnet2023_2024_eval.csv"),  index_col=0, parse_dates=True)
df24fnet['LE'] = - df24fnet['LE']

df_psi_stem_obs = pd.read_csv(os.path.join(rtobspath, "PsiStem2023.csv"),  index_col=0, parse_dates=True)
df_sap_flow_obs = pd.read_csv(os.path.join(rtobspath, "Sapflow2023.csv"),  index_col=0, parse_dates=True)
df_sap_flow_obs.loc[df_sap_flow_obs['J0.5'] < 0.0, 'J0.5'] = 0.0

setups = []

obt = OutputBenchType()
obt.mod_var_cat   = 'PHYD'
obt.mod_var_name  = 'G_avg'
obt.plt_name      = 'G_avg'
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)

obt = OutputBenchType()
obt.mod_var_cat   = 'PHYD'
obt.mod_var_name  = 'stem_flow_avg'
obt.plt_name      = 'stem_flow_avg'
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)

obt = OutputBenchType()
obt.mod_var_cat   = 'Q_ASSIMI'
obt.mod_var_name  = 'beta_gs'
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)

obt = OutputBenchType()
obt.mod_var_cat   = 'PHYD'
obt.mod_var_name  = 'G_avg'
obt.obs_var_name  = 'J0.5'
obt.plt_name      = 'G_avg_obs'
obt.normalized = True
obt.df_obs = df_sap_flow_obs
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)

obt = OutputBenchType()
obt.mod_var_cat   = 'PHYD'
obt.mod_var_name  = 'stem_flow_avg'
obt.obs_var_name  = 'J0.5'
obt.normalized = True
obt.plt_name      = 'stem_flow_obs'
obt.df_obs = df_sap_flow_obs
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)



obt = OutputBenchType()
obt.mod_var_cat   = 'Q_ASSIMI'
obt.mod_var_name  = 'gpp_avg'
obt.obs_var_name  = 'GPP'
obt.df_obs = df22fnet
obt.plt_name = 'GPP22_obs'
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)


obt = OutputBenchType()
obt.mod_var_cat   = 'Q_ASSIMI'
obt.mod_var_name  = 'gpp_avg'
obt.plt_name  = 'GPP2017-2023'
obt.dt_begin = pd.to_datetime("01-01-2017")
obt.dt_end = pd.to_datetime("31-12-2023")
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)

obt = OutputBenchType()
obt.mod_var_cat   = 'PHYD'
obt.mod_var_name  = 'psi_leaf_avg'
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)

obt = OutputBenchType()
obt.mod_var_cat   = 'PHYD'
obt.mod_var_name  = 'psi_stem_avg'
obt.plt_name      = 'psi_stem_avg'
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)

obt = OutputBenchType()
obt.mod_var_cat   = 'SPQ'
obt.mod_var_name  = 'transpiration_avg'
obt.plt_name      = 'transpiration_avg'
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)


obt = OutputBenchType()
obt.mod_var_cat   = 'PHYD'
obt.mod_var_name  = 'psi_stem_avg'
obt.plt_name      = 'psi_stem_avg_2023'
obt.dt_begin = pd.to_datetime("01-01-2023")
obt.dt_end = pd.to_datetime("31-12-2023")
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)

obt = OutputBenchType()
obt.mod_var_cat   = 'PHYD'
obt.mod_var_name  = 'psi_stem_avg'
obt.plt_name      = 'psi_stem_avg_2017-2023'
obt.dt_begin = pd.to_datetime("01-01-2017")
obt.dt_end = pd.to_datetime("31-12-2023")
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)


obt = OutputBenchType()
obt.mod_var_cat   = 'PHYD'
obt.mod_var_name  = 'psi_leaf_avg'
obt.plt_name      = 'psi_leaf_avg_2017-2023'
obt.dt_begin = pd.to_datetime("01-01-2017")
obt.dt_end = pd.to_datetime("31-12-2023")
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)


obt = OutputBenchType()
obt.mod_var_cat   = 'PHYD'
obt.mod_var_name  = 'psi_stem_avg'
obt.obs_var_name  = 'FAG'
obt.df_obs        = df_psi_stem_obs
obt.plt_name      = 'psi_stem_2023_obs'
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)

obt = OutputBenchType()
obt.mod_var_cat   = 'VEG'
obt.mod_var_name  = 'total_veg_c'
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)

obt = OutputBenchType()
obt.mod_var_cat   = 'VEG'
obt.mod_var_name  = 'LAI'
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)

obt = OutputBenchType()
obt.mod_var_cat   = 'SPQ'
obt.mod_var_name  = 'qle_avg'
obt.obs_var_name  = 'LE'
obt.df_obs        = df22fnet
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)

obt = OutputBenchType()
obt.mod_var_cat   = 'Q_ASSIMI'
obt.mod_var_name  = 'gc_avg'
obt.fig = plt.figure(figsize=(16, 12))
setups.append(obt)


ax_ax_list = []
for setup in setups:
    axs = []
    i = 1
    for reduc_type in list(Time_Reduction_Type):    
        axs.append(setup.fig.add_subplot(3, 3, i))
        i += 1
    ax_ax_list.append(axs)


cat_error = 'rmseStem'
fids  =  [0,2120, 4914, 4972, 5962, 6129, 7251, 8025, 8269, 8949, 9769, 15671]

# cat_error = 'slope'
# fids  =  [0,3050, 16317,
#  8220,
#  15476,
#  14592,
#  3493,
#  11970,
#  526,
#  16140,
#  15434]

for fid in fids:
    parser = QNC_output_parser(os.path.join(OUTPUT_DIR,'output', str(fid)))
    parser.Read()
    output = parser.Available_outputs['fluxnetdata']
    nc_output = QNC_ncdf_reader(os.path.join(OUTPUT_DIR, 'output', str(fid)),
                                            output.Categories,
                                            output.Identifier,
                                            output.Time_resolution
                                            )
    nc_output.Parse_env_and_variables()   
    nc_output.Read_all_1D()        
    nc_output.Close()
   
    fig_index = 0 
    for setup in setups:
        
        axs = ax_ax_list[fig_index]              
        i = 1
        for reduc_type in list(Time_Reduction_Type):    
            ax = axs[i - 1]
            cat = setup.mod_var_cat
            var_name_mod = setup.mod_var_name
            var_name_obs = setup.obs_var_name
            
            df = nc_output.Datasets_1D[cat][['date', var_name_mod]]
            df.set_index('date', inplace = True)            
            
            if var_name_obs is not None:      
                df_obs = setup.df_obs               
                df = pd.merge(df[var_name_mod], df_obs[var_name_obs], left_index=True, right_index=True, how='inner')
                    
            if setup.dt_begin is not None:                            
                df = df[df.index >= setup.dt_begin]
            
            if setup.dt_end is not None:                            
                df = df[df.index <= setup.dt_end]
                
                                
            df = rescale(df = df, time_reduction= reduc_type)
                        
            if var_name_obs is not None:  
                if setup.normalized:
                    df[var_name_mod] = df[var_name_mod]/np.max(df[var_name_mod])
                    df[var_name_obs] = df[var_name_obs]/np.max(df[var_name_obs])
                                
            
            if fid == 0:
                ax.plot(df[var_name_mod],c = 'tab:blue', alpha = 0.75, label = 'Q-std')                
                if var_name_obs is not None:                                                                                                  
                        ax.plot(df[var_name_obs], c = 'black', label = 'F')                      
                                
            else: 
                ax.plot(df[var_name_mod], c = 'tab:red', alpha = 0.75)
                
                # if var_name_mod == 'psi_stem_avg':
                #     if reduc_type == Time_Reduction_Type.HourOfDay:
                #         maxss = np.max(df[var_name_mod])
                #         if maxss > -0.03:                        
                #             print(np.max(df[var_name_mod]))
                #             print(i)
                #             # break
                    
            ax.set_title(reduc_type.name)
            ax.legend()
            
            i += 1
        fig_index += 1
    
    print(fid)
    
os.makedirs(os.path.join(post_dir, "plt"), exist_ok=True)
        
for setup in setups:
    if setup.plt_name ==  None:       
        setup.fig.savefig(os.path.join(post_dir, "plt", f"{cat_error}_sel_{setup.mod_var_name}.png"), bbox_inches='tight', dpi = 150)
    else: 
        setup.fig.savefig(os.path.join(post_dir, "plt", f"{cat_error}_sel_{setup.plt_name}.png"), bbox_inches='tight', dpi = 150)


# %%



  
plt.show()

# %%


