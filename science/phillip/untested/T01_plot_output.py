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


from src.postprocessing.qnc_defintions import Time_Reduction_Type
from src.postprocessing.qnc_output_parser import QNC_output_parser
from src.postprocessing.qnc_ncdf_reader import QNC_ncdf_reader
from src.postprocessing.qnc_rescaler import QNC_Rescaler
from src.postprocessing.qnc_obs_reader import QNC_obs_reader
    
OUTPUT_DIR = '/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/11_transient_latin_hypercube_with_std_HAINICH_data'
OUTPUT_DIR = '/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/14_transient_latin_hypercube_with_std_HAINICH_data_full'
post_dir = os.path.join(OUTPUT_DIR, 'post')
os.makedirs(post_dir, exist_ok=True)


obs_reader = QNC_obs_reader('/Net/Groups/BSI/data/OCN/evaluation/point/FLUXNET/v2/DE-Hai.2000-2006.obs.nc')
obs_reader.Parse_env_and_variables()

# df_params = pd.read_csv(os.path.join(OUTPUT_DIR, "parameters.csv"))
# df_rmse = pd.read_csv(os.path.join(OUTPUT_DIR, "rmsedata.csv"))
# df_res = pd.merge(df_params, df_rmse, on='fid')
#fids =  df_slice_good['fid'].to_list()
#fids.insert(0, 0)
# df_slice_good = df_res[ (df_res['GPP'] < 3.6)&(df_res['kappa_stem'] < 200)]
# df_slice_good
# %%
fids = np.arange(0, 4096, 16)



setups = []

d = {}
d['var_cat'] = 'Q_ASSIMI'
d['var_name_mod'] = 'gpp_avg'
d['var_name_obs'] = 'GPP'
d['var_name_obs'] = None
d['fig'] = plt.figure(figsize=(16, 12))
setups.append(d)

d = {}
d['var_cat'] = 'PHYD'
d['var_name_mod'] = 'psi_leaf_avg'
d['var_name_obs'] = None
d['fig'] = plt.figure(figsize=(16, 12))
setups.append(d)

d = {}
d['var_cat'] = 'PHYD'
d['var_name_mod'] = 'psi_stem_avg'
d['var_name_obs'] = None
d['fig'] = plt.figure(figsize=(16, 12))
setups.append(d)

d = {}
d['var_cat'] = 'VEG'
d['var_name_mod'] = 'total_veg_c'
d['var_name_obs'] = None
d['fig'] = plt.figure(figsize=(16, 12))
setups.append(d)

d = {}
d['var_cat'] = 'SPQ'
d['var_name_mod'] = 'qle_avg'
d['var_name_obs'] = None
d['fig'] = plt.figure(figsize=(16, 12))
setups.append(d)

d = {}
d['var_cat'] = 'Q_ASSIMI'
d['var_name_mod'] = 'gc_avg'
d['var_name_obs'] = None
d['fig'] = plt.figure(figsize=(16, 12))
setups.append(d)

ax_ax_list = []
for setup in setups:
    axs = []
    i = 1
    for reduc_type in list(Time_Reduction_Type):    
        axs.append(setup['fig'].add_subplot(3, 3, i))
        i += 1
    ax_ax_list.append(axs)

for fid in fids:
#for fid in [0, 96, 672]:
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

    comparer = QNC_Rescaler(nc_output, obs_reader)


    
    fig_index = 0 
    for setup in setups:
        
        axs = ax_ax_list[fig_index]              
        i = 1
        for reduc_type in list(Time_Reduction_Type):    
            ax = axs[i - 1]
            cat = setup['var_cat']
            var_name_mod = setup['var_name_mod']
            var_name_obs = setup['var_name_obs']
            df = comparer.Get_reduced_1D_dataframe(cat, var_name_mod, reduc_type, varname_obs = var_name_obs)
            
            if fid == 0:
                ax.plot(df[var_name_mod],c = 'tab:blue', alpha = 0.75, label = 'Q-std')
                if var_name_obs is not None: 
                    if var_name_obs == 'LE' :
                        ax.plot(-df[var_name_obs], c = 'black', label = 'F')
                    else:
                        ax.plot(df[var_name_obs], c = 'black', label = 'F')                        
            
                    
            else: 
                ax.plot(df[var_name_mod] ,c = 'tab:red', alpha = 0.10)
                
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
        
for setup in setups:       
    setup['fig'].savefig(os.path.join(post_dir, setup['var_name_mod']), bbox_inches='tight', dpi = 150)



# %%



  
plt.show()

# %%


