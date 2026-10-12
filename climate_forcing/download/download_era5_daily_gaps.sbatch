#!/bin/bash
#SBATCH --job-name=era5_gaps
#SBATCH --partition=big
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=7-00:00:00
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-era5-gaps-%j.log

# ERA5 daily Tmin/Tmax for the years the BGC archive (1950-2024) lacks:
# Tmin 1940-1949 and Tmin+Tmax 2025 (Tmax 1940-1949 is already in era5/raw).
# One CDS request per year (--chunk-years 1, CDS cost limit), skipped when
# the raw file exists, so a rerun resumes. Long silent waits in the CDS
# queue are normal -- see download_era5_daily_tmintmax_full.sbatch.
#   START=1940 END=1942 E5_GROUPS="tmin" sbatch download_era5_daily_gaps.sbatch
# (E5_GROUPS, not GROUPS: GROUPS is a bash builtin holding your group ids and cannot be set)

set -euo pipefail
REPO=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3
cd "$REPO"
MAX_ATTEMPTS=20
for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
    echo "$(date +%T) [era5-gaps] $START-$END $E5_GROUPS attempt $attempt/$MAX_ATTEMPTS"
    if "$PY" download/download_era5_daily.py --start-year "$START" --end-year "$END" --chunk-years 1 --groups $E5_GROUPS; then
        echo "$(date +%T) [era5-gaps] finished"
        exit 0
    fi
    echo "$(date +%T) [era5-gaps] attempt $attempt failed, retrying in 10 min"
    sleep 600
done
exit 1
