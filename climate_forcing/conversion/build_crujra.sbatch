#!/bin/bash
#SBATCH --job-name=crujra
#SBATCH --partition=small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-crujra-%x-%A_%a.log

# CRU-JRA v2.5 forcing, in stages (STAGE env var):
#   STAGE=wind   array over years 1901-2023: monthly wind speed from 6-hourly u/v
#   STAGE=merge  QUINCY-named monthly files (needs all wind years)
#   STAGE=store  global QUINCY forcing store (NetCDF + Zarr)
# e.g.  w=$(STAGE=wind sbatch --parsable --array=1901-2023%10 build_crujra.sbatch)
#       m=$(STAGE=merge sbatch --parsable -d afterok:$w --mem=48G build_crujra.sbatch)
#       s=$(STAGE=store sbatch --parsable -d afterok:$m -p big --mem=96G --time=24:00:00 build_crujra.sbatch)

set -euo pipefail
REPO=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3
OUT=/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/global_forcing

case "${STAGE:?set STAGE=wind|merge|store}" in
  wind)  cd "$REPO/climate_forcing/conversion"; "$PY" -W ignore build_crujra_monthly.py wind "$SLURM_ARRAY_TASK_ID" ;;
  merge) cd "$REPO/climate_forcing/conversion"; "$PY" -W ignore build_crujra_monthly.py merge ;;
  store) cd "$REPO"; "$PY" -m src.forcing.build_global_forcing_crujra --year-min 1901 --output "$OUT/crujra_global_forcing_0.5deg_1901-2023.nc" ;;
esac
