"""Driver script: build the global gridded QUINCY forcing NetCDF + Zarr
from ERA5-Land monthly meteorology, at 0.5deg or 0.25deg.

Usage:
    python -m src.forcing.build_global_forcing_era5land --res 0.25deg \\
        --output /path/to/era5land_global_forcing_0.25deg_1950-2024.nc

The output grid is the ERA5-Land monthly files' own grid (cell-centred,
see climate_forcing/conversion/build_era5land_monthly.py). Soil grids are
native 0.1deg, so 0.25deg carries real soil detail; lithology, phosphorus
pools and N/P deposition are native 0.5deg and are nearest-neighbour
resampled (replicated) onto the finer grid, as for every other source.
See build_global_forcing_era5.py for the NetCDF-vs-Zarr chunking rationale.
"""

import argparse
import dataclasses

from src.forcing.global_forcing_builder import (
    GlobalForcingBuilder, ERA5LAND_MET, add_common_args, settings_from_args,
)

MONTHLY_ROOT = "/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/era5_land/monthly"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(parser, ERA5LAND_MET)
    parser.add_argument("--res", choices=["0.5deg", "0.25deg", "0.1deg"], default="0.5deg",
                        help="ERA5-Land monthly resolution to build from (ignored if --met-dir is given)")
    args = parser.parse_args()
    if args.met_dir == ERA5LAND_MET.dir:
        args.met_dir = f"{MONTHLY_ROOT}/{args.res}"
    met = dataclasses.replace(ERA5LAND_MET, dir=args.met_dir)

    builder = GlobalForcingBuilder(settings_from_args(args, met))
    builder.build(args.output)


if __name__ == "__main__":
    main()
