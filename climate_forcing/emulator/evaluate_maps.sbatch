#!/bin/bash
#SBATCH --job-name=forcing_emulator_maps
#SBATCH --partition=small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=100G
#SBATCH --time=01:00:00
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/emulator/logs/slurm-maps-%j.log

set -euo pipefail

REPO=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3

if [ -z "${ZARR_INPUT:-}" ]; then
  echo "ZARR_INPUT env var not set" >&2
  exit 1
fi

# must match the DATASET used for train_emulator.sbatch (see there for details).
DATASET="${DATASET:-era}"
EMDIR="$REPO/climate_forcing/emulator/models/$DATASET"

export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
export MKL_NUM_THREADS=$SLURM_CPUS_PER_TASK
export OPENBLAS_NUM_THREADS=$SLURM_CPUS_PER_TASK

cd "$REPO"
"$PY" -m climate_forcing.emulator.evaluate_maps \
    --input "$ZARR_INPUT" \
    --weights "$EMDIR/weights.json" \
    --output-dir "$EMDIR/analysis"
