#!/bin/bash
# Bit-for-bit check of the QUINCY cpp_port GWGEN (cpp_port/src/gwgen.cpp, in
# LPJ-GUESS year-boundary mode) against LPJ-GUESS modules/weathergen.cpp
# compiled unchanged, on random GLDAS 0.5deg land points (see make_points.py).
#
# Usage: ./check_port.sh [n_points]   (default 2000)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${WORK:-$HERE/work}
N=${1:-2000}
LPJ=/Net/Groups/BSI/work_scratch/ppapastefanou/src/LPJ-GUESS
QUINCY=/Net/Groups/BSI/work_scratch/ppapastefanou/src/quincy/cpp_port
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3
GLDAS=/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/global_forcing/gldas_global_forcing_0.5deg_2000-2025.nc
CXX=${CXX:-/opt/ohpc/pub/compiler/gcc/12.2.0/bin/g++}

mkdir -p "$WORK/shim"
cp "$HERE"/shim/guess.h "$HERE"/shim/config.h "$WORK/shim/"
cp "$LPJ/modules/weathergen.cpp" "$LPJ/modules/weathergen.h" "$WORK/"
[ -f "$WORK/points_$N.csv" ] || "$PY" "$HERE/make_points.py" "$GLDAS" "$N" "$WORK/points_$N.csv"

cd "$WORK"
"$CXX" -std=c++20 -O2 -w -Ishim -I. -I"$QUINCY/include" -o check_port \
    "$HERE/check_port.cpp" weathergen.cpp "$QUINCY/src/gwgen.cpp"
LD_LIBRARY_PATH=/opt/ohpc/pub/compiler/gcc/12.2.0/lib64:${LD_LIBRARY_PATH:-} ./check_port "points_$N.csv"
