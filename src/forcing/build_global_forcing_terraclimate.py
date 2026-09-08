"""Driver script: build the global gridded QUINCY forcing NetCDF + Zarr
from TerraClimate, coarsened to a 0.5deg grid (see build_global_forcing.py
for the ERA5 equivalent).

Usage:
    python -m src.forcing.build_global_forcing_terraclimate --output /path/to/terraclimate_global_forcing.nc
    python -m src.forcing.build_global_forcing_terraclimate --year-min 2000 --year-max 2010 --output /tmp/test.nc

Run conversion/coarsen_terraclimate_to_0.5deg.py first -- TerraClimate's
native grid (1/24deg) is ~144x finer than ERA5/GLDAS's 0.5deg, so this
reads the coarsened product under driver_data/terraclimate/monthly/0.5deg/,
not the native-resolution files under monthly/4km/. See that script's
docstring for the coarsening/unit-conversion details.

TerraClimate does not report longwave radiation or cloud cover at all, so
TERRACLIMATE_MET's variable list (global_forcing_builder.py) omits both --
the output file simply has no lw_srf_down variable, rather than a
fabricated one.

See build_global_forcing_gldas.py for the GLDAS equivalent -- all three
share the same pipeline (global_forcing_builder.py) and only swap out
which MetSourceConfig defines the target grid/variables.
"""

import argparse

from src.forcing.global_forcing_builder import (
    GlobalForcingBuilder, TERRACLIMATE_MET, add_common_args, settings_from_args,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(parser, TERRACLIMATE_MET)
    args = parser.parse_args()

    builder = GlobalForcingBuilder(settings_from_args(args, TERRACLIMATE_MET))
    builder.build(args.output)


if __name__ == "__main__":
    main()
