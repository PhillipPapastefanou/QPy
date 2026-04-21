import numpy as np
import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import sys
from time import perf_counter

sys.path.append("/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy")
   
OUTPUT_DIR = '/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/11_transient_latin_hypercube_with_std_HAINICH_data'
OUTPUT_DIR = '/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/20_transient_latin_hypercube_with_std_HAINICH_data_full_2024_rs_work'

def aggregate(path = OUTPUT_DIR):
    
    nsims_total = 0
    pattern = os.path.join(os.path.join(path, "post"), "*.csv[0-9]*")
    
    matching_files = glob.glob(pattern)
    
    print(f"Found {len(matching_files)} files!" )
    print("Lets go and aggregate them")


    for i in range(0, len(matching_files)):        
        if i == 0:
            df = pd.read_csv(matching_files[i])
        else:
            df_t = pd.read_csv(matching_files[i])
            df = pd.concat([df, df_t], axis = 0)
        print(i)
            
    df = df.sort_values(by='fid')
    df.to_csv(os.path.join(path, "post", "standard_ranking.csv"), index = None)
    print("Completed!")


#aggregate()