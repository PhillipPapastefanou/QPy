#!/bin/bash
#SBATCH --job-name=julia_mpi
#SBATCH --output=julia_mpi_%j.log
#SBATCH --error=julia_mpi_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=16
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=02:00:00

# 1. Lift system limits
ulimit -s unlimited || true
ulimit -v unlimited || true
ulimit -n 65536 || true

# 2. SANITIZE THE ENVIRONMENT (Destroy links to Home directory)
unset LD_LIBRARY_PATH
unset JULIA_LOAD_PATH
unset JULIA_PROJECT
unset JULIA_BINDIR
export PATH=/usr/bin:/bin:/usr/local/bin

# 3. Force EVERYTHING to the scratch drive
SCRATCH_DIR="/Net/Groups/BSI/work_scratch/ppapastefanou"
export JULIA_DEPOT_PATH="$SCRATCH_DIR/julia_depot"
export TMPDIR="$SCRATCH_DIR/tmp"
mkdir -p $JULIA_DEPOT_PATH $TMPDIR

export JULIA_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1

# 4. Run the PURE scratch binary
echo "Starting MPI Julia job with pure scratch binary..."

srun $SCRATCH_DIR/julia-1.11.3/bin/julia --pkgimages=no run_analysis_mpi.jl

echo "Job finished."