import os
import glob
import numpy as np
import pandas as pd
import xarray as xr
from datetime import datetime
from mpi4py import MPI
from dataclasses import dataclass

# ==========================================
# Data Structures
# ==========================================
@dataclass
class HainichObs:
    df_fnet_22: pd.DataFrame
    df_fnet_24: pd.DataFrame
    df_psi_stem_obs: pd.DataFrame
    df_psi_leaf_obs: pd.DataFrame
    df_sap_flow_2023: pd.DataFrame

# ==========================================
# Initialization & Observations
# ==========================================
def init_hainich_obs():
    rtobspath = "/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed"

    df_fnet_22 = pd.read_csv(os.path.join(rtobspath, "Fluxnet2000_2021_eval.csv"), parse_dates=['time'])
    df_fnet_22.rename(columns={'time': 'DateTime'}, inplace=True)
    df_fnet_22.dropna(inplace=True)

    df_fnet_24 = pd.read_csv(os.path.join(rtobspath, "Fluxnet2023_2024_eval.csv"), parse_dates=['date'])
    df_fnet_24.rename(columns={'date': 'DateTime'}, inplace=True)

    df_psi_stem = pd.read_csv(os.path.join(rtobspath, "PsiStem2023.csv"), parse_dates=['date'])
    df_psi_stem.rename(columns={'date': 'DateTime'}, inplace=True)

    df_sap_flow = pd.read_csv(os.path.join(rtobspath, "Sapflow2023.csv"), parse_dates=['date'])
    df_sap_flow.rename(columns={'date': 'DateTime'}, inplace=True)

    df_psi_leaf = pd.read_csv(os.path.join(rtobspath, "psi_leaf_midday_2023_2024_avg.csv"), parse_dates=['date'])
    df_psi_leaf.rename(columns={'date': 'DateTime'}, inplace=True)

    df_sap_flow = df_sap_flow.dropna(subset=['J0.5'])
    df_sap_flow['J0.5'] = df_sap_flow['J0.5'].astype(float)
    df_sap_flow.loc[df_sap_flow['J0.5'] < 0.0, 'J0.5'] = 0.0

    return HainichObs(df_fnet_22, df_fnet_24, df_psi_stem, df_psi_leaf, df_sap_flow)

# ==========================================
# Data Slicing and Mapping Helpers
# ==========================================
def slice_obs(df, varname, d1, d2):
    """Slices the pandas observation dataframe by date and extracts the target variable."""
    mask = (df['DateTime'] >= d1) & (df['DateTime'] < d2)
    sliced = df.loc[mask, ['DateTime', varname]].copy()
    sliced.rename(columns={varname: 'mean_1'}, inplace=True) 
    return sliced

def build_var_map(folder_path, sim_type="fluxnetdata"):
    """
    Scans all NetCDF files containing the sim_type (e.g., fluxnetdata) in their name.
    Returns a dictionary mapping {variable_name: file_path}
    """
    search_pattern = os.path.join(folder_path, f"*{sim_type}*.nc")
    matching_files = glob.glob(search_pattern)
    
    if not matching_files:
        return {}

    var_map = {}
    for file_path in matching_files:
        try:
            with xr.open_dataset(file_path) as ds:
                for var in ds.data_vars:
                    var_map[var] = file_path
        except Exception as e:
            pass # Silently skip unreadable files to prevent clutter
            
    return var_map

def get_model_slice(var_map, varname, d1, d2):
    """
    Looks up the file for the variable, slices it by time natively using xarray, 
    and returns a clean pandas DataFrame with standard datetime objects.
    """
    if varname not in var_map:
        raise KeyError(f"Variable '{varname}' not found in mapped NetCDF files.")
        
    file_path = var_map[varname]
    
    with xr.open_dataset(file_path) as ds:
        d1_str = d1.strftime('%Y-%m-%d')
        d2_str = d2.strftime('%Y-%m-%d')
        sliced_ds = ds[varname].sel(time=slice(d1_str, d2_str)).to_dataframe().reset_index()
        
    sliced_ds.rename(columns={'time': 'DateTime', varname: 'mean'}, inplace=True)
    sliced_ds['DateTime'] = pd.to_datetime(sliced_ds['DateTime'].astype(str))
    
    return sliced_ds

# ==========================================
# Main MPI Execution
# ==========================================
def calculate_mod_obs_rmse_2023_mpi(quincy_output, hainich_obs):
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    world_size = comm.Get_size()

    if rank == 0:
        print(f"--- Starting Python MPI Job with {world_size} processes ---", flush=True)

    date_ranges = [
        ("23",   datetime(2023, 5, 1),  datetime(2023, 10, 30)),
        ("full", datetime(2000, 1, 1),  datetime(2024, 12, 31)),
        ("03",   datetime(2003, 5, 1),  datetime(2003, 10, 30)),
        ("18",   datetime(2018, 5, 1),  datetime(2018, 10, 30))
    ]

    post_process_dir = os.path.join(quincy_output, "post2")
    if rank == 0:
        os.makedirs(post_process_dir, exist_ok=True)
    comm.Barrier() 

    output_dir = os.path.join(quincy_output, "output")
    full_dir_paths = [f.path for f in os.scandir(output_dir) if f.is_dir()]
    short_dir_paths = [os.path.basename(p) for p in full_dir_paths]
    
    # Divide the work among ranks
    my_dirs = list(zip(full_dir_paths, short_dir_paths))[rank::world_size]
    print(f"Rank {rank:02d} reporting for duty! I have {len(my_dirs)} directories to process.", flush=True)

    df_param = pd.read_csv(os.path.join(quincy_output, "parameters.csv"))

    # 1. Initialize ALL NaN columns in the DataFrame upfront
    prefixes = ["gpp", "le", "psi_stem", "psi_leaf"]
    flow_prefixes = ["stem_flow", "G"]
    multipliers = [(1.0, ""), (0.5, "_05"), (0.25, "_025"), (2.0, "_2")]
    
    for ystr, _, _ in date_ranges:
        for p in prefixes:
            df_param[f"{p}_rmse_{ystr}"] = np.nan
        for p in flow_prefixes:
            for _, m in multipliers:
                df_param[f"{p}_rmse{m}_{ystr}"] = np.nan

    # 2. Pre-slice Observations for ALL Eras
    if rank == 0:
        print("Pre-slicing observation data...", flush=True)
        
    obs_by_era = {}
    for ystr, d1, d2 in date_ranges:
        df_fnet = hainich_obs.df_fnet_22 if d1.year < 2022 else hainich_obs.df_fnet_24
        obs_by_era[ystr] = {
            'gpp': slice_obs(df_fnet, "GPP", d1, d2),
            'le': slice_obs(df_fnet, "LE", d1, d2),
            'psi_stem': slice_obs(hainich_obs.df_psi_stem_obs, "FAG", d1, d2),
            'sapflow': slice_obs(hainich_obs.df_sap_flow_2023, "J0.5", datetime(2023, 6, 1), datetime(2023, 8, 1)),
            'psi_leaf': slice_obs(hainich_obs.df_psi_leaf_obs, "psi_leaf_midday_avg", d1, d2)
        }

    # 3. Process assigned directories (Directory First -> Eras Second)
    total_my_dirs = len(my_dirs)
    
    for i, (full_dir, short_dir) in enumerate(my_dirs, start=1):
        
        # Build the map ONLY ONCE per directory
        var_map = build_var_map(full_dir, "fluxnetdata")
        
        if not var_map:
            continue # Skip if no files were mapped

        idx = df_param.index[df_param['fid'] == int(short_dir)]

        # Now process all 4 date ranges for this specific directory
        for ystr, d1, d2 in date_ranges:
            obs_dict = obs_by_era[ystr]
            
            standard_vars = [
                {'mod_var': 'gpp_avg',      'obs_df': obs_dict['gpp'],      'prefix': 'gpp',      'scale': 1.0, 'use_abs': False},
                {'mod_var': 'qle_avg',      'obs_df': obs_dict['le'],       'prefix': 'le',       'scale': 1.0, 'use_abs': True},
                {'mod_var': 'psi_stem_avg', 'obs_df': obs_dict['psi_stem'], 'prefix': 'psi_stem', 'scale': 1.0, 'use_abs': False},
                {'mod_var': 'psi_leaf_avg', 'obs_df': obs_dict['psi_leaf'], 'prefix': 'psi_leaf', 'scale': 1.0, 'use_abs': False}
            ]
            flow_vars = [
                {'mod_var': 'stem_flow_per_sap_area_avg', 'obs_df': obs_dict['sapflow'], 'prefix': 'stem_flow', 'scale': 1000.0},
                {'mod_var': 'G_per_sap_area_avg',         'obs_df': obs_dict['sapflow'], 'prefix': 'G',         'scale': 1000.0}
            ]

            for v in standard_vars:
                try:
                    df_mod = get_model_slice(var_map, v['mod_var'], d1, d2)
                    df_join = pd.merge(df_mod, v['obs_df'], on='DateTime', how='inner')
                    
                    if v['use_abs']:
                        rmse = np.sqrt(np.mean((np.abs(df_join['mean'] * v['scale']) - np.abs(df_join['mean_1']))**2))
                    else:
                        rmse = np.sqrt(np.mean((df_join['mean'] * v['scale'] - df_join['mean_1'])**2))
                    
                    df_param.loc[idx, f"{v['prefix']}_rmse_{ystr}"] = rmse
                except Exception as e:
                    # Do not use exit() in MPI, or it will deadlock the cluster!
                    pass 

            for v in flow_vars:
                try:
                    df_mod = get_model_slice(var_map, v['mod_var'], d1, d2)
                    df_join = pd.merge(df_mod, v['obs_df'], on='DateTime', how='inner')
                    
                    for mult, suffix in multipliers:
                        rmse = np.sqrt(np.mean((mult * df_join['mean'] * v['scale'] - df_join['mean_1'])**2))
                        df_param.loc[idx, f"{v['prefix']}_rmse{suffix}_{ystr}"] = rmse
                except Exception as e:
                    pass
        
        # Print progress only once per directory
        print(f"Rank {rank:02d} progress: {i}/{total_my_dirs} directories processed.", flush=True)

    # 4. Save a rank-specific temporary CSV file
    rank_file = os.path.join(post_process_dir, f"params_rmse_2023_rank{rank}.csv")
    df_param.to_csv(rank_file, index=False)
    
    comm.Barrier() 

    # 5. Rank 0 merges the files together
    if rank == 0:
        print("All ranks finished! Rank 0 is stitching the results together...", flush=True)
        final_df = df_param.copy()
        
        for r in range(world_size):
            temp_file = os.path.join(post_process_dir, f"params_rmse_2023_rank{r}.csv")
            if os.path.exists(temp_file):
                temp_df = pd.read_csv(temp_file)
                
                for col in final_df.columns:
                    if col != "fid":
                        mask = temp_df[col].notna()
                        final_df.loc[mask, col] = temp_df.loc[mask, col]
                        
                os.remove(temp_file) 
            
        final_out = os.path.join(post_process_dir, "params_rmse_2023.csv")
        final_df.to_csv(final_out, index=False)
        print("Successfully wrote final params_rmse_2023.csv!", flush=True)


if __name__ == "__main__":
    target_dir = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/2023_bench/57_run_transient_g1_low_gamma_leaf" 
    obs_data = init_hainich_obs()
    calculate_mod_obs_rmse_2023_mpi(target_dir, obs_data)