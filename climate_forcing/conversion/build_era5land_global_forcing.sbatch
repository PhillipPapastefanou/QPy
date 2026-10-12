#!/bin/bash
#SBATCH --job-name=e5l_global
#SBATCH --partition=big
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=96G
#SBATCH --time=24:00:00
#SBATCH --array=0-1
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-e5l-global-%A_%a.log

# Stage 3 of the ERA5-Land forcing: the full QUINCY global forcing store
# (met + CO2/isotopes + N/P deposition + soils + lithology + P pools) via
# src/forcing/build_global_forcing_era5land.py, one array task per
# resolution. Submit with --dependency=afterok:<merge job id>.

set -euo pipefail
REPO=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3
OUT=/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/global_forcing
RES=(0.5deg 0.25deg)
R=${RES[$SLURM_ARRAY_TASK_ID]}

cd "$REPO"
"$PY" -m src.forcing.build_global_forcing_era5land --res "$R" \
    --output "$OUT/era5land_global_forcing_${R}_1950-2024.nc"
