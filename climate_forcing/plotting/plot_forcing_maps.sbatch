#!/bin/bash
#SBATCH --job-name=forcing_maps
#SBATCH --partition=small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --array=0-132%10
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-maps-%A_%a.log

# One array task per file of `plot_forcing_maps.py --list` (check the count
# there and adjust --array when files are added). %10 throttle keeps the
# shared filesystem load moderate.

set -euo pipefail
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3
cd /Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/plotting
"$PY" -W ignore plot_forcing_maps.py --index "$SLURM_ARRAY_TASK_ID"
