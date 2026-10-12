#!/bin/bash
#SBATCH --job-name=gldas_daily_1825
#SBATCH --partition=big
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=150G
#SBATCH --time=5-00:00:00
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-gldas-daily-1825-%j.log

# Downloads GLDAS_NOAH025_3H.2.1 raw 3-hourly files for 2018-2025 (extending
# the existing 2000-2017 raw archive). 2018 was previously only 71% complete
# (2076/2920 files) -- download_file() skips any file that already exists,
# so this resumes 2018 rather than re-downloading it, then continues through
# 2025. Needed so derive_gldas_tmin_tmax.py can extend its tmin/tmax record
# past 2017 (the monthly mean product, GLDAS_NOAH025_M.2.1, already covers
# 2000-2025 -- only the 3-hourly tmin/tmax source is short).
#
# Runs under Slurm (not a plain background shell) for the same reason as the
# sibling era5/gldas full-record jobs: this session's interactive process
# has repeatedly torn down mid-run, killing background children regardless
# of nohup/harness tracking.
#
# Resumable at the file level (download_file() skips existing dest files),
# so a restart after an interruption or a transient proxy/auth failure only
# re-fetches what's missing.
#
# SIZE: ~380GB raw over 8 years (see download_gldas.py docstring: ~1.4GB/yr
# per variable-group, 8 vars/file, 8 years) -- expect several days at this
# cluster's outbound bandwidth even with 3 retries per file baked in.
#
# MEMORY: a first attempt at 8G was OOM-killed after ~20min (confirmed via
# sacct: MaxRSS 8266356K) -- process_daily() in download_gldas.py holds an
# entire year's daily-mean fields (8 variables x 600x1440 grid x up to 366
# days) as a plain Python list before the single per-year to_netcdf write,
# which is roughly 10-20GB/year depending on dtype/overhead. A second
# attempt at 48G also OOM-killed (year 2 alone reached 35GB+ despite year 1
# peaking at ~22GB) -- root cause was memory growing *across* year
# iterations, not just within one: dask task graphs from open_mfdataset
# form reference cycles that only the cyclic GC clears, not simple
# refcounting, so uncollected graph objects from year N were still resident
# when year N+1 started. Fixed with an explicit gc.collect() between years
# in download_gldas.py. 150G is generous headroom on top of that fix --
# these nodes have ~2TB RAM with plenty free, so there's no reason to run
# this close to a cap a third time.

set -euo pipefail

REPO=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3

export EARTHDATA_TOKEN
EARTHDATA_TOKEN="$(cat "$HOME/.earthdata_token")"

cd "$REPO"
"$PY" download/download_gldas.py --products daily_0.25deg --start-year 2018 --end-year 2025
