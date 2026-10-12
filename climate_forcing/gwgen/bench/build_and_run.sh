#!/bin/bash
# Benchmarks LPJ-GUESS's GWGEN (modules/weathergen.cpp, compiled unchanged
# against shim/guess.h) against the current QUINCY cpp_port monthly->daily
# generator on random GLDAS 0.5deg land points. See
# ../../NOTES_2026-10-10_downloads_emulator_gwgen.md for results.
#
# Usage: ./build_and_run.sh [n_points]   (default 2000)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${WORK:-$HERE/work}
N=${1:-2000}
LPJ=/Net/Groups/BSI/work_scratch/ppapastefanou/src/LPJ-GUESS
QUINCY=/Net/Groups/BSI/work_scratch/ppapastefanou/src/quincy
QBRANCH=feature/plant-hydraulics-physics-mpich-cc
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3
GLDAS=/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/global_forcing/gldas_global_forcing_0.5deg_2000-2025.nc

mkdir -p "$WORK/shim/quincy"
cp "$HERE"/shim/guess.h "$HERE"/shim/config.h "$WORK/shim/"
cp "$HERE"/shim/quincy/kind.hpp "$WORK/shim/quincy/"
cp "$LPJ/modules/weathergen.cpp" "$LPJ/modules/weathergen.h" "$WORK/"
git -C "$QUINCY" show "$QBRANCH:cpp_port/src/monthly_to_daily_forcing.cpp" > "$WORK/m2d.cpp"
git -C "$QUINCY" show "$QBRANCH:cpp_port/include/quincy/monthly_to_daily_forcing.hpp" \
    > "$WORK/shim/quincy/monthly_to_daily_forcing.hpp"
cp "$HERE/bench.cpp" "$WORK/"

[ -f "$WORK/points_$N.csv" ] || "$PY" "$HERE/make_points.py" "$GLDAS" "$N" "$WORK/points_$N.csv"

cd "$WORK"
g++ -std=c++17 -O2 -w -Ishim -I. -o bench bench.cpp weathergen.cpp
./bench "points_$N.csv"
