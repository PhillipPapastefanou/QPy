#!/bin/bash
#SBATCH --job-name=gldas_coarsen
#SBATCH --partition=big
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-gldas-coarsen-%j.log

# Coarsens download_gldas.py's 2018-2025 daily_0.25deg product
# (t_air/q_air/press_srf/wind_air/swvis_srf_down/lw_srf_down/rain/snow) to
# 0.5deg, matching the resolution ERA5/CRU-JRA/TerraClimate's final products
# already share (see coarsen_gldas_daily_to_0.5deg.py's docstring for why
# this was the one GLDAS product still stuck at native resolution). Runs
# under Slurm for the same reason as the sibling era5/gldas jobs: this
# session's interactive process has repeatedly torn down mid-run.
#
# Resumable per-variable: process() skips any variable whose output file
# already exists, so a restart after an interruption only redoes the
# variable that was in flight.

set -euo pipefail

REPO=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/conversion
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3

cd "$REPO"
"$PY" coarsen_gldas_daily_to_0.5deg.py
