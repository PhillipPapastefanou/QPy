import numpy as np
import os
import pandas as pd
import matplotlib.pyplot as plt
import sys
from time import perf_counter
from time import sleep

from mpi4py import MPI

sys.path.append("/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy")

from src.postprocessing.qnc_defintions import Time_Reduction_Type
from src.postprocessing.qnc_output_parser import QNC_output_parser
from src.postprocessing.qnc_ncdf_reader import QNC_ncdf_reader
from src.postprocessing.qnc_rescaler import QNC_Rescaler
from src.postprocessing.qnc_obs_reader import QNC_obs_reader
from science.phillip.bench.post_process_aggregate import aggregate
    
OUTPUT_DIR = '/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/11_transient_latin_hypercube_with_std_HAINICH_data'
OUTPUT_DIR = '/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/26_transient_latin_hypercube_with_std_HAINICH_data_full_2024_rs_work_high_gammastem'
post_dir = os.path.join(OUTPUT_DIR, 'post')
rtobspath = '/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed'

df22fnet = pd.read_csv(os.path.join(rtobspath, "Fluxnet2000_2021_eval.csv"),  index_col=0, parse_dates=True)
df22fnet['LE'] = - df22fnet['LE']
df24fnet = pd.read_csv(os.path.join(rtobspath, "Fluxnet2023_2024_eval.csv"),  index_col=0, parse_dates=True)
df24fnet['LE'] = - df24fnet['LE']

df_psi_stem_obs = pd.read_csv(os.path.join(rtobspath, "PsiStem2023.csv"),  index_col=0, parse_dates=True)
df_sap_flow_obs = pd.read_csv(os.path.join(rtobspath, "Sapflow2023.csv"),  index_col=0, parse_dates=True)
df_sap_flow_obs.loc[df_sap_flow_obs['J0.5'] < 0.0, 'J0.5'] = 0.0

def rmse(predictions, targets):
    return np.sqrt(((predictions - targets) ** 2).mean())       

def calc_rmse(df_slice_mod, var_mod, df_slice_obs, var_obs, normalized = False):    
    dfm = pd.merge(df_slice_mod[var_mod], df_slice_obs[var_obs], left_index=True, right_index=True, how='inner')    
    if normalized:
        dfm[var_mod] = dfm[var_mod]/np.max(dfm[var_mod])
        dfm[var_obs] = dfm[var_obs]/np.max(dfm[var_obs])        
    return rmse(dfm[var_mod], dfm[var_obs])

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

# Initialize
nsims_total = None
nsims_local = None

if rank == 0:   
    os.makedirs(post_dir, exist_ok=True)
    
    nsims_total = 0
    for item in os.listdir(os.path.join(OUTPUT_DIR, "output")):
        item_path = os.path.join(OUTPUT_DIR, "output", item)
        if os.path.isdir(item_path):
            nsims_total += 1
            
# Broadcast the number the total number of simulations
nsims_total = comm.bcast(nsims_total, root=0)


# Calculate the distribution
chunk_size = nsims_total // size
remainder = nsims_total % size

sendcounts = np.array([chunk_size] * size, dtype=int)
sendcounts[:remainder] += 1

displs = np.zeros(size, dtype=int)
displs[1:] = np.cumsum(sendcounts[:-1])

# Create the full data array on rank 0
if rank == 0:
    data = np.arange(nsims_total)
else:
    data = None   
        

# Determine the local receive buffer size
recvcount = sendcounts[rank]

# Allocate the receive buffer
local_data = np.zeros(recvcount, dtype=np.int64)

# Scatter the data
comm.Scatterv([data, sendcounts, displs, MPI.LONG_LONG], [local_data, recvcount, MPI.LONG_LONG], root=0)

# Print the local data for each process
print(f"Rank {rank}: Local data = {local_data}")

df_rmse = pd.DataFrame(columns= ['fid', 'rmse_psi_stem', 'rmse_psi_stem_norm', 'rmse_gpp_22', 'rmse_gpp_24', 'rmse_le_22', 'rmse_le_24', 'rmse_sapflow_norm', 'slope_gpp17-19'])

t1 = perf_counter()

run_id = 1
for fid in local_data:
    parser = QNC_output_parser(os.path.join(OUTPUT_DIR, 'output', str(fid)))
    parser.Read()
    output = parser.Available_outputs['fluxnetdata']
    nc_out_reader = QNC_ncdf_reader(os.path.join(OUTPUT_DIR, 'output', str(fid)),
                                            output.Categories,
                                            output.Identifier,
                                            output.Time_resolution
                                            )
    nc_out_reader.Parse_env_and_variables()

    cat = 'Q_ASSIMI'
    var_mod = 'gpp_avg'
    df_gpp = nc_out_reader.Read_1D_flat(cat, var_mod)
    df_gpp.set_index('date', inplace=True)
    df_gpp.drop('index', axis = 1, inplace=True)

    cat = 'SPQ'
    var_mod = 'qle_avg'
    df_le = nc_out_reader.Read_1D_flat(cat, var_mod)
    df_le.set_index('date', inplace=True)
    df_le.drop('index', axis = 1, inplace=True)

    cat = 'PHYD'
    var_mod = 'psi_stem_avg'
    df_psi_stem_mod = nc_out_reader.Read_1D_flat(cat, var_mod)
    df_psi_stem_mod.set_index('date', inplace=True)
    df_psi_stem_mod.drop('index', axis = 1, inplace=True)

    cat = 'PHYD'
    var_mod = 'G_avg'
    df_G_mod = nc_out_reader.Read_1D_flat(cat, var_mod)
    df_G_mod.set_index('date', inplace=True)
    df_G_mod.drop('index', axis = 1, inplace=True)
    
    nc_out_reader.Close()

    rmse_psi_stem = calc_rmse(df_psi_stem_mod,'psi_stem_avg', df_psi_stem_obs, "FAG")
    rmse_psi_stem_norm = calc_rmse(df_psi_stem_mod,'psi_stem_avg', df_psi_stem_obs, "FAG", normalized=True)
    rmse_gpp_22 = calc_rmse(df_gpp, 'gpp_avg', df22fnet, 'GPP')
    rmse_gpp_24 = calc_rmse(df_gpp, 'gpp_avg', df24fnet, 'GPP')
    rmse_le_22  = calc_rmse(df_le, 'qle_avg', df22fnet, 'LE')
    rmse_le_24  = calc_rmse(df_le, 'qle_avg', df24fnet, 'LE')
    rmse_sapflow_norm = calc_rmse(df_G_mod,'G_avg', df_sap_flow_obs, "J0.5", normalized=True)
    
    mean17 = df_gpp[df_gpp.index.year == 2017]['gpp_avg'].mean()
    mean19 = df_gpp[df_gpp.index.year == 2019]['gpp_avg'].mean()
    
    #print(f"{mean17} {mean19}")
    diff19_17 = mean19 - mean17
    

    df_rmse.loc[len(df_rmse)] = [fid, rmse_psi_stem, rmse_psi_stem_norm, rmse_gpp_22, rmse_gpp_24, rmse_le_22, rmse_le_24, rmse_sapflow_norm, diff19_17]
    elapsed = perf_counter()
    print(f"Rank {rank} completed {run_id} out of {local_data.shape[0]}. Elapsed: {np.round(elapsed-t1,1)}s.")
    run_id += 1

df_rmse.to_csv(os.path.join(post_dir, f"standard_ranking.csv{rank}"), index= False)

# Wait for all processes to be finished
comm.Barrier()
sleep(5)
if rank == 0:
    aggregate(OUTPUT_DIR)
