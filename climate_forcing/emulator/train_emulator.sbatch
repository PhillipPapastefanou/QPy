#!/bin/bash
#SBATCH --job-name=forcing_emulator
#SBATCH --partition=small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#SBATCH --mem=150G
#SBATCH --time=02:00:00
#SBATCH --output=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy/climate_forcing/emulator/logs/slurm-%j.log

set -euo pipefail

REPO=/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3

if [ -z "${ZARR_INPUT:-}" ]; then
  echo "ZARR_INPUT env var not set" >&2
  exit 1
fi

# each forcing product gets its own self-contained subfolder (models/era/, models/gldas/, ...)
# holding weights.json/.bin + analysis/ - set DATASET to pick which one.
DATASET="${DATASET:-era}"
OUT="$REPO/climate_forcing/emulator/models/$DATASET/weights.json"
mkdir -p "$(dirname "$OUT")"

export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
export MKL_NUM_THREADS=$SLURM_CPUS_PER_TASK
export OPENBLAS_NUM_THREADS=$SLURM_CPUS_PER_TASK

cd "$REPO"
"$PY" -m climate_forcing.emulator.train_emulator \
    --input "$ZARR_INPUT" \
    --output "$OUT" \
    --torch-threads "$SLURM_CPUS_PER_TASK" ${EXTRA_ARGS:-}
