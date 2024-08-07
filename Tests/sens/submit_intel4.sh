#!/bin/bash
#SBATCH -J GUESS_NCPS
#SBATCH --error=%j.err
#SBATCH --output=%j.log
#SBATCH -D ./
#SBATCH --get-user-env
#SBATCH --mail-type=ALL
#SBATCH --mail-user=papa@tum.de
#SBATCH --export=NONE
#SBATCH --time=24:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --partition='work'
#SBATCH --mem='100G'
module purge
module -q load gnu12 R/4.3.2
module -q load openmpi4 netcdf
ml all/Miniconda3


source /User/homes/ppapastefanou/miniconda3/etc/profile.d/conda.sh
conda activate /Net/Groups/BSI/work_scratch/ppapastefanou/envs/phs
which python


export FI_PROVIDER=tcp



mpirun -n 4 python run_mpi.py 
