#!/bin/bash
#SBATCH --job-name=e5l_merge
#SBATCH --partition=work
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --array=0-6
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/logs/slurm-e5l-merge-%A_%a.log

# Stage 2 of the ERA5-Land monthly forcing: one array task per variable,
# concatenating the per-year cache into era5land_<var>_1950-2024_monthly.nc
# at 0.1/0.25/0.5deg; press_q writes the gap-filled press_srf and q_air (see
# build_era5land_monthly.py). Submit with --dependency=afterok:<stage-1 job id>.

set -euo pipefail
REPO=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/conversion
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3
VARS=(t_air_min t_air_max precip_total swvis_srf_down wind_air lw_srf_down press_q)

cd "$REPO"
"$PY" build_era5land_monthly.py merge "${VARS[$SLURM_ARRAY_TASK_ID]}"
