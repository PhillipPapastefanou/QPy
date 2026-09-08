"""Driver script: build the global gridded QUINCY forcing NetCDF + Zarr
from GLDAS monthly meteorology, on GLDAS's own 0.5deg grid.

Usage:
    python -m src.forcing.build_global_forcing_gldas --output /path/to/gldas_global_forcing.nc
    python -m src.forcing.build_global_forcing_gldas --year-min 2005 --year-max 2010 --output /tmp/test.nc

GLDAS only covers 2000-2025 and -59.75 to 89.75 lat (no Antarctica) - the
output grid/time range follow GLDAS's own coverage automatically, same as
build_global_forcing_era5.py does for ERA5. See that script's docstring
for the NetCDF-vs-Zarr chunking rationale (identical here).
"""

import argparse

from src.forcing.global_forcing_builder import (
    GlobalForcingBuilder, GLDAS_MET, add_common_args, settings_from_args,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(parser, GLDAS_MET)
    args = parser.parse_args()

    builder = GlobalForcingBuilder(settings_from_args(args, GLDAS_MET))
    builder.build(args.output)


if __name__ == "__main__":
    main()
