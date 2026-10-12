#!/bin/bash
#SBATCH --job-name=gldas_tmintmax
#SBATCH --partition=big
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=1-00:00:00
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-gldas-tmintmax-%j.log

# Derives GLDAS monthly t_air_min/t_air_max for the full 2000-2025 record,
# now that download_gldas_daily_2018-2025.sbatch (job 7375276) finished
# extending the raw 3-hourly archive past its prior 2017 cutoff. Runs under
# Slurm rather than a plain background shell for the same reason as
# download_era5_daily_tmintmax_full.sbatch (sibling script): this session's
# interactive process has repeatedly torn down mid-run, killing background
# children regardless of nohup/harness tracking. Resumable: process_year()
# caches each year's result under raw/tmin_tmax_yearly/ and skips years
# already cached, so a restart after an interruption only redoes the year
# that was in flight.
#
# The 2000-2017 per-year caches from the earlier run are reused as-is. The
# existing 2018 cache was deleted before this job was queued -- confirmed
# live 2026-09-08/09 it was built (Sep 8 10:02) from that year's raw data
# while it was still only 71% downloaded, so it would otherwise silently
# feed incomplete-year data into the combined output now that the full
# year (2920/2920 files) is on disk.
#
# Also deleted before this run: stray single-year test outputs
# (gldas_t_air_{min,max}_derived_{2017-2017,2018-2018}_monthly.nc) in
# monthly/{0.25deg,0.5deg}/. plot_seasonal_cycles_9sites.py's
# _latest_matching_file() picks the alphabetically-last glob match, and
# "2018-2018" sorts after "2000-2025" no matter how far the real combined
# range extends -- left in place, the plot script would have silently read
# 2018-only data for every requested year. This run's output
# (gldas_t_air_{min,max}_derived_2000-2025_monthly.nc) will be the only
# remaining match once this completes.
#
# NOTE: the final concat+write step (after all years are cached) has been
# observed to hang indefinitely with zero I/O progress on this cluster's
# networked filesystem (confirmed via /proc/<pid>/io showing no byte-count
# change across repeated checks) -- the same class of NFS/HDF5 locking
# issue documented in coarsen_terraclimate_to_0.5deg.py's own docstring.
# If this job's log stalls at "wrote ..." for a long time with no further
# progress and no CPU time accruing, cancel and resubmit -- the expensive
# per-year work is already cached, so a resubmit reaches the final write
# again quickly instead of redoing everything.

set -euo pipefail

REPO=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/conversion
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3

cd "$REPO"
"$PY" derive_gldas_tmin_tmax.py --start-year 2000 --end-year 2025
