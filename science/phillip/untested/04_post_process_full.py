import os
import glob
import sys
import subprocess
import xarray as xr
import numpy as np
import pandas as pd
from time import perf_counter
import matplotlib.pyplot as plt
import datetime

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

from src.postprocessing.qnc_defintions import Output_format
from src.postprocessing.qnc_output_parser import QNC_output_parser
from src.postprocessing.qnc_ncdf_reader import QNC_ncdf_reader
from src.postprocessing.qnc_multi_fluxnet_comparer import QNC_Multi_Fluxnet_Comparer


OUTPUT_DIR = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/14_transient_latin_hypercube_with_std_HAINICH_data_full"



comparer = QNC_Multi_Fluxnet_Comparer("DE-Hai")
var_list = comparer.Generate_Default_Fluxnet_Var_List()
comparer.Set_target_list(var_list)
comparer.Parse_Obs('/Net/Groups/BSI/data/OCN/evaluation/point/FLUXNET/v2/DE-Hai.2000-2006.obs.nc')

from time import perf_counter

t1 = perf_counter()

nsims = 0
for item in os.listdir(os.path.join(OUTPUT_DIR, "output")):
    item_path = os.path.join(OUTPUT_DIR, "output", item)
    if os.path.isdir(item_path):
        nsims += 1

for fid in range(0,nsims):
    parser = QNC_output_parser(os.path.join(THIS_DIR, OUTPUT_DIR, 'output', str(fid)))
    parser.Read()
    output = parser.Available_outputs['fluxnetdata']
    nc_out_reader = QNC_ncdf_reader(os.path.join(THIS_DIR, OUTPUT_DIR, 'output', str(fid)),
                                            output.Categories,
                                            output.Identifier,
                                            output.Time_resolution
                                            )

    nc_out_reader.Parse_env_and_variables()
    
    comparer.Parse_Mod(nc_out_reader)
    nc_out_reader.Close()
    print(fid)
    
df = pd.DataFrame(comparer.list_rmse)
df.columns = [pair.name for pair in var_list.Target_variables]
df['fid'] = range(0, nsims)

t2 = perf_counter()

print(f"elapsed: {t2-t1}")
df.to_csv(os.path.join(THIS_DIR, OUTPUT_DIR, "rmsedata.csv"), index=False)