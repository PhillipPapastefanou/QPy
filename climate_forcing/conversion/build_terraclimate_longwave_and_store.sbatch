#!/bin/bash
#SBATCH --job-name=tc_lw_store
#SBATCH --partition=big
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=96G
#SBATCH --time=12:00:00
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-tc-lw-store-%j.log

# TerraClimate longwave (derive_terraclimate_longwave.py), then rebuild the
# 0.5deg TerraClimate QUINCY global forcing store so it carries lw_srf_down.
# The previous store (no longwave) is kept as *.bak_nolw.

set -euo pipefail
REPO=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3
OUT=/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/global_forcing
STORE=$OUT/terraclimate_global_forcing_0.5deg_1958-2025

cd "$REPO/climate_forcing/conversion"
"$PY" -W ignore derive_terraclimate_longwave.py --start-year 1958 --end-year 2025

for ext in nc zarr; do
  [ -e "$STORE.$ext" ] && mv "$STORE.$ext" "$STORE.$ext.bak_nolw"
done
cd "$REPO"
"$PY" -m src.forcing.build_global_forcing_terraclimate --output "$STORE.nc"
