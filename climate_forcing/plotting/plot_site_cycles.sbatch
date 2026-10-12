#!/bin/bash
#SBATCH --job-name=site_cycles
#SBATCH --partition=small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --array=0-133%10
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-sites-%A_%a.log

# Tasks 0..N-1: one per file of `plot_forcing_maps.py --list`; task N: the
# cross-dataset comparison. Adjust --array to (number of files) when files are added.

set -euo pipefail
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3
cd /Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/plotting
N=$("$PY" -W ignore plot_forcing_maps.py --list | wc -l)
if [ "$SLURM_ARRAY_TASK_ID" -ge "$N" ]; then
  "$PY" -W ignore plot_site_cycles.py --compare
else
  "$PY" -W ignore plot_site_cycles.py --index "$SLURM_ARRAY_TASK_ID"
fi
