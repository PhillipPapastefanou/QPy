"""Build one global, gridded NetCDF + Zarr forcing file on a met source's
own 0.5deg grid (ERA5, GLDAS, ...).

Combines the chosen gridded meteorology (see MetSourceConfig / ERA5_MET /
GLDAS_MET below) with the auxiliary datasets that gridded_input.py /
quinct_input_generator.py otherwise extract one site at a time (CO2 +
isotopes, N deposition, P deposition, soil taxonomy, lithology, phosphorus
pools). The met source defines the target grid - everything else is
nearest-neighbour regridded onto it, so the same pipeline produces an
ERA5-gridded file or a GLDAS-gridded file depending only on which
MetSourceConfig is passed in `GlobalForcingSettings.met`.

Time-varying fields keep a (time, lat, lon) grid; fields that are constant
per gridcell (soil grids, lithology, phosphorus pools, P deposition) are
written as (lat, lon) only; CO2 concentration/dC13 are pure (time) series
and CO2-DC14 is (time, lat) since it only varies by latitude band - none
of these are broadcast to the full 3-D grid, to keep the file size sane.
"""

import dataclasses
import glob
import os
from dataclasses import dataclass, field
from typing import Optional

import netCDF4
import numpy as np
import pandas as pd
import zarr
from global_land_mask import globe
from zarr.codecs import Shuffle, GzipCodec, ZstdCodec

from src.forcing.misc_forcing_settings import ProjectionScenario


@dataclass
class MetSourceConfig:
    """Describes one gridded meteorology source: where its monthly files
    live, which variables/files to pull in, and how to read its grid.
    Files are expected to follow the `<name>_<var>_*_monthly.nc` naming
    convention already used under driver_data/, one variable per file."""
    name: str
    dir: str
    variables: list
    lat_name: str = "lat"
    lon_name: str = "lon"
    # (scale_factor, output_units) for variables needing a unit conversion;
    # everything else keeps its native units.
    unit_override: dict = field(default_factory=dict)
    # Fallback long_names for variables whose source files carry none.
    long_name_fallback: dict = field(default_factory=dict)
    # Maps an output variable name to several source variables that get
    # summed to produce it (see GLDAS_MET's "rain" below); omit for a plain
    # 1:1 read of the source file named `var`.
    combine_vars: dict = field(default_factory=dict)
    # Variables with NO time dimension at all -- written as (lat, lon), not
    # (time, lat, lon), and read once rather than time-indexed. For
    # TerraClimate's press_srf: a climatological estimate from elevation
    # (see coarsen_terraclimate_to_0.5deg.py), genuinely constant in time,
    # unlike ERA5/GLDAS's real synoptic surface pressure.
    static_variables: list = field(default_factory=list)
    # Set NaN over ocean gridcells (via the `global_land_mask` package) for
    # every variable in `variables`. ERA5 reports real values over ocean
    # (e.g. SST-driven t2m) which a land model has no use for; GLDAS is
    # already NaN there natively (land-surface model output), so leave this
    # off for it.
    mask_ocean: bool = False


ERA5_MET = MetSourceConfig(
    name="era5",
    dir="/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/era5/monthly/0.5deg",
    # t_air_min/t_air_max replace the mean t_air here (2026-09-11, at user's
    # request) so this file directly carries what monthly_to_daily_forcing's
    # weather generator needs (MonthlyForcingRecord has no mean-t_air field
    # at all, only tmin/tmax). NOTE: era5_t_air_{min,max}_*_monthly.nc don't
    # exist yet as of this change -- ERA5 only has a genuine daily tmax/tmin
    # product (download_era5_daily.py --groups tmax tmin), still downloading
    # (see climate_forcing/logs/slurm-era5-tmintmax-*.log). Rebuilding this
    # zarr with real ERA5 min/max needs that download to finish AND a
    # derive_era5_tmin_tmax_monthly.py-style script (mirroring
    # derive_gldas_tmin_tmax.py) to aggregate daily -> monthly mean-of-
    # extremes into era5_t_air_{min,max}_*_monthly.nc first -- neither
    # exists yet, so build_global_forcing_era5.py will FileNotFoundError
    # until then.
    variables=["t_air_min", "t_air_max", "q_air", "press_srf", "precip_total", "wind_air",
               "cloud_cover", "swvis_srf_down", "lw_srf_down"],
    lat_name="latitude",
    lon_name="longitude",
    unit_override={
        "q_air": (1000.0, "g kg-1"),      # kg/kg -> g/kg
        "press_srf": (0.01, "hPa"),        # Pa -> hPa
    },
    long_name_fallback={
        "precip_total": "Total precipitation",
        "swvis_srf_down": "Visible-band surface downward shortwave radiation",
        "lw_srf_down": "Surface downward longwave radiation",
    },
    mask_ocean=True,
)

GLDAS_MET = MetSourceConfig(
    name="gldas",
    dir="/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/gldas/monthly/0.5deg",
    # t_air_min/t_air_max replace the mean t_air here (2026-09-11, at user's
    # request) so this file directly carries what monthly_to_daily_forcing's
    # weather generator needs (MonthlyForcingRecord has no mean-t_air field
    # at all, only tmin/tmax). Sourced from
    # climate_forcing/conversion/derive_gldas_tmin_tmax.py's
    # gldas_t_air_{min,max}_derived_*_monthly.nc (mean-of-daily-extremes from
    # GLDAS's raw 3-hourly Tair_f_inst -- see that script's own docstring for
    # the approximation this involves). "snow" is not written as its own
    # output variable - see combine_vars.
    variables=["t_air_min", "t_air_max", "q_air", "press_srf", "rain", "wind_air",
               "swvis_srf_down", "lw_srf_down"],
    lat_name="lat",
    lon_name="lon",
    unit_override={
        "q_air": (1000.0, "g kg-1"),      # kg/kg -> g/kg
        "press_srf": (0.01, "hPa"),        # Pa -> hPa
    },
    long_name_fallback={
        "rain": "Total precipitation (rain + snow)",
    },
    # QUINCY's "rain" forcing variable means total precipitation, not just
    # the liquid fraction - GLDAS reports rain/snow separately, so sum them
    # into the single "rain" output variable to match that convention.
    combine_vars={"rain": ["rain", "snow"]},
)

TERRACLIMATE_MET = MetSourceConfig(
    name="terraclimate",
    dir="/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/terraclimate/monthly/0.5deg",
    # No native lw_srf_down or cloud_cover - TerraClimate doesn't report either at
    # all (native variables are limited to tmax/tmin/ppt/srad/vap/ws plus
    # some derived indices like PDSI/AET that aren't meteorological
    # forcing). t_air/rain/press_srf/q_air are not native TerraClimate
    # variables either - they're built by
    # conversion/coarsen_terraclimate_to_0.5deg.py from tmax+tmin, ppt,
    # and elevation+vap respectively (see that script's docstring), and
    # already carry the right units on disk (K, mm/day, Pa, kg/kg) so no
    # unit_override is needed for them here beyond the same q_air/press_srf
    # entries ERA5_MET already uses.
    # t_air_min/t_air_max replace the mean t_air here (2026-09-11, at user's
    # request) so this file directly carries what monthly_to_daily_forcing's
    # weather generator needs (MonthlyForcingRecord has no mean-t_air field
    # at all, only tmin/tmax) -- native tmax/tmin coarsened straight to K,
    # same coarsen_terraclimate_to_0.5deg.py output as everything else here.
    # lw_srf_down (2026-10-11) is not native either: derived from TerraClimate's
    # own tmin/tmax, q_air, shortwave and elevation by
    # conversion/derive_terraclimate_longwave.py (Prata clear-sky +
    # Crawford-Duchon clouds; ~+3 W m-2 bias, 14 W m-2 rmse vs ERA5).
    variables=["t_air_min", "t_air_max", "q_air", "rain", "wind_air", "swvis_srf_down", "lw_srf_down"],
    static_variables=["press_srf"],  # no time dimension -- see MetSourceConfig.static_variables
    unit_override={
        "q_air": (1000.0, "g kg-1"),      # kg/kg -> g/kg
        "press_srf": (0.01, "hPa"),        # Pa -> hPa
    },
)
ERA5LAND_MET = MetSourceConfig(
    name="era5land",
    # 0.5deg by default; build_global_forcing_era5land.py --res 0.25deg points
    # at the 0.25deg files. Built by climate_forcing/conversion/
    # build_era5land_monthly.py: land-only (NaN over ocean already), cell-
    # centred grid, Tmin/Tmax instead of mean temperature, longwave from ERA5.
    dir="/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/era5_land/monthly/0.5deg",
    variables=["t_air_min", "t_air_max", "q_air", "press_srf", "precip_total", "wind_air",
               "swvis_srf_down", "lw_srf_down"],
    lat_name="lat",
    lon_name="lon",
    unit_override={
        "q_air": (1000.0, "g kg-1"),      # kg/kg -> g/kg
        "press_srf": (0.01, "hPa"),        # Pa -> hPa
    },
)

CRUJRA_MET = MetSourceConfig(
    name="crujra",
    # CRU-JRA v2.5 only (v3.0's precipitation lacks the CRU TS bias adjustment),
    # converted to QUINCY names/units by climate_forcing/conversion/
    # build_crujra_monthly.py: native Tmin/Tmax, precipitation in mm/day, wind
    # as the monthly mean of 6-hourly speed. Land-only (NaN over ocean), 0.5deg
    # cells, 1901-2023.
    dir="/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/crujra/monthly/0.5deg_quincy",
    variables=["t_air_min", "t_air_max", "q_air", "press_srf", "precip_total", "wind_air",
               "swvis_srf_down", "lw_srf_down"],
    lat_name="lat",
    lon_name="lon",
    unit_override={
        "q_air": (1000.0, "g kg-1"),      # kg/kg -> g/kg
        "press_srf": (0.01, "hPa"),        # Pa -> hPa
    },
)

NDEP_UNIT_CONVERT = 86400.0 * 1.0e6  # kg(N) m-2 s-1 -> mg(N) m-2 day-1


@dataclass
class GlobalForcingSettings:
    met: MetSourceConfig = field(default_factory=lambda: ERA5_MET)

    co2_concentration_file: str = "/Net/Groups/BSI/people/ppapastefanou/climate_aux/co2/GCP2023_co2_global.dat"
    co2_dC13_file: str = "/Net/Groups/BSI/people/ppapastefanou/climate_aux/co2/delta13C_in_air_input4MIPs_GM_1850-2021_extrapolated.txt"
    co2_DC14_file: str = "/Net/Groups/BSI/people/ppapastefanou/climate_aux/co2/Delta14C_in_air_input4MIPs_SHTRNH_1850-2021_extrapolated.txt"

    root_ndep_path: str = "/Net/Groups/BSI/data/OCN/input/gridded/NDEP/CESM-CAM"
    ndep_projection_scenario: ProjectionScenario = ProjectionScenario.RCP126

    pdep_file: str = "/Net/Groups/BSI/work/quincy/model/InputDataSources/P-DEP/nitrogenandphosphorus_annualdep_0.5x0.5.nc"

    soil_grid_dir: str = "/Net/Groups/BSI/data/datastructure_bgi_cpy/grid/Global/0d10_static/soilgrids/v0_5_1/Data"
    phosphorus_dir: str = "/Net/Groups/BSI/data/datastructure_bgi_cpy/grid/Global/0d50_static/Phosphorous/v2014_06/Data"
    lithology_file: str = "/Net/Groups/BSI/data/datastructure_bgi_cpy/grid/Global/0d50_static/GLiM/v1_0/Data/GLim.720.360.nc"

    year_min: int = 1940
    year_max: Optional[int] = None  # None => auto-detect from the shortest-covered source
    zlib_complevel: int = 5

    # Chunking: every chunk holds the FULL time axis for a small (chunk_lat x
    # chunk_lon) tile, so extracting one point's whole timeseries touches a
    # single chunk. Reading one full-globe map at one timestep instead needs
    # to touch every chunk - acceptable since that access pattern is only
    # used for occasional test plotting, not the point/timeseries lookups
    # this file is chunked for (see the WASM/Zarr discussion in the driver
    # script docstring).
    chunk_lat: int = 20
    chunk_lon: int = 20
    shuffle: bool = True

    write_zarr: bool = True  # companion Zarr store, same chunking, for point lookups from JS/WASM
    # zstd decodes ~5x faster than gzip for ~+14% size - the right trade for a
    # compiled WASM reader that can link libzstd directly (no browser-native
    # decoder to fall back on). Use "gzip" instead if the WASM/JS side is
    # limited to the browser's native DecompressionStream (gzip/deflate only).
    zarr_compressor: str = "zstd"
    verbose: bool = True

    def dprint(self, *args):
        if self.verbose:
            print(*args)


def nearest_index(target, source, wrap=None):
    """Vectorized nearest-neighbour index of each `target` value in `source`."""
    target = np.asarray(target, dtype=np.float64)
    source = np.asarray(source, dtype=np.float64)
    if wrap is not None:
        target = np.mod(target, wrap)
        source = np.mod(source, wrap)
    diff = np.abs(target[:, None] - source[None, :])
    if wrap is not None:
        diff = np.minimum(diff, wrap - diff)
    return np.argmin(diff, axis=1)


def regrid_nearest(data, src_lat, src_lon, tgt_lat, tgt_lon):
    """Nearest-neighbour regrid of a (..., lat, lon) array onto (tgt_lat, tgt_lon)."""
    lat_idx = nearest_index(tgt_lat, src_lat)
    lon_idx = nearest_index(tgt_lon, src_lon, wrap=360.0)
    out = np.take(data, lat_idx, axis=-2)
    out = np.take(out, lon_idx, axis=-1)
    return out


def to_nan(arr):
    if np.ma.isMaskedArray(arr):
        arr = arr.astype(np.float64).filled(np.nan)
    return np.asarray(arr, dtype=np.float32)


class GlobalForcingBuilder:
    def __init__(self, settings: GlobalForcingSettings):
        self.settings = settings

    # ------------------------------------------------------------------
    # Target grid / time axis
    # ------------------------------------------------------------------
    def _met_path(self, var):
        met = self.settings.met
        matches = sorted(glob.glob(os.path.join(met.dir, f"{met.name}_{var}_*_monthly.nc")))
        if not matches:
            raise FileNotFoundError(f"No {met.name} file found for variable '{var}' in {met.dir}")
        return matches[0]

    def _load_target_grid(self):
        met = self.settings.met
        with netCDF4.Dataset(self._met_path(met.variables[0])) as ds:
            src_lat = ds[met.lat_name][:].astype(np.float64)
            src_lon = ds[met.lon_name][:].astype(np.float64)
            self.time_num = ds["time"][:].astype(np.int64)
            self.time_units = ds["time"].units
            self.time_calendar = getattr(ds["time"], "calendar", "standard")

        # Normalize the output grid to the COARDS/CF-standard orientation -
        # latitude ascending (south to north) and longitude in [-180, 180) -
        # regardless of how the source product ships its own grid (e.g.
        # ERA5's native files are lat-descending with lon in [0, 360)).
        # self._src_lat/_src_lon keep the original values for the same-grid
        # check in _read_met_var, and _lat_order/_lon_order are the
        # permutation _read_met_var applies to reorder same-grid reads to
        # match. Everything read via _read_static_grid/_build_ndep's
        # nearest-neighbour regrid targets self.lat/self.lon by value and
        # needs no separate handling.
        self._src_lat = src_lat
        self._src_lon = src_lon
        self._lat_order = np.argsort(src_lat)
        lon_180 = ((src_lon + 180.0) % 360.0) - 180.0
        self._lon_order = np.argsort(lon_180)
        self.lat = src_lat[self._lat_order]
        self.lon = lon_180[self._lon_order]

        dates = netCDF4.num2date(self.time_num, self.time_units, self.time_calendar)
        self.years = np.array([d.year for d in dates])
        self.months = np.array([d.month for d in dates])

        self.land_mask = None
        if met.mask_ocean:
            lon2d, lat2d = np.meshgrid(self.lon, self.lat)
            self.land_mask = globe.is_land(lat2d, lon2d)

    def _last_full_year(self, path, kind):
        if kind == "co2":
            df = pd.read_csv(path, sep=r"\s+", header=None, names=["year", "value"])
            return int(df["year"].max())
        elif kind == "isotope":
            df = pd.read_csv(path, sep=r"\s+", header=None)
            year = df[0] - 0.5
            return int(year.astype(int).max())
        raise ValueError(kind)

    def _determine_time_range(self):
        s = self.settings
        met_year_max = int(self.years.max())
        co2_year_max = self._last_full_year(s.co2_concentration_file, "co2")
        dC13_year_max = self._last_full_year(s.co2_dC13_file, "isotope")
        DC14_year_max = self._last_full_year(s.co2_DC14_file, "isotope")

        # dC13/DC14 are NOT allowed to cap the output range: they lag behind
        # the other sources, and _build_dC13/_build_DC14 forward-fill their
        # last known value for any year past their native coverage rather
        # than truncating the whole dataset for it.
        auto_year_max = min(met_year_max, co2_year_max)
        year_max = s.year_max if s.year_max is not None else auto_year_max
        # Clamp to the met source's own first year (e.g. GLDAS starts 2000,
        # well after the 1940 default) - otherwise this stays at the
        # settings default and both the log and the N-deposition file loop
        # in _build_ndep() below would (harmlessly but wastefully) think
        # the range starts decades before any data actually exists.
        year_min = max(s.year_min, int(self.years.min()))

        s.dprint(f"Time coverage per source (last full year): "
                 f"{s.met.name}={met_year_max}, co2={co2_year_max}, "
                 f"dC13={dC13_year_max}, DC14={DC14_year_max}")
        if year_max > dC13_year_max or year_max > DC14_year_max:
            s.dprint(f"co2_dC13/co2_DC14 do not cover {year_max} - "
                     f"forward-filling their last known value for the missing years.")
        s.dprint(f"Using output time range {year_min}-{year_max} "
                 f"({'auto-detected' if s.year_max is None else 'user-specified'} upper bound)")

        self.time_mask = (self.years >= year_min) & (self.years <= year_max)
        if not np.any(self.time_mask):
            raise ValueError(f"No ERA5 timesteps fall inside {year_min}-{year_max}")

        self.out_time_num = self.time_num[self.time_mask]
        self.out_years = self.years[self.time_mask]
        self.out_months = self.months[self.time_mask]
        self.year_min = year_min
        self.year_max = year_max

    # ------------------------------------------------------------------
    # Time-varying fields
    # ------------------------------------------------------------------
    def _read_met_var(self, var):
        """Read one output variable. Usually a straight 1:1 read of the
        source file named `var`, but `met.combine_vars` can map an output
        name to several source variables that get summed - e.g. GLDAS
        splits rain/snow where QUINCY's "rain" means total precipitation."""
        met = self.settings.met
        source_vars = met.combine_vars.get(var, [var])

        data = None
        units = ""
        long_name = met.long_name_fallback.get(var, var)
        for sv in source_vars:
            path = self._met_path(sv)
            with netCDF4.Dataset(path) as ds:
                lat = ds[met.lat_name][:].astype(np.float64)
                lon = ds[met.lon_name][:].astype(np.float64)
                if lat.shape != self._src_lat.shape or lon.shape != self._src_lon.shape or \
                        not np.allclose(lat, self._src_lat) or not np.allclose(lon, self._src_lon):
                    raise ValueError(f"{path} is not on the reference {met.name} grid")
                # source file is on the native (pre-normalization) grid order -
                # reorder to match self.lat/self.lon (see _load_target_grid).
                part = to_nan(ds[sv][self.time_mask, :, :])
                part = part[:, self._lat_order, :][:, :, self._lon_order]
                units = getattr(ds[sv], "units", "")
                if len(source_vars) == 1:
                    long_name = getattr(ds[sv], "long_name", "") or long_name
            if sv in met.unit_override:
                scale, units = met.unit_override[sv]
                part = part * scale
            data = part if data is None else data + part

        comment = None
        if len(source_vars) > 1:
            comment = (f"{var} = " + " + ".join(source_vars) + f" ({met.name} reports these as "
                       f"separate variables; summed here to match QUINCY's 'rain' convention, "
                       f"where rain means total precipitation)")

        if self.land_mask is not None:
            data[:, ~self.land_mask] = np.nan
            ocean_comment = "Ocean gridcells set to NaN (global_land_mask), even though the source reports values there."
            comment = f"{comment} {ocean_comment}" if comment else ocean_comment

        return data, units, long_name, comment

    def _read_static_met_var(self, var):
        """Like _read_met_var, but for a met.static_variables entry: no time
        dimension to slice/index, just a single (lat, lon) read reordered to
        match self.lat/self.lon (see _load_target_grid)."""
        met = self.settings.met
        path = self._met_path(var)
        with netCDF4.Dataset(path) as ds:
            lat = ds[met.lat_name][:].astype(np.float64)
            lon = ds[met.lon_name][:].astype(np.float64)
            if lat.shape != self._src_lat.shape or lon.shape != self._src_lon.shape or \
                    not np.allclose(lat, self._src_lat) or not np.allclose(lon, self._src_lon):
                raise ValueError(f"{path} is not on the reference {met.name} grid")
            data = to_nan(ds[var][:])
            data = data[self._lat_order, :][:, self._lon_order]
            units = getattr(ds[var], "units", "")
            long_name = getattr(ds[var], "long_name", "") or met.long_name_fallback.get(var, var)
        if var in met.unit_override:
            scale, units = met.unit_override[var]
            data = data * scale
        return data, units, long_name

    def _lookup_with_ffill(self, series):
        """Reindex an annual `series` onto self.out_years, forward-filling
        its last known value for any year past its native coverage instead
        of producing NaN there."""
        series = series.sort_index()
        full_index = range(series.index.min(), self.year_max + 1)
        filled = series.reindex(full_index).ffill()
        return filled.reindex(self.out_years).to_numpy(dtype=np.float32)

    def _build_co2(self):
        df = pd.read_csv(self.settings.co2_concentration_file, sep=r"\s+", header=None,
                          names=["year", "co2_mixing_ratio"])
        return self._lookup_with_ffill(df.set_index("year")["co2_mixing_ratio"])

    def _build_dC13(self):
        df = pd.read_csv(self.settings.co2_dC13_file, sep=r"\s+", header=None, names=["year", "co2_dC13"])
        df["year"] = (df["year"] - 0.5).astype(int)
        return self._lookup_with_ffill(df.set_index("year")["co2_dC13"])

    def _build_DC14(self):
        df = pd.read_csv(self.settings.co2_DC14_file, sep=r"\s+", header=None)
        df.columns = ["year", "north", "tropics", "south"]
        df["year"] = (df["year"] - 0.5).astype(int)
        df = df.set_index("year")

        north = self._lookup_with_ffill(df["north"])
        tropics = self._lookup_with_ffill(df["tropics"])
        south = self._lookup_with_ffill(df["south"])

        out = np.empty((len(self.out_years), len(self.lat)), dtype=np.float32)
        lat_band = np.where(self.lat > 30.0, 0, np.where(self.lat > -30.0, 1, 2))
        stacked = np.stack([north, tropics, south], axis=1)  # (time, 3)
        out[:, :] = stacked[:, lat_band]
        return out

    def _ndep_file_for_year(self, year):
        s = self.settings
        if year < 1996:
            return os.path.join(s.root_ndep_path, f"ndep_{year}.nc")
        appendix = "RCP2.6" if s.ndep_projection_scenario == ProjectionScenario.RCP126 else "RCP8.5"
        return os.path.join(s.root_ndep_path, f"ndep_{appendix}_{year}.nc")

    def _build_ndep(self):
        nhx_by_year = {}
        noy_by_year = {}
        lat_idx = lon_idx = None

        for year in range(self.year_min, self.year_max + 1):
            path = self._ndep_file_for_year(year)
            with netCDF4.Dataset(path) as ds:
                if lat_idx is None:
                    src_lat = ds["lat"][:].astype(np.float64)
                    src_lon = ds["lon"][:].astype(np.float64)
                    lat_idx = nearest_index(self.lat, src_lat)
                    lon_idx = nearest_index(self.lon, src_lon, wrap=360.0)
                nhx = to_nan(ds["NHx_deposition"][:])  # (12, lat, lon)
                noy = to_nan(ds["NOy_deposition"][:])
            nhx = np.take(np.take(nhx, lat_idx, axis=1), lon_idx, axis=2)
            noy = np.take(np.take(noy, lat_idx, axis=1), lon_idx, axis=2)
            nhx_by_year[year] = nhx * NDEP_UNIT_CONVERT
            noy_by_year[year] = noy * NDEP_UNIT_CONVERT

        n_time = len(self.out_years)
        nhx_out = np.empty((n_time, len(self.lat), len(self.lon)), dtype=np.float32)
        noy_out = np.empty((n_time, len(self.lat), len(self.lon)), dtype=np.float32)
        for i, (year, month) in enumerate(zip(self.out_years, self.out_months)):
            nhx_out[i] = nhx_by_year[year][month - 1]
            noy_out[i] = noy_by_year[year][month - 1]
        return nhx_out, noy_out

    # ------------------------------------------------------------------
    # Static (lat, lon) fields
    # ------------------------------------------------------------------
    def _read_static_grid(self, path, var, lat_name="lat", lon_name="lon"):
        with netCDF4.Dataset(path) as ds:
            src_lat = ds[lat_name][:].astype(np.float64)
            src_lon = ds[lon_name][:].astype(np.float64)
            data = to_nan(ds[var][:])
            units = getattr(ds[var], "units", "")
            long_name = getattr(ds[var], "long_name", var)
        data = regrid_nearest(data, src_lat, src_lon, self.lat, self.lon)
        return data, units, long_name

    def _build_pdep(self):
        return self._read_static_grid(self.settings.pdep_file, "pdep", lat_name="lat", lon_name="lon")

    def _build_soil_grids(self):
        s = self.settings
        bedrock, _, _ = self._read_static_grid(
            os.path.join(s.soil_grid_dir, "BDRICM.soilgrid.3600.1800.nc"), "BDRICM",
            lat_name="latitude", lon_name="longitude")
        bedrock = bedrock / 100.0  # cm -> m

        taxousda, _, _ = self._read_static_grid(
            os.path.join(s.soil_grid_dir, "TAXOUSDA_10km.soilgrid.3600.1800.nc"), "TAXOUSDA_10km",
            lat_name="latitude", lon_name="longitude")

        taxnwrb, _, _ = self._read_static_grid(
            os.path.join(s.soil_grid_dir, "TAXNWRB.soilgrid.3600.1800.nc"), "TAXNWRB",
            lat_name="latitude", lon_name="longitude")

        return bedrock, taxousda, taxnwrb

    def _build_lithology(self):
        data, _, _ = self._read_static_grid(self.settings.lithology_file, "GLim", lat_name="lat", lon_name="lon")
        return data

    def _build_phosphorus(self):
        s = self.settings
        files = {
            "p_labile_inorganic": "Labile_Inorganic_P.nc",
            "p_secondary_mineral": "Seconday_Mineral__P.nc",
            "p_occluded": "Occluded_P.nc",
            "p_apatite": "Apatite_P.nc",
            "p_organic": "organic_P.nc",
            "p_total": "Total_P.nc",
        }
        var_names = {
            "p_labile_inorganic": "Labile_Inorganic_P",
            "p_secondary_mineral": "Seconday_Mineral__P",
            "p_occluded": "Occluded_P",
            "p_apatite": "Apatite_P",
            "p_organic": "organic_P",
            "p_total": "Total_P",
        }
        out = {}
        for key, fname in files.items():
            data, units, long_name = self._read_static_grid(
                os.path.join(s.phosphorus_dir, fname), var_names[key],
                lat_name="latitude", lon_name="longitude")
            out[key] = (data, units, long_name)
        return out

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    @staticmethod
    def zarr_path_for(output_path):
        root, _ext = os.path.splitext(output_path)
        return root + ".zarr"

    def _nc_chunks_for(self, dims):
        """One full map per chunk: near-instant map reads (used by tests /
        cdo / xarray), best compression ratio. Slow for point timeseries -
        that access pattern is what the Zarr companion store is for."""
        if "lat" in dims or "lon" in dims:
            chunk = {"time": 1, "lat": len(self.lat), "lon": len(self.lon)}
        else:
            chunk = {"time": len(self.out_time_num)}
        return tuple(chunk[d] for d in dims)

    def _zarr_chunks_for(self, dims):
        """Full time axis per small lat/lon tile: one point's whole
        timeseries lives in a single chunk, so a JS/WASM reader needs
        exactly one HTTP range fetch per point query."""
        chunk = {"time": len(self.out_time_num),
                 "lat": min(self.settings.chunk_lat, len(self.lat)),
                 "lon": min(self.settings.chunk_lon, len(self.lon))}
        return tuple(chunk[d] for d in dims)

    def build(self, output_path):
        s = self.settings
        self._load_target_grid()
        self._determine_time_range()

        out_nc = netCDF4.Dataset(output_path, "w", format="NETCDF4")
        out_zarr = zarr.open_group(zarr.storage.LocalStore(self.zarr_path_for(output_path)), mode="w") \
            if s.write_zarr else None

        try:
            out_nc.createDimension("time", len(self.out_time_num))
            out_nc.createDimension("lat", len(self.lat))
            out_nc.createDimension("lon", len(self.lon))

            self._write_coord(out_nc, out_zarr, "time", self.out_time_num, "i8",
                               units=self.time_units, calendar=self.time_calendar,
                               standard_name="time")
            self._write_coord(out_nc, out_zarr, "lat", self.lat, "f8",
                               units="degrees_north", standard_name="latitude")
            self._write_coord(out_nc, out_zarr, "lon", self.lon, "f8",
                               units="degrees_east", standard_name="longitude")

            def write_var(name, dims, data, units, long_name, comment=None):
                nc_chunks = self._nc_chunks_for(dims)
                v = out_nc.createVariable(name, "f4", dims,
                                           zlib=True, complevel=s.zlib_complevel, shuffle=s.shuffle,
                                           chunksizes=nc_chunks, fill_value=np.nan)
                v[:] = data
                v.units = units
                v.long_name = long_name
                if comment:
                    v.comment = comment

                if out_zarr is not None:
                    zarr_chunks = self._zarr_chunks_for(dims)
                    compressor = {"zstd": ZstdCodec(level=3), "gzip": GzipCodec(level=s.zlib_complevel)}[s.zarr_compressor]
                    compressors = [Shuffle(elementsize=4), compressor] if s.shuffle else [compressor]
                    za = out_zarr.create_array(name, shape=data.shape, dtype="f4", chunks=zarr_chunks,
                                                compressors=compressors, fill_value=np.nan,
                                                dimension_names=dims)
                    za[...] = data
                    za.attrs["units"] = units
                    za.attrs["long_name"] = long_name
                    if comment:
                        za.attrs["comment"] = comment

            write_3d = lambda name, data, units, long_name, comment=None: write_var(
                name, ("time", "lat", "lon"), data, units, long_name, comment)
            write_2d = lambda name, data, units, long_name: write_var(name, ("lat", "lon"),
                                                                       data, units, long_name)

            s.dprint(f"Writing {s.met.name} meteorology..")
            for var in s.met.variables:
                data, units, long_name, comment = self._read_met_var(var)
                write_3d(var, data, units, long_name, comment)
                s.dprint(f"  {var} done.")

            if s.met.static_variables:
                s.dprint(f"Writing {s.met.name} static (time-invariant) meteorology..")
                for var in s.met.static_variables:
                    data, units, long_name = self._read_static_met_var(var)
                    write_2d(var, data, units, long_name)
                    s.dprint(f"  {var} done.")

            s.dprint("Writing CO2 concentration / isotopes..")
            write_var("co2_mixing_ratio", ("time",), self._build_co2(),
                      "ppm", "Global atmospheric CO2 mixing ratio")
            write_var("co2_dC13", ("time",), self._build_dC13(),
                      "per mill", "Global atmospheric CO2 delta-13C")
            write_var("co2_DC14", ("time", "lat"), self._build_DC14(),
                       "per mill", "Atmospheric CO2 Delta-14C (zonal: >30N, 30S-30N, <30S)")

            s.dprint("Writing N deposition..")
            nhx, noy = self._build_ndep()
            write_3d("nhx_srf_down", nhx, "mg N m-2 day-1", "NHx deposition (dry+wet)")
            write_3d("noy_srf_down", noy, "mg N m-2 day-1", "NOy deposition (dry+wet)")

            s.dprint("Writing P deposition..")
            pdep, pdep_units, pdep_long = self._build_pdep()
            write_2d("p_dep", pdep, pdep_units or "mg/m2/year", pdep_long or "Annual atmospheric P deposition")

            s.dprint("Writing soil grids..")
            bedrock, taxousda, taxnwrb = self._build_soil_grids()
            write_2d("bedrock_depth", bedrock, "m", "Depth to bedrock")
            write_2d("taxousda", taxousda, "class", "USDA soil taxonomy suborder (SoilGrids TAXOUSDA)")
            write_2d("taxnwrb", taxnwrb, "class", "WRB 2006 soil class (SoilGrids TAXNWRB)")

            s.dprint("Writing lithology..")
            glim = self._build_lithology()
            write_2d("lithology_class", glim, "class", "GLiM lithology class")

            s.dprint("Writing phosphorus pools..")
            for key, (data, units, long_name) in self._build_phosphorus().items():
                write_2d(key, data, units or "gP/m2", long_name or key)

            attrs = {
                "title": f"Global gridded QUINCY forcing ({s.met.name.upper()} 0.5deg grid)",
                "history": f"Created by src/forcing/build_global_forcing_{s.met.name}.py",
                "Conventions": "CF-1.8",
                "source_met_dir": s.met.dir,
                "source_root_ndep_path": s.root_ndep_path,
                "source_pdep_file": s.pdep_file,
                "source_soil_grid_dir": s.soil_grid_dir,
                "source_phosphorus_dir": s.phosphorus_dir,
                "source_lithology_file": s.lithology_file,
                "ndep_projection_scenario": s.ndep_projection_scenario.name,
            }
            for k, v in attrs.items():
                setattr(out_nc, k, v)
            if out_zarr is not None:
                out_zarr.attrs.update(attrs)
        finally:
            out_nc.close()

        s.dprint(f"Done. Wrote {output_path}")
        if out_zarr is not None:
            s.dprint(f"Done. Wrote {self.zarr_path_for(output_path)}")

    def _write_coord(self, out_nc, out_zarr, name, data, dtype, **attrs):
        v = out_nc.createVariable(name, dtype, (name,))
        v[:] = data
        for k, val in attrs.items():
            setattr(v, k, val)
        if out_zarr is not None:
            za = out_zarr.create_array(name, shape=data.shape,
                                        dtype="i8" if dtype == "i8" else "f8",
                                        chunks=data.shape, dimension_names=(name,))
            za[...] = data
            za.attrs.update(attrs)


# ----------------------------------------------------------------------
# Shared CLI plumbing for the per-source driver scripts
# (build_global_forcing_era5.py, build_global_forcing_gldas.py, ...): every
# driver script wants the same aux-data/chunking/zarr flags and differs only
# in which MetSourceConfig it defaults to.
# ----------------------------------------------------------------------
def add_common_args(parser, met: MetSourceConfig):
    parser.add_argument("--output", required=True, help="Output NetCDF path (Zarr is written alongside it)")
    parser.add_argument("--met-dir", default=met.dir,
                         help=f"Directory with {met.name}_<var>_*_monthly.nc files")
    parser.add_argument("--co2-concentration-file", default=GlobalForcingSettings.co2_concentration_file)
    parser.add_argument("--co2-dC13-file", default=GlobalForcingSettings.co2_dC13_file)
    parser.add_argument("--co2-DC14-file", default=GlobalForcingSettings.co2_DC14_file)
    parser.add_argument("--root-ndep-path", default=GlobalForcingSettings.root_ndep_path)
    parser.add_argument("--ndep-scenario", choices=["RCP126", "RCP585"], default="RCP126",
                         help="N-deposition projection scenario used for years >= 1996")
    parser.add_argument("--pdep-file", default=GlobalForcingSettings.pdep_file)
    parser.add_argument("--soil-grid-dir", default=GlobalForcingSettings.soil_grid_dir)
    parser.add_argument("--phosphorus-dir", default=GlobalForcingSettings.phosphorus_dir)
    parser.add_argument("--lithology-file", default=GlobalForcingSettings.lithology_file)
    parser.add_argument("--year-min", type=int, default=GlobalForcingSettings.year_min)
    parser.add_argument("--year-max", type=int, default=None,
                         help="Defaults to the last year fully covered by all sources")
    parser.add_argument("--complevel", type=int, default=GlobalForcingSettings.zlib_complevel)
    parser.add_argument("--chunk-lat", type=int, default=GlobalForcingSettings.chunk_lat,
                         help="Zarr point-access tile size along lat")
    parser.add_argument("--chunk-lon", type=int, default=GlobalForcingSettings.chunk_lon,
                         help="Zarr point-access tile size along lon")
    parser.add_argument("--no-shuffle", action="store_true", help="Disable the HDF5/Zarr byte-shuffle filter")
    parser.add_argument("--no-zarr", action="store_true", help="Skip writing the companion Zarr store")
    parser.add_argument("--zarr-compressor", choices=["zstd", "gzip"], default=GlobalForcingSettings.zarr_compressor,
                         help="zstd: ~5x faster decode, +14%% size - use if the WASM reader links libzstd. "
                              "gzip: use if it's limited to the browser's native DecompressionStream.")
    parser.add_argument("--quiet", action="store_true")
    return parser


def settings_from_args(args, met: MetSourceConfig):
    return GlobalForcingSettings(
        met=dataclasses.replace(met, dir=args.met_dir),
        co2_concentration_file=args.co2_concentration_file,
        co2_dC13_file=args.co2_dC13_file,
        co2_DC14_file=args.co2_DC14_file,
        root_ndep_path=args.root_ndep_path,
        ndep_projection_scenario=ProjectionScenario[args.ndep_scenario],
        pdep_file=args.pdep_file,
        soil_grid_dir=args.soil_grid_dir,
        phosphorus_dir=args.phosphorus_dir,
        lithology_file=args.lithology_file,
        year_min=args.year_min,
        year_max=args.year_max,
        zlib_complevel=args.complevel,
        chunk_lat=args.chunk_lat,
        chunk_lon=args.chunk_lon,
        shuffle=not args.no_shuffle,
        write_zarr=not args.no_zarr,
        zarr_compressor=args.zarr_compressor,
        verbose=not args.quiet,
    )
