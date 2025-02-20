
import os

def GenerateSlurmScript(ntasks, path):    
    script_content = f"""#!/bin/bash
#SBATCH -J QUINCY_QPY
#SBATCH --error=%j.err
#SBATCH --output=%j.log
#SBATCH -D ./
#SBATCH --get-user-env
#SBATCH --export=NONE
#SBATCH --time=24:00:00
#SBATCH --nodes=1
#SBATCH --ntasks={ntasks}
#SBATCH --partition='work'
#SBATCH --mem='64G'
module purge
module -q load gnu12 R/4.3.2
module -q load openmpi4 netcdf

ml all/Miniconda3

source ~/.bash_profile
echo "QUINCY path: $QUINCY"

source /User/homes/ppapastefanou/miniconda3/etc/profile.d/conda.sh
conda activate /Net/Groups/BSI/work_scratch/ppapastefanou/envs/phs
which python

export FI_PROVIDER=tcp

mpirun -n 4 python run_mpi.py
"""
    
    with open(os.path.join(path, 'submit.sh'), 'w') as f:
        f.write(script_content)


