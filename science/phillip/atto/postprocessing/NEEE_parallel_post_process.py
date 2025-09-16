import pandas as pd
import xarray as xr
import numpy as np
from mpi4py import MPI
import os
import time

def rmse(y_true, y_pred):
    return np.sqrt(np.mean((y_true - y_pred) ** 2))

df_obs = pd.read_csv("/Net/Groups/BSI/work_scratch/ppapastefanou/atto_summerschool_25/data/ATTO_evaluation.csv")


comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

# ---------------- rank 0: discover work ----------------
if rank == 0:
    base_path = '/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/ATTO_example_05_hydraulics'
    base_path_output = os.path.join(base_path, "output")
    # your discovery logic (subdirs are ints)
    subdirs = [int(d) for d in os.listdir(base_path_output)
               if os.path.isdir(os.path.join(base_path_output, d))]
    subdirs.sort()

    if not subdirs:
        print("Empty output. Stopping processing")
        has_work = False
    else:
        has_work = True

    # Pack as numpy for Scatterv
    subdirs_np = np.asarray(subdirs, dtype=np.int64)
    n = subdirs_np.size

    # Build Scatterv counts/displacements (contiguous block partition)
    counts = np.array([n // size + (1 if r < (n % size) else 0) for r in range(size)], dtype=np.int32)
    displs = np.zeros(size, dtype=np.int32)
    if size > 1:
        displs[1:] = np.cumsum(counts[:-1], dtype=np.int32)
else:
    base_path_output = None
    has_work = None
    subdirs_np = None
    counts = None
    displs = None
    n = None

# ---------------- broadcast shared bits ----------------
base_path_output = comm.bcast(base_path_output, root=0)
has_work = comm.bcast(has_work, root=0)

if not has_work:
    MPI.Finalize()
    raise SystemExit()

n = comm.bcast(n, root=0)
counts = comm.bcast(counts, root=0)
displs = comm.bcast(displs, root=0)

# ---------------- scatter my chunk of subdirs ----------------
my_count = int(counts[rank])
my_subdirs = np.empty(my_count, dtype=np.int64)

# sendbuf only valid on root; use explicit MPI types for clarity
comm.Scatterv([subdirs_np, counts, displs, MPI.LONG_LONG] if rank == 0 else None,
              my_subdirs, root=0)

rmses_year_day = np.zeros(len(my_subdirs), dtype=float)
rmses_day = np.zeros(len(my_subdirs), dtype=float)

    
    
def compute_metrics_for(index, out):
    
    ds_mod_ass = xr.open_dataset(os.path.join(base_path_output, str(out),"Q_ASSIMI_fluxnetdata_timestep.nc"))
    ds_mod_veg = xr.open_dataset(os.path.join(base_path_output,str(out), "VEG_fluxnetdata_timestep.nc"))
    ds_mod_sb  = xr.open_dataset(os.path.join(base_path_output,str(out), "SB_fluxnetdata_timestep.nc"))
    
    
    df_mod = ds_mod_veg['npp_avg'].to_pandas().to_frame()
    df_mod['gpp_avg'] = ds_mod_ass['gpp_avg']
    df_mod['nee_avg'] = -(ds_mod_veg['npp_avg'] -ds_mod_sb['het_respiration_avg'] )
    
    
    df_mod['Year'] = df_mod.index.year
    df_mod['day_of_year_adj'] = df_mod.index.dayofyear
    df_mod['Hour'] = df_mod.index.hour
    df_mod['Minute'] = df_mod.index.minute
    
    
    df_merged = pd.merge(
    df_mod,
    df_obs,
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
    
    
    dfm = df_merged.groupby([df_merged.index.day_of_year, df_merged.index.year]).agg(
        nee_mean_mod=("nee_avg", "mean"),
        nee_q25_mod=("nee_avg", lambda x: x.quantile(0.25)),
        nee_median_mod=("nee_avg", "median"),
        nee_q75_mod=("nee_avg", lambda x: x.quantile(0.75)),
        
        nee_mean_obs=("NEE_U50_orig", "mean"),
        nee_q25_obs=("NEE_U50_orig", lambda x: x.quantile(0.25)),
        nee_median_obs=("NEE_U50_orig", "median"),
        nee_q75_obs=("NEE_U50_orig", lambda x: x.quantile(0.75)),
    )


    vrmse_doy_year = rmse(dfm['nee_mean_mod'], dfm['nee_mean_obs'])

    
    dfm = df_merged.groupby([df_merged.index.day_of_year]).agg(
        nee_mean_mod=("nee_avg", "mean"),
        nee_q25_mod=("nee_avg", lambda x: x.quantile(0.25)),
        nee_median_mod=("nee_avg", "median"),
        nee_q75_mod=("nee_avg", lambda x: x.quantile(0.75)),
        
        nee_mean_obs=("NEE_U50_orig", "mean"),
        nee_q25_obs=("NEE_U50_orig", lambda x: x.quantile(0.25)),
        nee_median_obs=("NEE_U50_orig", "median"),
        nee_q75_obs=("NEE_U50_orig", lambda x: x.quantile(0.75)),
    )

    vrmse_doy = rmse(dfm['nee_mean_mod'], dfm['nee_mean_obs'])
 
    end = time.time()

    elapsed = end - start
    print(f"Rank {rank} did index {out}, this is {index + 1} out of {my_count} elapsed: {np.round(elapsed, 1)}s")

    ds_mod_ass.close()
    ds_mod_sb.close()
    ds_mod_veg.close()
    
    return vrmse_doy_year, vrmse_doy


start = time.time()


local_rmses_year_day = np.full(my_count, np.nan, dtype=float)
local_rmses_day = np.full(my_count, np.nan, dtype=float)


for i in range(my_count):
    out_int = int(my_subdirs[i])
    try:
        v_year, v_day = compute_metrics_for(i, out_int)
        local_rmses_year_day[i] = v_year
        local_rmses_day[i] = v_day
    except Exception as e:
        print(f"[rank {rank}] Failed on {out_int}: {e}")
        
# ---------------- gather results back in order ----------------
if rank == 0:
    rmses_year_day = np.empty(n, dtype=float)
    rmses_day = np.empty(n, dtype=float)
else:
    rmses_year_day = None
    rmses_day = None

comm.Gatherv(local_rmses_year_day,
             [rmses_year_day, counts, displs, MPI.DOUBLE] if rank == 0 else None,
             root=0)
comm.Gatherv(local_rmses_day,
             [rmses_day, counts, displs, MPI.DOUBLE] if rank == 0 else None,
             root=0)


# ---------------- export the files ----------------

if rank == 0:
    df_param = pd.read_csv(os.path.join(base_path, "parameters.csv"))
    df_param = df_param.set_index('id').reindex(subdirs_np)
    df_param['rmse_year_doy'] = rmses_year_day
    df_param['rmse_doy'] = rmses_day
    os.makedirs(os.path.join(base_path, "post_process"),exist_ok=True)
    df_param.to_csv(os.path.join(base_path, "post_process", "parameters_best_t.csv"))
    
