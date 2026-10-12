#!/bin/bash
#SBATCH --job-name=crujra_compress
#SBATCH --partition=small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=06:00:00
#SBATCH --array=0-19
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-crujra-compress-%A_%a.log

# Compress the raw CRU-JRA files in place (netCDF-3 -> netCDF-4 zlib, lossless,
# each file verified before it replaces the original): one array task per
# version/variable folder of driver_data/crujra/raw/. Reruns skip finished files.
#   sbatch compress_crujra_raw.sbatch

set -euo pipefail
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3
cd /Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/conversion
FOLDERS=()
for v in v2.5 v3.0; do
    for var in dlwrf dswrf pre pres spfh tmax tmin tmp ugrd vgrd; do FOLDERS+=("$v/$var"); done
done
"$PY" compress_crujra_raw.py "${FOLDERS[$SLURM_ARRAY_TASK_ID]}"
