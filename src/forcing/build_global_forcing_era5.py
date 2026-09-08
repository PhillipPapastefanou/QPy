"""Driver script: build the global gridded QUINCY forcing NetCDF + Zarr
from ERA5 monthly meteorology, on ERA5's own 0.5deg grid.

Usage:
    python -m src.forcing.build_global_forcing_era5 --output /path/to/era5_global_forcing.nc
    python -m src.forcing.build_global_forcing_era5 --year-min 2000 --year-max 2010 --output /tmp/test.nc

Run from the QPy repository root so that the `src` package resolves.
All source-data paths default to the shared BSI cluster locations and can
be overridden individually if needed.

Writes two files side by side: `<output>.nc` and `<output base>.zarr`.
They are chunked differently on purpose, for two different consumers:
  - NetCDF: one full (lat, lon) map per chunk. Near-instant map reads
    (cdo/xarray/panoply, or the map plots in tests), best compression.
  - Zarr: the full time axis per small (chunk-lat x chunk-lon) tile. One
    point's whole timeseries lives in a single chunk, so extracting a
    (lon, lat) timeseries - including from a JS/WASM point reader doing
    one HTTP range fetch per chunk - is a single-chunk read instead of
    touching every timestep's map. Pass --no-zarr to skip it.

See build_global_forcing_gldas.py for the GLDAS equivalent - both share
the same pipeline (global_forcing_builder.py) and only swap out which
MetSourceConfig (ERA5_MET vs GLDAS_MET) defines the target grid.
"""

import argparse

from src.forcing.global_forcing_builder import (
    GlobalForcingBuilder, ERA5_MET, add_common_args, settings_from_args,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(parser, ERA5_MET)
    args = parser.parse_args()

    builder = GlobalForcingBuilder(settings_from_args(args, ERA5_MET))
    builder.build(args.output)


if __name__ == "__main__":
    main()
