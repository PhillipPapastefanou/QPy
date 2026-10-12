#!/bin/bash
# Hainich (51.08N 10.45E), QUINCY cpp_port land/simple_1d (ssm_run chain),
# 30 spinup years + 1958-2015, five forcings:
#   D_subdaily            CRUNCEP half-hourly climate.dat (reference)
#   E_cruncep_gwgen       the same, aggregated to monthly -> GWGEN (in memory)
#   E2_cruncep_simple     the same monthly -> simple interpolation generator
#   A_emulator_gwgen      TerraClimate emulator monthly -> GWGEN
#   B_terraclimate_gwgen  TerraClimate 0.5deg monthly -> GWGEN
# then compare_runs.py. Needs a cpp_port build with ssm_run and
# monthly_gwgen_ssm_run.
#
# Usage: ./run_hainich.sh <cpp_port_build_dir> <work_dir>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
B=$(cd "$1" && pwd)
W=$2
PY=/Net/Groups/BSI/work_scratch/ppapastefanou/envs/QPy_gnu_mpich/bin/python3
EXP=/Net/Groups/BSI/scratch/ppapastefanou/quincy_exp/exp_52_short_transient_cn_cruncep_ssm_bccedb14/HAI_01/input
CRUNCEP=/Net/Groups/BSI/data/quincy/input/point/CRUNCEPv7/met_forcing/HAI_1901-2015.dat
TC=/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/global_forcing/terraclimate_global_forcing_0.5deg_1958-2025.nc
export LD_LIBRARY_PATH=/opt/ohpc/pub/compiler/gcc/12.2.0/lib64:${LD_LIBRARY_PATH:-}

mkdir -p "$W" && cd "$W"
sed -e 's/forcing_file_start_yr=.*/forcing_file_start_yr=1958/' -e 's/forcing_file_last_yr=.*/forcing_file_last_yr=2015/' \
    -e 's/simulation_length_number=.*/simulation_length_number=58/' \
    -e 's/transient_spinup_start_year=.*/transient_spinup_start_year=1958/' \
    -e 's/transient_spinup_end_year=.*/transient_spinup_end_year=1987/' \
    -e 's/transient_spinup_years=.*/transient_spinup_years=30/' \
    -e 's/transient_simulation_start_year=.*/transient_simulation_start_year=1958/' "$EXP/qs.namelist" > qs.namelist
cp "$EXP/lctlib_quincy_nlct14.def" .
# The port reads forcing from the first record, so cut the file to 1958-.
awk 'NR<=2 || ($1+0>=1958)' "$CRUNCEP" > HAI_1958-2015.dat
"$PY" "$HERE/climate_dat_to_monthly.py" HAI_1958-2015.dat cruncep_monthly.csv
"$PY" "$HERE/../../emulator/export_site_monthly.py" --emulator "$HERE/../../emulator/models/terraclimate" --lon 10.45 --lat 51.08 \
    --forcing "$TC" --out emulator_terraclimate.csv
"$PY" "$HERE/../../emulator/export_site_monthly.py" --lon 10.45 --lat 51.08 --forcing "$TC" --out terraclimate.csv

run() {  # <dir> <program> <args...>
  mkdir -p "$1" && (cd "$1" && "${@:2}" > log 2>&1) || { echo "$1 failed, see $W/$1/log" >&2; exit 1; }
}
M="$B/monthly_gwgen_ssm_run ../qs.namelist ../lctlib_quincy_nlct14.def"
run D_subdaily "$B/ssm_run" ../qs.namelist ../lctlib_quincy_nlct14.def ../HAI_1958-2015.dat &
run E_cruncep_gwgen $M ../cruncep_monthly.csv --write-daily daily.dat &
run E2_cruncep_simple $M ../cruncep_monthly.csv --generator simple --write-daily daily.dat &
run A_emulator_gwgen $M ../emulator_terraclimate.csv --write-daily daily.dat &
run B_terraclimate_gwgen $M ../terraclimate.csv --write-daily daily.dat &
wait
"$PY" "$HERE/compare_runs.py" . HAI_1958-2015.dat D_subdaily E_cruncep_gwgen E2_cruncep_simple A_emulator_gwgen B_terraclimate_gwgen
