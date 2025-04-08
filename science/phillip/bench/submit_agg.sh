#!/bin/bash
#SBATCH -J QUINCY_QPY
#SBATCH --error=%j.err
#SBATCH --output=%j.log
#SBATCH -D ./
#SBATCH --get-user-env
#SBATCH --export=NONE
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=128
#SBATCH --partition='big'
#SBATCH --mem='1000G'

ml purge 
ml intel/2023.0.0  impi/2021.6.0
ml netcdf/4.9.0
ml all/Miniconda3

source ~/.bash_profile
echo "QUINCY path: $QUINCY"

source /User/homes/ppapastefanou/miniconda3/etc/profile.d/conda.sh
conda activate /Net/Groups/BSI/work_scratch/ppapastefanou/envs/SimPHony_intel_oneapi
which python

export FI_PROVIDER=tcp

mpirun -n 128 python -u post_process_complete_parallel.py