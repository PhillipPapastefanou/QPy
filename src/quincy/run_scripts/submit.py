
import os

def GenerateSlurmScript(ntasks, path, ram_in_gb = 300, nnodes = 1, partition = 'work'):  
    
      
    script_content = f"""#!/bin/bash
#SBATCH -J QUINCY_QPY
#SBATCH --error=%j.err
#SBATCH --output=%j.log
#SBATCH -D ./
#SBATCH --get-user-env
#SBATCH --export=NONE
#SBATCH --time=72:00:00
#SBATCH --nodes={nnodes}
#SBATCH --ntasks={ntasks}
#SBATCH --partition='{partition}'
#SBATCH --mem='{ram_in_gb}G'

module purge
#module -q load gnu12 
#module -q load openmpi4 netcdf
ml gnu12/12.2.0 mpich/3.4.3-ofi
ml netcdf/4.9.0

ml all/Miniconda3

source ~/.bash_profile
echo "QUINCY path: $QUINCY"

#source /User/homes/ppapastefanou/miniconda3/etc/profile.d/conda.sh
#conda activate /Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich
# which python

export FI_PROVIDER=tcp

mpirun -n {ntasks} /Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python run_mpi.py
"""
    
    with open(os.path.join(path, 'submit.sh'), 'w') as f:
        f.write(script_content)


