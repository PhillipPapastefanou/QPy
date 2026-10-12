#!/bin/bash
#SBATCH --job-name=era5_wind
#SBATCH --partition=big
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=7-00:00:00
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-era5-wind-%j.log

# Replaces ERA5 monthly wind_air (previously |mean u10/v10|, biased low) with
# 10m_wind_speed, at native 0.25deg and at 0.5deg. Only this variable is
# requested; raw chunks are cached, so a rerun resumes. The old files were
# kept as era5_wind_air_1940-2025_monthly.nc.bak_vectormean.

set -euo pipefail
REPO=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3

cd "$REPO"
"$PY" download/download_era5_monthly.py --start-year 1940 --end-year 2025 --variables 10m_wind_speed
"$PY" download/download_era5_monthly.py --start-year 1940 --end-year 2025 --variables 10m_wind_speed --grid 0.5/0.5
