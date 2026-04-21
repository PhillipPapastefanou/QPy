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
OUTPUT_DIR = '/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/kmax_gammastem/10_run_slope_opt_manu_soil_params'
OUTPUT_DIR = '/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/pheno_hydro/02_manu_soil_params_phenology'
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

def init_setups():
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
    obt.ylab = r"$J$ norm.[-]"
    setups.append(obt)

    obt = OutputBenchType()
    obt.mod_var_cat   = 'Q_ASSIMI'
    obt.mod_var_name  = 'beta_gs'
    obt.ylab = r"$\beta$ [-]"
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
    obt.ylab = r"$J$ norm.[-]"
    obt.fig = plt.figure(figsize=(16, 12))
    setups.append(obt)

    obt = OutputBenchType()
    obt.mod_var_cat   = 'Q_ASSIMI'
    obt.mod_var_name  = 'gpp_avg'
    obt.obs_var_name  = 'GPP'
    obt.df_obs = df22fnet
    obt.ylab = r"$\mathrm{\mu mol \ m^{-2}\  s^{-1}}$"
    obt.plt_name = 'GPP22_obs'
    obt.fig = plt.figure(figsize=(16, 12))
    setups.append(obt)

    obt = OutputBenchType()
    obt.mod_var_cat   = 'Q_ASSIMI'
    obt.mod_var_name  = 'gpp_avg'
    obt.obs_var_name  = 'GPP'
    obt.ylab = r"$\mathrm{\mu mol \ m^{-2}\  s^{-1}}$"
    obt.df_obs = df22fnet
    obt.plt_name = 'GPP18_obs'
    obt.dt_begin = pd.to_datetime("01-01-2018")
    obt.dt_end = pd.to_datetime("31-12-2018")
    obt.fig = plt.figure(figsize=(16, 12))
    setups.append(obt)


    obt = OutputBenchType()
    obt.mod_var_cat   = 'Q_ASSIMI'
    obt.mod_var_name  = 'gpp_avg'
    obt.plt_name  = 'GPP2017-2023'
    obt.ylab = r"$\mathrm{\mu mol \ m^{-2}\  s^{-1}}$"
    obt.dt_begin = pd.to_datetime("01-01-2017")
    obt.dt_end = pd.to_datetime("31-12-2023")
    obt.fig = plt.figure(figsize=(16, 12))
    setups.append(obt)

    obt = OutputBenchType()
    obt.mod_var_cat   = 'PHYD'
    obt.mod_var_name  = 'psi_leaf_avg'
    obt.ylab = r"$\psi_\mathrm{leaf}$ [$\mathrm{MPa}$]"
    obt.fig = plt.figure(figsize=(16, 12))
    setups.append(obt)

    obt = OutputBenchType()
    obt.mod_var_cat   = 'PHYD'
    obt.mod_var_name  = 'psi_stem_avg'
    obt.plt_name      = 'psi_stem_avg'
    obt.ylab = r"$\psi_\mathrm{stem}$ [$\mathrm{MPa}$]"
    obt.fig = plt.figure(figsize=(16, 12))

    setups.append(obt)

    obt = OutputBenchType()
    obt.mod_var_cat   = 'SPQ'
    obt.mod_var_name  = 'transpiration_avg'
    obt.plt_name      = 'transpiration_avg'
    obt.ylab = r"[$\mathrm{mm}$ $\mathrm{s}^{-1}$]"
    obt.fig = plt.figure(figsize=(16, 12))
    setups.append(obt)

    obt = OutputBenchType()
    obt.mod_var_cat   = 'SPQ'
    obt.mod_var_name  = 'rootzone_soilwater_potential'
    obt.plt_name      = 'rootzone_soilwater_potential_23'
    obt.dt_begin = pd.to_datetime("01-04-2023")
    obt.dt_end = pd.to_datetime("31-12-2023")
    obt.ylab = r"$\psi_\mathrm{root_{avg}}$ [$\mathrm{MPa}$]"
    obt.fig = plt.figure(figsize=(16, 12))
    setups.append(obt)
    
    obt = OutputBenchType()
    obt.mod_var_cat   = 'SPQ'
    obt.mod_var_name  = 'rootzone_soilwater_potential'
    obt.plt_name      = 'rootzone_soilwater_potential'
    obt.ylab = r"$\psi_\mathrm{root_{avg}}$ [$\mathrm{MPa}$]"
    obt.fig = plt.figure(figsize=(16, 12))
    setups.append(obt)

    obt = OutputBenchType()
    obt.mod_var_cat   = 'PHYD'
    obt.mod_var_name  = 'psi_stem_avg'
    obt.plt_name      = 'psi_stem_avg_2018'
    obt.dt_begin = pd.to_datetime("01-04-2018")
    obt.dt_end = pd.to_datetime("30-11-2018")
    obt.ylab = r"$\psi_\mathrm{stem}$ [$\mathrm{MPa}$]"
    obt.fig = plt.figure(figsize=(16, 12))
    obt.ylim = [-4.5, 0.0]
    setups.append(obt)

    obt = OutputBenchType()
    obt.mod_var_cat   = 'PHYD'
    obt.mod_var_name  = 'psi_stem_avg'
    obt.plt_name      = 'psi_stem_avg_2020'
    obt.ylab = r"$\psi_\mathrm{stem}$ [$\mathrm{MPa}$]"
    obt.dt_begin = pd.to_datetime("01-04-2020")
    obt.dt_end = pd.to_datetime("30-11-2020")
    obt.ylim = [-4.5, 0.0]
    obt.fig = plt.figure(figsize=(16, 12))
    setups.append(obt)


    obt = OutputBenchType()
    obt.mod_var_cat   = 'PHYD'
    obt.mod_var_name  = 'psi_stem_avg'
    obt.plt_name      = 'psi_stem_avg_2023'
    obt.ylab = r"$\psi_\mathrm{stem}$ [$\mathrm{MPa}$]"
    obt.dt_begin = pd.to_datetime("01-04-2023")
    obt.dt_end = pd.to_datetime("30-11-2023")
    obt.fig = plt.figure(figsize=(16, 12))
    obt.ylim = [-4.5, 0.0]
    setups.append(obt)

    obt = OutputBenchType()
    obt.mod_var_cat   = 'PHYD'
    obt.mod_var_name  = 'psi_stem_avg'
    obt.plt_name      = 'psi_stem_avg_2017-2023'
    obt.ylab = r"$\psi_\mathrm{stem}$ [$\mathrm{MPa}$]"
    obt.dt_begin = pd.to_datetime("01-01-2017")
    obt.dt_end = pd.to_datetime("31-12-2023")
    obt.fig = plt.figure(figsize=(16, 12))
    obt.ylim = [-4.5, 0.0]
    setups.append(obt)


    obt = OutputBenchType()
    obt.mod_var_cat   = 'PHYD'
    obt.ylab = r"$\psi_\mathrm{leaf}$ [$\mathrm{MPa}$]"
    obt.mod_var_name  = 'psi_leaf_avg'
    obt.plt_name      = 'psi_leaf_avg_2017-2023'
    obt.dt_begin = pd.to_datetime("01-01-2017")
    obt.dt_end = pd.to_datetime("31-12-2023")
    obt.fig = plt.figure(figsize=(16, 12))
    obt.ylim = [-4.5, 0.0]
    setups.append(obt)


    obt = OutputBenchType()
    obt.mod_var_cat   = 'PHYD'
    obt.mod_var_name  = 'psi_stem_avg'
    obt.plt_name      = 'psi_stem_avg_s_2023'
    obt.ylab = r"$\psi_\mathrm{stem}$ [$\mathrm{MPa}$]"
    obt.dt_begin = pd.to_datetime("01-01-2023")
    obt.dt_end = pd.to_datetime("31-12-2023")
    obt.fig = plt.figure(figsize=(16, 12))
    #obt.ylim = [-4.5, 0.0]
    setups.append(obt)


    obt = OutputBenchType()
    obt.mod_var_cat   = 'PHYD'
    obt.mod_var_name  = 'psi_stem_avg'
    obt.plt_name      = 'psi_stem_avg_s_2018'
    obt.ylab = r"$\psi_\mathrm{stem}$ [$\mathrm{MPa}$]"
    obt.dt_begin = pd.to_datetime("01-01-2018")
    obt.dt_end = pd.to_datetime("31-12-2018")
    obt.fig = plt.figure(figsize=(16, 12))
    #obt.ylim = [-4.5, 0.0]
    setups.append(obt)

    obt = OutputBenchType()
    obt.mod_var_cat   = 'PHYD'
    obt.mod_var_name  = 'psi_stem_avg'
    obt.plt_name      = 'psi_stem_avg_s_2017'
    obt.ylab = r"$\psi_\mathrm{stem}$ [$\mathrm{MPa}$]"
    obt.dt_begin = pd.to_datetime("01-01-2017")
    obt.dt_end = pd.to_datetime("31-12-2017")
    obt.fig = plt.figure(figsize=(16, 12))
    #obt.ylim = [-4.5, 0.0]
    setups.append(obt)


    obt = OutputBenchType()
    obt.mod_var_cat   = 'PHYD'
    obt.mod_var_name  = 'psi_stem_avg'
    obt.plt_name      = 'psi_stem_avg_s_2003'
    obt.ylab = r"$\psi_\mathrm{stem}$ [$\mathrm{MPa}$]"
    obt.dt_begin = pd.to_datetime("01-01-2003")
    obt.dt_end = pd.to_datetime("31-12-2003")
    obt.fig = plt.figure(figsize=(16, 12))
    #obt.ylim = [-4.5, 0.0]
    setups.append(obt)

    obt = OutputBenchType()
    obt.mod_var_cat   = 'PHYD'
    obt.mod_var_name  = 'psi_stem_avg'
    obt.ylab = r"$\psi_\mathrm{stem}$ [$\mathrm{MPa}$]"
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
    obt.ylab = r"[$\mathrm{mm}$ $\mathrm{s}^{-1}$]"

    obt.df_obs        = df22fnet
    obt.fig = plt.figure(figsize=(16, 12))
    setups.append(obt)

    obt = OutputBenchType()
    obt.mod_var_cat   = 'Q_ASSIMI'
    obt.mod_var_name  = 'gc_avg'
    obt.ylab = r"$\mathrm{mol \ m^{-2}\  s^{-1}}$"
    obt.fig = plt.figure(figsize=(16, 12))
    setups.append(obt)

    obt = OutputBenchType()
    obt.mod_var_cat   = 'Q_ASSIMI'
    obt.mod_var_name  = 'gc_avg'
    obt.plt_name      = 'gc_avg_2018'
    obt.ylab = r"$\mathrm{mol \ m^{-2}\  s^{-1}}$"
    obt.dt_begin = pd.to_datetime("01-04-2018")
    obt.dt_end = pd.to_datetime("30-11-2018")
    obt.fig = plt.figure(figsize=(16, 12))
    setups.append(obt)
    return setups

mcols = ['tab:red', 'orange']
cat_errors = ['1', '2']
fidss  =  [[0,11629,
 5352,
 26627,
 4959,
 31121,
 21025,
 13113,
 20714,
 32095,
 4430,
 20836,
 16140,
 11336,
 8867,
 10776,
 5557,
 18098,
 13624,
 23388,
 1042], 
           
           [0,30470,
 19641,
 22630,
 18821,
 640,
 26079,
 3884,
 26541,
 31023,
 12147,
 15855,
 2403,
 3074,
 11062,
 32123,
 8867,
 14120,
 2026,
 30155,
 18956,
 29221,
 9134,
 27551,
 25061,
 6173]]

for ci in range(0, 2):         
    setups = init_setups() 
      
    ax_ax_list = []
    for setup in setups:
        axs = []
        i = 1
        for reduc_type in list(Time_Reduction_Type):    
            axs.append(setup.fig.add_subplot(3, 3, i))
            i += 1
        ax_ax_list.append(axs)

    mcol = mcols[ci]
    cat_error = cat_errors[ci]
    fids  =  fidss[ci] 

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
                                                
                        
        
            
            if fid == 0:                
                setup.df_std = df 
            
                
                # ax.plot(df[var_name_mod],c = 'tab:blue', alpha = 0.75, label = 'Q-std')                
                # if var_name_obs is not None:                                                                                                  
                #         ax.plot(df[var_name_obs], c = 'black', label = 'F')                      
                                
            else:
                
                df['fid'] = fid
                
                if setup.df_mod.empty:                
                    setup.df_mod = df[['fid',var_name_mod]].copy(deep=True)
                else:
                    setup.df_mod = pd.concat([setup.df_mod,df[['fid',var_name_mod]]], axis = 0).copy(deep=True)
                
                #ax.plot(df[var_name_mod], c = 'tab:red', alpha = 0.75)
                
            
            i += 1

        
        print(fid)
        
    for setup in setups:
        var_name_mod = setup.mod_var_name    
        setup.df_mod_50 = setup.df_mod.groupby(setup.df_mod.index).median()
        setup.df_mod_25 = setup.df_mod.groupby(setup.df_mod.index).quantile(q = 0.1)
        setup.df_mod_75 = setup.df_mod.groupby(setup.df_mod.index).quantile(q = 0.9)
    os.makedirs(os.path.join(post_dir, "egu"), exist_ok=True)   
        
    for setup in setups:  
        i = 1

        for reduc_type in list(Time_Reduction_Type): 
            cat = setup.mod_var_cat
            var_name_mod = setup.mod_var_name
            var_name_obs = setup.obs_var_name 
            setup.fig = plt.figure(figsize=(7, 5))
            ax = setup.fig.add_subplot(1,1,1)
            
            df_std = rescale(df = setup.df_std, time_reduction= reduc_type)        
            df_mod25 = rescale(df = setup.df_mod_25, time_reduction= reduc_type)      
            df_mod50 = rescale(df = setup.df_mod_50, time_reduction= reduc_type) 
            df_mod75 = rescale(df = setup.df_mod_75, time_reduction= reduc_type)       
                
            
            
            if setup.normalized:
                df_mod50[var_name_mod] = df_mod50[var_name_mod]/np.max(df_mod50[var_name_mod])
                df_mod25[var_name_mod] = df_mod25[var_name_mod]/np.max(df_mod25[var_name_mod])
                df_mod75[var_name_mod] = df_mod75[var_name_mod]/np.max(df_mod75[var_name_mod])
                
            
            ax.plot(df_std[var_name_mod],c = 'tab:blue', alpha = 1.0, label = 'Q-std')
                            
            if var_name_obs is not None:
                df_obs = setup.df_obs          
                
                if setup.dt_begin is not None:                                            
                    df_obs = df_obs[df_obs.index >= setup.dt_begin]
            
                if setup.dt_end is not None:                            
                    df_obs = df_obs[df_obs.index <= setup.dt_end]

                df_obs = rescale(df = df_obs, time_reduction= reduc_type)      
                if setup.normalized:   
                    df_obs[var_name_obs]  = df_obs[var_name_obs] /np.max(df_obs[var_name_obs] )                                                                                                                                                       
                ax.plot(df_obs[var_name_obs], c = 'black', label = 'F') 
                


            ax.plot(df_mod50[var_name_mod],c = mcol, alpha = 1.0)
            ax.fill_between(df_mod25.index, df_mod25[var_name_mod], df_mod75[var_name_mod],color = mcol, alpha = 0.25)                    

            ax.tick_params(axis='x', labelrotation=45) 
            ax.set_title(var_name_mod) 
            
            if setup.ylim is not None:
                ax.set_ylim(setup.ylim)
                
            if setup.ylab is not None:
                ax.set_ylabel(setup.ylab)
            
            if setup.plt_name ==  None:   
                setup.fig.savefig(os.path.join(post_dir, "egu", f"EGU_{cat_error}_sel_{setup.mod_var_name}_{reduc_type.name}.png"), bbox_inches='tight', dpi = 150)
            else:
                setup.fig.savefig(os.path.join(post_dir, "egu", f"EGU_{cat_error}_sel_{setup.plt_name}_{reduc_type.name}.png"), bbox_inches='tight', dpi = 150)
            i += 1        
                    


# for setup in setups:
#     if setup.plt_name ==  None:       
#         setup.fig.savefig(os.path.join(post_dir, "egu", f"EGU_{cat_error}_sel_{setup.mod_var_name}.png"), bbox_inches='tight', dpi = 150)
#     else: 
#         setup.fig.savefig(os.path.join(post_dir, "egu", f"EGU_{cat_error}_sel_{setup.plt_name}.png"), bbox_inches='tight', dpi = 150)


# %%


# %%


