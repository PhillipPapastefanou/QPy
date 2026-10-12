"""Driver script: build the global gridded QUINCY forcing NetCDF + Zarr
from CRU-JRA v2.5 monthly meteorology (0.5deg, 1901-2023).

Run climate_forcing/conversion/build_crujra_monthly.py first (wind + merge),
which writes the QUINCY-named monthly files CRUJRA_MET points at.

Usage:
    python -m src.forcing.build_global_forcing_crujra \\
        --output /path/to/crujra_global_forcing_0.5deg_1901-2023.nc
"""

import argparse

from src.forcing.global_forcing_builder import (
    GlobalForcingBuilder, CRUJRA_MET, add_common_args, settings_from_args,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(parser, CRUJRA_MET)
    args = parser.parse_args()

    builder = GlobalForcingBuilder(settings_from_args(args, CRUJRA_MET))
    builder.build(args.output)


if __name__ == "__main__":
    main()
