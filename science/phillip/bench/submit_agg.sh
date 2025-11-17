#!/bin/bash
#SBATCH -J QUINCY_QPY
#SBATCH --error=%j.err
#SBATCH --output=%j.log
#SBATCH -D ./
#SBATCH --get-user-env
#SBATCH --export=NONE
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=16
#SBATCH --partition='work'
#SBATCH --mem='300'

ml purge 
ml intel/2023.0.0  impi/2021.6.0
ml netcdf/4.9.0
ml all/Miniconda3

source ~/.bash_profile
echo "QUINCY path: $QUINCY"

source /User/homes/ppapastefanou/miniconda3/etc/profile.d/conda.sh
conda activate /Net/Groups/BSI/work_scratch/ppapastefanou/envs/SimPHony_intel_mpich
which python

#export FI_PROVIDER=tcp

mpirun -n 16 python -u post_process_complete_parallel.py