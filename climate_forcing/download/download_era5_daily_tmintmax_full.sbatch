#!/bin/bash
#SBATCH --job-name=era5_tmintmax
#SBATCH --partition=big
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=14-00:00:00
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-era5-tmintmax-%j.log

# Full 1940-2025 ERA5 daily tmax/tmin pull. Runs under Slurm (not a plain
# background shell) because this session's interactive process has twice
# been torn down mid-download (Claude Code agent/session teardown kills
# background children regardless of nohup or the harness's own background
# tracking -- confirmed live 2026-09-08), which a multi-day, 172-request
# CDS job can't tolerate. See PORT_NOTES/session history: --groups tmax tmin
# (not the default all-4-group request) works around CDS's per-request cost
# limit for this dataset (derived-era5-single-levels-daily-statistics) --
# even a 3-year single-variable global request was rejected ("cost limits
# exceeded"), so --chunk-years 1 is required, not just a smaller default.
#
# EXPECT LONG SILENT STRETCHES: confirmed live 2026-09-08 that a prior run
# of this job (7370259) sat in CDS's "accepted" state for 1h42m with zero
# log output before being (incorrectly) judged stuck and cancelled --
# cdsapi (via ecmwf.datastores.processing) only logs on a status
# *transition* (accepted -> running -> successful) and has no client-side
# timeout, so a quiet log does not mean a hung process. CDS's own live
# dashboard showed ~6,000 requests queued against ~500 running at the time,
# i.e. genuine backend queue congestion, not a bug here. --time is set
# generously (14 days) and the partition itself has no time limit (sinfo:
# TIMELIMIT infinite) specifically so this can sit queued upstream for as
# long as CDS needs without Slurm or an operator killing it prematurely.
# Check `sacct -j <id>` MaxRSS/CPU time, not just log quietness, before
# assuming a problem -- near-zero RSS/CPU with a quiet log is normal idle
# waiting, not a hang.

set -euo pipefail

REPO=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3

cd "$REPO"
# Transient CDS/network failures (e.g. SSL EOF, job 7374551) kill the whole
# python process; the script skips years already on disk, so just rerun it.
MAX_ATTEMPTS=20
for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
    echo "$(date +%T) [era5-sbatch] attempt $attempt/$MAX_ATTEMPTS"
    if "$PY" download/download_era5_daily.py --start-year 1940 --end-year 2025 --chunk-years 1 --groups tmax tmin; then
        echo "$(date +%T) [era5-sbatch] finished"
        exit 0
    fi
    echo "$(date +%T) [era5-sbatch] attempt $attempt failed, retrying in 10 min"
    sleep 600
done
echo "$(date +%T) [era5-sbatch] giving up after $MAX_ATTEMPTS attempts"
exit 1
