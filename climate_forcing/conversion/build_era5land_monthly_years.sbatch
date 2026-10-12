#!/bin/bash
#SBATCH --job-name=e5l_monthly
#SBATCH --partition=work
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=24G
#SBATCH --time=12:00:00
#SBATCH --array=1950-2024%15
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-e5l-monthly-%A_%a.log

# Stage 1 of the ERA5-Land monthly forcing (see build_era5land_monthly.py):
# one array task per year, daily 0.1deg -> monthly 0.1/0.25/0.5deg cache
# files. %15 caps concurrent tasks so the shared archive's filesystem isn't
# hammered by 75 simultaneous ~20 GB/year readers. Resumable: a task whose
# three cache files exist returns immediately.
#
# Run a single year with: sbatch --array=2010 build_era5land_monthly_years.sbatch

set -euo pipefail
REPO=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/conversion
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

cd "$REPO"
"$PY" build_era5land_monthly.py year "$SLURM_ARRAY_TASK_ID"
