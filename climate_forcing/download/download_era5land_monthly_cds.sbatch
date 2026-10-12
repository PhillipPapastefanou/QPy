#!/bin/bash
#SBATCH --job-name=e5l_cds
#SBATCH --partition=big
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=7-00:00:00
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-e5l-cds-%j.log

# ERA5-Land monthly means from CDS (see download_era5land_monthly_cds.py):
# 2024-2025 shortwave/dewpoint/pressure first (needed to add 2025 to the
# ERA5-Land forcing; 2024 overlaps the archive-based build for a check),
# then 1950-2025 longwave. Resumable: cached raw files are skipped.

set -euo pipefail
REPO=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3

cd "$REPO"
"$PY" download/download_era5land_monthly_cds.py --start-year 2024 --end-year 2025 --chunk-years 2 \
    --variables surface_solar_radiation_downwards 2m_dewpoint_temperature surface_pressure
"$PY" download/download_era5land_monthly_cds.py --start-year 1950 --end-year 2025 --chunk-years 5 \
    --variables surface_thermal_radiation_downwards
