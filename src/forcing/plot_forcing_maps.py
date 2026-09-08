"""QA diagnostic: plot every meteorological variable of a global forcing
NetCDF as a 3x3 grid of maps, one panel per variable, for a single month.

This is the "map plotting for tests" use case the NetCDF file is chunked
for (see global_forcing_builder.py / build_global_forcing_era5.py) - one
full (lat, lon) map per chunk, so this reads fast even though the point
lookups (Zarr) are optimized for something else entirely.

Usage:
    python -m src.forcing.plot_forcing_maps --input /path/to/era5_global_forcing.nc --output era5_maps.png
    python -m src.forcing.plot_forcing_maps --input /path/to/gldas_global_forcing.nc --output gldas_maps.png \\
        --variables t_air q_air press_srf rain snow wind_air swvis_srf_down lw_srf_down
"""

import argparse

import cartopy.crs as ccrs
import matplotlib
import matplotlib.pyplot as plt
import netCDF4
import numpy as np

matplotlib.use("Agg")

from src.forcing.global_forcing_builder import ERA5_MET, GLDAS_MET

MET_BY_NAME = {"era5": ERA5_MET, "gldas": GLDAS_MET}


def plot_variable_grid(nc_path, out_png, variables, date_str=None, cmap="viridis"):
    ds = netCDF4.Dataset(nc_path)
    try:
        lat = ds["lat"][:]
        lon = ds["lon"][:]
        time_num = ds["time"][:]
        dates = netCDF4.num2date(time_num, ds["time"].units, getattr(ds["time"], "calendar", "standard"))

        if date_str is None:
            time_idx = -1
        else:
            target_year, target_month = (int(x) for x in date_str.split("-"))
            time_idx = next(i for i, d in enumerate(dates) if d.year == target_year and d.month == target_month)
        chosen_date = dates[time_idx]

        fig, axes = plt.subplots(3, 3, figsize=(16, 10), subplot_kw={"projection": ccrs.PlateCarree()})
        fig.suptitle(f"{nc_path.split('/')[-1]} - {chosen_date:%Y-%m}", fontsize=13)

        for ax, var in zip(axes.flat, variables):
            data = ds[var][time_idx, :, :]
            units = getattr(ds[var], "units", "")
            mesh = ax.pcolormesh(lon, lat, data, transform=ccrs.PlateCarree(), cmap=cmap, shading="auto")
            ax.coastlines(linewidth=0.4)
            ax.set_title(f"{var} [{units}]", fontsize=10)
            fig.colorbar(mesh, ax=ax, orientation="horizontal", pad=0.05, shrink=0.85, fraction=0.05)

        for ax in axes.flat[len(variables):]:
            ax.axis("off")

        fig.tight_layout(rect=[0, 0, 1, 0.96])
        fig.savefig(out_png, dpi=130)
        plt.close(fig)
    finally:
        ds.close()


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, help="Global forcing NetCDF path")
    p.add_argument("--output", required=True, help="Output PNG path")
    p.add_argument("--source", choices=["era5", "gldas"], default=None,
                    help="Which MetSourceConfig's variable list to plot; auto-detected from --input if omitted")
    p.add_argument("--variables", nargs="+", default=None,
                    help="Explicit variable list (overrides --source), at most 9")
    p.add_argument("--date", default=None, help="YYYY-MM month to plot (defaults to the last timestep)")
    return p.parse_args()


def main():
    args = parse_args()
    if args.variables is not None:
        variables = args.variables
    else:
        source = args.source or next((k for k in MET_BY_NAME if k in args.input.lower()), None)
        if source is None:
            raise SystemExit("Could not infer --source from --input; pass --source or --variables explicitly.")
        variables = MET_BY_NAME[source].variables
    if len(variables) > 9:
        raise SystemExit(f"3x3 grid holds at most 9 variables, got {len(variables)}: {variables}")

    plot_variable_grid(args.input, args.output, variables, date_str=args.date)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
