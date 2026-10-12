#!/usr/bin/env python3
"""
Write a README.md into every forcing folder under driver_data/, documenting
each climate file: where it comes from, which script made it, how it was
derived, its real units, and known problems.

Each README has two parts:
  - hand-written notes (NOTES below, keyed by folder path relative to
    driver_data/) -- provenance, derivation, caveats;
  - a file table read from the files themselves (variable, units attribute,
    period, grid, size). Folders with many files (raw caches) get a summary
    instead of opening every file.

Rerun after any rebuild so the tables stay current:
  python write_data_readmes.py [--root /path/to/driver_data] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
from collections import Counter
from pathlib import Path

import netCDF4 as nc

DEFAULT_ROOT = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data")
TOOLKIT = "QPy/climate_forcing"
MAX_TABLE_FILES = 40
SKIP_DIRS = {".zarr"}  # never write inside a zarr store

CONVENTIONS = """\
Variable names follow QUINCY's forcing names: `t_air` (mean 2 m temperature),
`t_air_min`/`t_air_max` (monthly mean of daily min/max), `q_air` (specific
humidity), `press_srf` (surface pressure), `precip_total` / `rain` / `snow`,
`swvis_srf_down` / `lw_srf_down` (downward short-/longwave), `wind_air`
(10 m wind speed). The **Units** column is the file's own `units` attribute; where it is
missing or wrong, the notes above say what the values really are."""

NOTES: dict[str, str] = {}

NOTES["."] = f"""\
# driver_data -- climate forcing

Global meteorological forcing for QUINCY, downloaded and processed with
`{TOOLKIT}` (download/ fetches, conversion/ derives; see its README.md).
Every product folder has its own README.md describing each file.

| Folder | Product | Period | Grids | Tmin/Tmax |
|---|---|---|---|---|
| `era5/` | ERA5 monthly means (Copernicus CDS) | 1940-2025 | 0.25deg, 0.5deg (point grids) | no |
| `era5_land/` | ERA5-Land, built from the BGC daily archive + CDS | 1950-2024 (2025 being added) | 0.1, 0.25, 0.5deg cells | yes |
| `gldas/` | GLDAS Noah v2.1 (NASA GES DISC) | monthly 2000-2025, daily 2018-2025 | 0.25, 0.5deg | derived from 3-hourly |
| `terraclimate/` | TerraClimate (Climatology Lab) | 1958-2025 | 4km native, 0.5deg | yes (native) |
| `crujra/` | CRU-JRA v2.5 (CEDA); v3.0 on disk but not used | 1901-2023 | 0.5deg | yes (native) |
| `global_forcing/` | full QUINCY forcing stores (met + CO2 + deposition + soils) | per source | 0.5 / 0.25deg | per source |
| `static/` | QUINCY static inputs: soil texture, bulk density, pH, AWC, soil classes, lithology, soil P | -- | 0.25deg, 0.5deg | -- |
| `ISIMIP_3b/` | ISIMIP3b GCM daily forcing + site extractions | 1850- | 0.5deg | -- |
| `LAI_prescribe/` | prescribed site LAI | -- | site | -- |

Global maps (mean/max/min of the first and last year) and 9-site seasonal
cycles of every gridded file are under `{TOOLKIT}/output/`, in the same
folder layout as here (`*_sites.png`); cross-dataset site comparisons in
`output/site_comparison/`.

Consistency checks for any of these: `{TOOLKIT}/forcing_checks.py`
(tests in `tests/consistency/test_forcing_checks.py`).
"""

# ---------------------------------------------------------------- ERA5
NOTES["era5"] = f"""\
# ERA5

ECMWF ERA5 reanalysis, Copernicus CDS dataset
`reanalysis-era5-single-levels-monthly-means`, downloaded by
`{TOOLKIT}/download/download_era5_monthly.py`.

- `monthly/0.25deg/` native grid, `monthly/0.5deg/` CDS-side regridded
  (`--grid 0.5/0.5`). Both are **point grids** (latitude 90..-90 including
  the poles, longitude 0..359.x), not cell-centred like era5_land/ or
  terraclimate/.
- `raw/` CDS downloads (cache, re-used on rerun).
- `daily/0.5deg/` empty -- reserved for the ERA5 daily-statistics product.
"""
_ERA5_MONTHLY = """\
# ERA5 monthly means -- {res}

Source: CDS `reanalysis-era5-single-levels-monthly-means` (monthly means of
hourly data), 1940-01..2025-12, written by `download/download_era5_monthly.py`
({grid}).

| File | Derived from | Notes |
|---|---|---|
| `era5_t_air_*` | `t2m` | monthly mean 2 m temperature, K. **No Tmin/Tmax**: the monthly-means product has none |
| `era5_q_air_*` | `d2m`, `sp` | Bolton (1980) e(Td), q = 0.622e/(p-0.378e), from the monthly means |
| `era5_press_srf_*` | `sp` | Pa |
| `era5_precip_total_*` | `tp` | x1000 -> mm day-1 (monthly mean of daily totals) |
| `era5_swvis_srf_down_*` | `ssrd` | /86400 -> W m-2 (mean daily accumulation) |
| `era5_lw_srf_down_*` | `strd` | /86400 -> W m-2 |
| `era5_wind_air_*` | `si10` (`10m_wind_speed`) | monthly mean of hourly speed, m s-1. Replaced 2026-10-11 |
| `era5_cloud_cover_*` | `tcc` | fraction 0-1 |

Known issues / history:
- The wind before 2026-10-11 was |mean(u), mean(v)|: monthly averaging of the
  components cancels opposing winds, so it was biased low (by ~30-50% in
  trade-wind/monsoon regions). Its `.bak_vectormean` copies and the raw
  `10m_wind_speed` downloads were deleted 2026-10-12. The ERA5 global forcing
  store built 2026-09-07 still carries the old wind until it is rebuilt.
- `number` and `expver` are CDS artefacts; `expver` marks months from the
  preliminary ERA5T stream (the last ~3 months at download time).
- The 1940-1958 back extension is the 2023 final release (the earlier
  "preliminary" back extension was replaced on CDS).
"""
NOTES["era5/monthly/0.25deg"] = _ERA5_MONTHLY.format(res="0.25deg", grid="native 0.25deg point grid, 721x1440")
NOTES["era5/monthly/0.5deg"] = _ERA5_MONTHLY.format(res="0.5deg", grid="regridded on the CDS side to a 0.5deg point grid, 361x720")
NOTES["era5/raw"] = """\
# ERA5 raw downloads

Cache of CDS requests; the processed files in monthly/ are written from these.

- `era5_monthly_means_<decade>[_grid0.5x0.5]_10m_wind_speed.nc` -- `si10`
  monthly means (0.25deg and 0.5deg), source of the corrected `wind_air`.
- `era5_daily_tmax_<year>_grid0.5x0.5.nc` -- CDS
  `derived-era5-single-levels-daily-statistics`, daily maximum 2 m
  temperature, 1940-1958 only. This download (meant to supply Tmin/Tmax
  before 1959, which the BGC shared archive lacks) was stopped on
  2026-10-11 at 1958; no Tmin was downloaded. Not used by any product yet.
"""
NOTES["era5/daily/0.5deg"] = """\
# ERA5 daily -- 0.5deg

Empty. Reserved for `download/download_era5_daily.py` output (ERA5 daily
statistics); that download was stopped, see ../../raw/README.md.
"""

# ---------------------------------------------------------------- ERA5-Land
NOTES["era5_land"] = f"""\
# ERA5-Land

ECMWF ERA5-Land (land-only rerun of the ERA5 land model at 0.1deg), built by
`{TOOLKIT}/conversion/build_era5land_monthly.py` from

1. the BGC shared daily archive `/Net/Groups/data_BGC/era5_land/e1/0d10_daily`
   (t2m min/max, tp, sp, d2m, ssrd, ws10), and
2. CDS `reanalysis-era5-land-monthly-means` (`cds_monthly/raw/`, via
   `download/download_era5land_monthly_cds.py`) where the archive is missing
   or broken, and
3. ERA5 monthly longwave (`../era5/monthly/0.25deg/`), since ERA5-Land has
   no longwave in the archive before 2000.

- `monthly/{{0.1,0.25,0.5}}deg/` final per-variable files.
- `monthly_yearly_cache/` (per-year intermediates) deleted 2026-10-12; rebuilt on demand.
- `cds_monthly/raw/` CDS monthly means.
"""
_E5L_MONTHLY = """\
# ERA5-Land monthly -- {res}

Built by `conversion/build_era5land_monthly.py` (stage 1 per year:
`build_era5land_monthly_years.sbatch`; stage 2 merge:
`build_era5land_monthly_merge.sbatch`).

Grid: cell-centred {shape}, latitude **descending** (north to south),
longitude -180..180. {coarsen}
Land only: ocean cells are NaN. `land_fraction` (in every file) is the
fraction of 0.1deg land pixels in the cell.

| File | Derived from | How |
|---|---|---|
| `t_air_min` / `t_air_max` | archive daily t2m min / max | monthly mean of daily extremes, K |
| `precip_total` | archive daily tp | monthly mean of daily totals, mm day-1 |
| `swvis_srf_down` | archive daily ssrd | W m-2. The archive ssrd sits half a pixel off in latitude; rows are pair-averaged onto the grid and coastal gaps filled from the 3x3 neighbourhood. Months the archive does not fully cover (1968-08/09, 1972 from Jan 31) and CDS months that differ from ERA5 by >2% (2024 Jan/Feb, ~45% low on CDS) use ERA5 shortwave instead; flagged per month in `swvis_srf_down_from_era5` |
| `q_air` | archive daily d2m + sp | monthly mean vapour pressure (Bolton) and monthly surface pressure, q = 0.622e/(p-0.378e), kg kg-1 |
| `press_srf` | archive daily sp | Pa. The archive has no sp for some pixels/days (14,681 static land pixels in 2000-2015; 84% missing in 2024); incomplete cell-months are filled with that cell's same-calendar-month mean over complete years, flagged in `press_srf_gapfilled` |
| `wind_air` | archive daily ws10 | monthly mean of daily mean speed, m s-1 |
| `lw_srf_down` | **ERA5** strd monthly means | bilinear from the ERA5 0.25deg point grid to these cell centres, W m-2 |

Known issues:
- **2024 `press_srf` and `q_air` in the current *_1950-2024 files are
  wrong**: the archive's 2024 sp is corrupt (e.g. 58,300 Pa near Guangzhou),
  giving q up to 70% too high. 2024 is being rebuilt from CDS surface
  pressure; these files will be replaced by *_1950-2025 versions.
- 1950 q_air over Antarctica is ~22% above ERA5 (0-7% in later years):
  source data (ERA5-Land spin-up year), left as is.
- Some q_air > saturation in very cold months: monthly means of a
  convex function (Jensen), physically expected, not a bug.
- 2025 (coming): ssrd, d2m, sp from CDS monthly means; t2m min/max, tp,
  ws10 from the archive.
"""
NOTES["era5_land/monthly/0.1deg"] = _E5L_MONTHLY.format(
    res="0.1deg", shape="1800x3600", coarsen="Native ERA5-Land resolution.")
NOTES["era5_land/monthly/0.25deg"] = _E5L_MONTHLY.format(
    res="0.25deg", shape="720x1440",
    coarsen="From 0.1deg by 2x upsampling to 0.05deg then NaN-aware 5x5 block means.")
NOTES["era5_land/monthly/0.5deg"] = _E5L_MONTHLY.format(
    res="0.5deg", shape="360x720", coarsen="From 0.1deg by NaN-aware 5x5 block means.")
for _r in ["0.1deg", "0.25deg", "0.5deg"]:
    NOTES[f"era5_land/monthly_yearly_cache/{_r}"] = f"""\
# ERA5-Land yearly cache -- {_r}

Stage-1 output of `conversion/build_era5land_monthly.py year YEAR`: one
file per year with all monthly variables at {_r}, plus helper fields used
by the merge (`vap_press` Pa, `press_coverage` fraction of complete
pressure, `swvis_from_era5` flag, `land_fraction`). Intermediate only --
use ../../monthly/{_r}/. Safe to delete after the merge (a rerun rebuilds
missing years).
"""
NOTES["era5_land/cds_monthly/raw"] = """\
# ERA5-Land CDS monthly means (raw)

CDS `reanalysis-era5-land-monthly-means`, native 0.1deg **point** grid
(1801 rows, 90..-90), downloaded by `download/download_era5land_monthly_cds.py`.
Accumulated fields are mean daily accumulations (J m-2 per day; /86400 -> W m-2).

- `era5land_monthly_means_ssrd-d2m-sp_2024-2025.nc` -- used for 2025
  shortwave/dewpoint/pressure and 2024 pressure.
- `era5land_monthly_means_strd_<5 years>.nc` -- ERA5-Land longwave,
  1950-2025, to be compared with / replace the ERA5 longwave.
"""

# ---------------------------------------------------------------- GLDAS
NOTES["gldas"] = f"""\
# GLDAS Noah v2.1

NASA GES DISC GLDAS-2.1 Noah, downloaded by `{TOOLKIT}/download/download_gldas.py`
(Earthdata login). Native 0.25deg, latitude -60..90 (**no Antarctica**),
ascending (south to north). Has a real rain/snow split (Noah's own partition).

- `monthly/` 2000-2025 from GLDAS_NOAH025_M.2.1; `daily/` 2018-2025 from
  the 3-hourly GLDAS_NOAH025_3H.2.1.
- `raw/` downloads: `monthly/`, `3hourly/<year>/<doy>/`, plus yearly caches
  `daily_yearly/` and `tmin_tmax_yearly/`.
"""
_GLDAS_MONTHLY = """\
# GLDAS monthly -- {res}

GLDAS_NOAH025_M.2.1 monthly means, 2000-01..2025-12. {grid}

| File | GLDAS field | Units |
|---|---|---|
| `t_air` | Tair_f_inst | K |
| `q_air` | Qair_f_inst | kg kg-1 |
| `press_srf` | Psurf_f_inst | Pa |
| `wind_air` | Wind_f_inst | m s-1 |
| `swvis_srf_down` | SWdown_f_tavg | W m-2 |
| `lw_srf_down` | LWdown_f_tavg | W m-2 |
| `rain` / `snow` | Rainf_tavg / Snowf_tavg | x86400 -> mm day-1 |
| `t_air_min_derived` / `t_air_max_derived` | 3-hourly Tair_f_inst | K, see below |

`t_air_min/max_derived` (`conversion/derive_gldas_tmin_tmax.py`): GLDAS has
no Tmin/Tmax, so each day's min/max is taken over the 8 instantaneous
3-hourly samples, then averaged over the month. The true daily extremes
can fall between samples, so this **underestimates the diurnal range**
slightly (Tmin too warm, Tmax too cold) compared with continuous-record
Tmin/Tmax (CRU-JRA, TerraClimate, ERA5-Land). The `_derived` suffix marks it
as not a native GLDAS product.

Known issues: the precipitation land mask differs from the other
variables in 0.23% of cells; q_air > saturation in 0.13% of values.
"""
NOTES["gldas/monthly/0.25deg"] = _GLDAS_MONTHLY.format(res="0.25deg", grid="Native grid 600x1440.")
NOTES["gldas/monthly/0.5deg"] = _GLDAS_MONTHLY.format(
    res="0.5deg", grid="2x2 block means of the 0.25deg grid (300x720), plain cell average, not area-weighted.")
_GLDAS_DAILY = """\
# GLDAS daily -- {res}

Daily means of GLDAS_NOAH025_3H.2.1 (8 x 3-hourly files per day),
2018-01-01..2025-12-31, from `download/download_gldas.py --products daily_0.25deg`.
{grid}

**The files carry no units attributes.** Values are in the same units as
the monthly files (checked 2026-10-11): t_air K, q_air kg kg-1, press_srf Pa,
wind_air m s-1, swvis_srf_down / lw_srf_down W m-2, rain / snow mm day-1.
"""
NOTES["gldas/daily/0.25deg"] = _GLDAS_DAILY.format(res="0.25deg", grid="Native 600x1440 grid.")
NOTES["gldas/daily/0.5deg"] = _GLDAS_DAILY.format(
    res="0.5deg", grid="2x2 block means of the 0.25deg files (`conversion/coarsen_gldas_daily_to_0.5deg.py`).")

# ---------------------------------------------------------------- TerraClimate
NOTES["terraclimate"] = f"""\
# TerraClimate

Climatology Lab TerraClimate v1.1 (ERA5 anomalies on WorldClim 2
climatologies), monthly, 1/24deg (~4 km), 1958-2025, downloaded by
`{TOOLKIT}/download/download_terraclimate_monthly.py` (no login).
Native variables: tmax, tmin, ppt, srad, vap, ws (+ the DEM). **No
longwave, no pressure, no cloud cover, no daily product.**

- `monthly/4km/` native, `monthly/0.5deg/` coarsened + derived.
- `raw/` yearly downloads (+ `ancillary/terraclim_dem.nc`),
  `derived_yearly_cache/` (per-year press/q, native) deleted 2026-10-12; rebuilt on demand.
"""
NOTES["terraclimate/monthly/4km"] = """\
# TerraClimate monthly -- native 1/24deg (4320x8640)

Native TerraClimate units: tmax/tmin degC, ppt mm per month, srad W m-2,
vap kPa, ws m s-1. Latitude descending.

`terraclimate_press_srf_derived_*` (kPa, from the DEM via the standard
atmosphere, `conversion/derive_terraclimate_humidity_pressure.py`) is
**incomplete**: the final write of that script hung on this filesystem and
the file has no data. The 0.5deg press_srf/q_air are derived directly at
0.5deg instead (see ../0.5deg/README.md).
"""
NOTES["terraclimate/monthly/0.5deg"] = """\
# TerraClimate monthly -- 0.5deg

`conversion/coarsen_terraclimate_to_0.5deg.py`: exact 12x12 block means of
the native 1/24deg grid -> 360x720 cells, latitude descending, lon -180..180.
Units converted to QUINCY conventions in the files.

| File | From | How |
|---|---|---|
| `t_air_min` / `t_air_max` | tmin / tmax | degC -> K. Native monthly mean of daily min/max |
| `t_air` | tmax, tmin | (tmax+tmin)/2, K |
| `rain` | ppt | mm per month -> mm day-1 (total precipitation, not split) |
| `swvis_srf_down` | srad | W m-2 |
| `wind_air` | ws | m s-1 |
| `press_srf` | DEM | **static** (lat, lon), standard-atmosphere pressure from elevation, Pa -- no time variation |
| `q_air` | vap + press_srf | q = 0.622e/(p-0.378e), kg kg-1 |
| `lw_srf_down` | tmin, tmax, q_air, srad, press_srf | **derived** (2026-10-11), see below |

`lw_srf_down` (`conversion/derive_terraclimate_longwave.py`): TerraClimate
has no longwave, so it is derived from TerraClimate's own variables:
Prata (1996) clear-sky emissivity from vapour pressure and temperature,
cloud fraction from shortwave transmissivity c = 1 - Rs/Rso with FAO-56
Rso = (0.75 + 2e-5 z) Ra (Crawford & Duchon 1999), all-sky emissivity
c + (1-c) eps_clr, and lw = eps sigma T_eff^4 with T_eff = tmin + (tmax-tmin)/3.
Validation against ERA5 longwave (land, cos-lat weighted): bias +2.8,
RMSE 14 W m-2, r = 0.99 (2010; the per-year values are in the build log).
Months with top-of-atmosphere insolation < 50 W m-2 (polar night; 18.5% of
land cell-months) cannot use the shortwave cloud estimate and take the
cell's mean cloud fraction over that year's sunlit months; flagged in
`lw_srf_down_cloud_fallback`.

Known issues:
- Polar shortwave exceeds the top-of-atmosphere maximum in places (up to
  8x), and q_air reaches up to 27x saturation at high latitudes -- from
  the source data (WorldClim climatology x ERA5 anomalies). Use with care
  poleward of ~60deg.
- press_srf has no weather variability (static from elevation).
"""

# ---------------------------------------------------------------- CRU-JRA
NOTES["crujra"] = f"""\
# CRU-JRA

CRU-JRA (CRU TS-adjusted JRA-55), 6-hourly 0.5deg, from the CEDA archive,
downloaded and aggregated by `{TOOLKIT}/download/download_crujra.py` (CEDA
token). v2.5 covers 1901-2023, v3.0 1901-2024 (released April 2025).
Grid: 360x720 cells, latitude ascending (south to north), 365-day calendar.

- `monthly/0.5deg/` monthly aggregates, `daily/0.5deg/` daily aggregates
  (`conversion/build_daily_aggregates.py`).
- `raw/v2.5/<var>/`, `raw/v3.0/<var>/` yearly 6-hourly CEDA files;
  `raw/daily_yearly_cache/` (per-year daily intermediates) deleted 2026-10-12.
- The two `crujra_v3.0_tmin/tmax_*_monthly.nc` in this folder are
  byte-identical copies of `monthly/0.5deg/` (older location).

**Only v2.5 is used** (`monthly/0.5deg_quincy/`, the QUINCY-ready files and
the `crujra_global_forcing_0.5deg_1901-2023` store). v3.0 is not used anywhere:
its precipitation lacks the CRU TS bias adjustment (see monthly/0.5deg/README.md).
"""
_CRU_UNITS = """\
Real units (checked 2026-10-11 against the values, not the attributes):

| Variable | Units attribute | Actual |
|---|---|---|
| tmp, tmin, tmax | Degrees Kelvin | K (tmin/tmax: mean of daily min/max) |
| spfh | v3.0 says **"Pa"** | kg kg-1 (attribute wrong, swapped with pres) |
| pres | v3.0 says **"kg/kg"** | Pa (attribute wrong) |
| dswrf | none | W m-2 (6-hourly J m-2 accumulations converted) |
| dlwrf | W/m^2 | W m-2 |
| ugrd, vgrd, wind | m/s | m s-1; wind = speed from 6-hourly u, v |
| pre | mm/6h | see below |
"""
NOTES["crujra/monthly/0.5deg"] = f"""\
# CRU-JRA monthly -- 0.5deg

Monthly aggregates of the 6-hourly CEDA files (state variables averaged).

{_CRU_UNITS}
**Precipitation (`pre`):**
- **v2.5**: monthly total, mm per month (Hainich 2021: 812 mm/yr,
  realistic).
- **v3.0**: **wrong in the CEDA source files** (raw v3.01 6-hourly files
  already sum to 215 mm/yr at Hainich). v3.0/v2.5 annual totals are 0.20-0.27
  depending on the cell (median ~0.25): the per-cell CRU-TS bias adjustment
  of JRA-55 precipitation documented for v2.4/v2.5 is missing. A constant
  factor does **not** fix it -- use v2.5 precipitation. Ocean cells are 0, not NaN.

`crujra_v3.0_wetdays_*`: wet days per month derived from v3.0 `pre`
(`--derive-wetdays`), so it inherits the broken v3.0 precipitation -- do not use.
"""
NOTES["crujra/daily/0.5deg"] = f"""\
# CRU-JRA daily -- 0.5deg

Daily aggregates of v3.0 6-hourly files (`conversion/build_daily_aggregates.py`).

{_CRU_UNITS}
**Precipitation (`pre`)**: v3.0 precipitation is wrong in the CEDA source
(missing CRU-TS bias adjustment, ~0.2-0.27 of v2.5; see
../../monthly/0.5deg/README.md) -- do not use. Ocean cells are 0.

**Broken files**: `crujra_v3.0_tmp_1901-2024_daily.nc` and
`crujra_v3.0_wind_1901-2024_daily.nc` have a fully masked (empty) time
coordinate -- the data are there but dates must be rebuilt (365-day
calendar from 1901-01-01) before use. The `*_2020-2021_daily.nc` files are
small test extracts.
"""
NOTES["crujra/monthly/0.5deg_quincy"] = """\
# CRU-JRA v2.5 monthly -- QUINCY names and units (0.5deg)

`conversion/build_crujra_monthly.py` (jobs: `conversion/build_crujra.sbatch`),
input of `src/forcing/build_global_forcing_crujra.py`. **v2.5 only, 1901-2023**
-- v3.0 is not used anywhere (broken precipitation).

| File | From v2.5 | Units |
|---|---|---|
| `t_air`, `t_air_min`, `t_air_max` | tmp, tmin, tmax (native daily extremes) | K |
| `precip_total` | pre, monthly total / days in month (365-day calendar, Feb = 28) | mm day-1 |
| `q_air` | spfh | kg kg-1 |
| `press_srf` | pres | Pa |
| `swvis_srf_down` / `lw_srf_down` | dswrf / dlwrf | W m-2 |
| `wind_air` | 6-hourly ugrd, vgrd from `raw/v2.5/` | monthly mean of sqrt(u^2+v^2), m s-1 |

Wind is recomputed from the 6-hourly components because speed from the
monthly mean u, v is only ~half of the real mean speed (2000: 1.69 vs
3.29 m/s land mean). Ocean is NaN everywhere (tmp's land mask). Time axis
is the first of each month, days since 1900-01-01, gregorian.
`../../monthly_wind_cache_v2.5/` holds the per-year wind (intermediate).
"""
NOTES["crujra/raw"] = """\
# CRU-JRA raw

`v2.5/<var>/`, `v3.0/<var>/`: original CEDA 6-hourly yearly files
(`crujra.v{2.5,3}.5d.<var>.<year>.365d.noc.nc`, v3.0 precipitation is
release 3.01). The per-year daily intermediates of
`conversion/build_daily_aggregates.py` (`daily_yearly_cache/`) were deleted 2026-10-12.
"""

# ---------------------------------------------------------------- global stores
NOTES["global_forcing"] = """\
# QUINCY global forcing stores

Complete gridded QUINCY input built by `src/forcing/build_global_forcing_<source>.py`
(shared code `src/forcing/global_forcing_builder.py`). Each store exists as
NetCDF (`.nc`) and Zarr (`.zarr`, used by the emulator / weather generator).

Common to all stores:
- Grid normalised to latitude **ascending**, longitude -180..180; ocean NaN
  (`global_land_mask`).
- Met units: q_air **g kg-1**, press_srf **hPa** (converted from the
  monthly files), temperatures K, radiation W m-2, precipitation mm day-1,
  wind m s-1.
- Non-met inputs: `co2_mixing_ratio`, `co2_dC13`, `co2_DC14` (global CO2 and
  isotopes), `nhx_srf_down`, `noy_srf_down` (N deposition, CESM-CAM 0.5deg),
  `p_dep` (P deposition), soil `bedrock_depth`, `taxousda`, `taxnwrb`
  (SoilGrids 0.1deg), `lithology_class`, `p_*` soil P pools (0.5deg) --
  all nearest-neighbour resampled to the store's grid.

| Store | Met source | Temperature | Notes |
|---|---|---|---|
| `era5_global_forcing_0.5deg_1940-2025` | era5/monthly/0.5deg | t_air (mean) only | built before the wind fix (old, biased-low wind); has cloud_cover. Needs a rebuild |
| `gldas_global_forcing_0.5deg_2000-2025` | gldas/monthly/0.5deg | t_air_min/max (derived) | `rain` instead of precip_total; no Antarctica |
| `terraclimate_global_forcing_0.5deg_1958-2025` | terraclimate/monthly/0.5deg | t_air_min/max | press_srf static; lw_srf_down derived (being rebuilt 2026-10-11, previous store without longwave kept as `*.bak_nolw`) |
| `crujra_global_forcing_0.5deg_1901-2023` | crujra/monthly/0.5deg_quincy (v2.5) | t_air_min/max | wind from 6-hourly speed |
| `era5land_global_forcing_{0.5,0.25}deg_1950-2024` | era5_land/monthly/<res> | t_air_min/max | **2024 press_srf/q_air wrong** (see era5_land README); to be replaced by 1950-2025 |

`*.bak` files are older builds kept for comparison; `build*.log` are build logs.
"""

NOTES["static"] = f"""\
# Static (time-invariant) QUINCY inputs

Soil, lithology and soil-phosphorus fields per grid cell, built by
`{TOOLKIT}/conversion/build_static_inputs.py` (`--res` selects the grid;
`<res>/quincy_static_inputs_<res>.nc`); PFT maps are then added to the same
file by `{TOOLKIT}/conversion/build_pft_map.py --res <res>` (rerun it after
rebuilding the soil fields). See ./0.25deg/README.md.
"""
NOTES["static/0.25deg"] = """\
# QUINCY static inputs -- 0.25deg

`quincy_static_inputs_0.25deg.nc`: 720x1440 cells, latitude ascending,
longitude -180..180; off land (land = SoilGrids soil cells) the fill value
(-9999 floats, -1 classes), read as NaN/masked. Stored compactly: classes as
int16, floats rounded to a stated precision and bit-groomed (netCDF
GranularBitRound), zlib level 9 + shuffle -- 6.0 MB on the 0.25 degree grid, 2.1 MB on the 0.5 degree grid.

**Model file:** variables `BLDFIE`, `PHIHOX`, `TAXOUSDA_10km`, `TAXNWRB`,
`Labile_Inorganic_P`, `Seconday_Mineral__P` (sic), `Occluded_P`,
`Apatite_P` and `qmax_org` carry the exact names QUINCY reads from
`bc_quincy_soil.nc` (mo_sb_init.f90, mo_sse_init.f90).

**Namelist (site-run) equivalents** are in the `quincy_namelist` attribute of
each variable: `sand/silt/clay_fraction` (qs_soil_*), `BLDFIE`
(qs_bulk_density), `awc` (qs_soil_awc_prescribe), `PHIHOX` (soil_ph = PHIHOX/10),
the soil classes, the P pools; plus `bedrock_depth` and `lith_glim`.

| Variable | Source | Method |
|---|---|---|
| sand/silt/clay_fraction | SoilGrids v0.5.1 (0.1deg) | trapezoid mean over 0-2 m (7 depths), renormalised to sum 1, block mean |
| BLDFIE, PHIHOX (pH x 10) | SoilGrids | mean of the 7 depths (as in the site tables), block mean |
| awc | SoilGrids AWCh1 (field capacity at -10 kPa) | vol % integrated over 0..min(bedrock, 2 m), mm |
| bedrock_depth | SoilGrids BDRICM | m, capped at 2 m by the product |
| TAXOUSDA_10km, TAXNWRB | SoilGrids | majority class of the 0.1deg cells |
| lith_glim | GLiM v1.0 (0.5deg) | nearest cell |
| *_P pools | Yang et al. 2013 (0.5deg) | nearest cell, land gaps from nearest valid cell; refer to 0-0.5 m (soil_p_depth) |
| qmax_org | **none** | -9999 = QUINCY uses its default 6.5537 |
| land_fraction | SoilGrids | fraction of 0.1deg cells with soil data |
| pft_fraction, veg_fraction, pft_dominant, pft_dominant_natural | CLM4 PFT fractions (0.25 x 0.3125deg) | conservative regrid, CLM4 -> QUINCY PFT mapping (build_pft_map.py) |

Checked against the GLOBAL site table (391 sites, which used the nearest
0.1deg SoilGrids cell): texture, bulk density and pH r = 0.94-0.98 with
median ratio 1.00; P pools median ratio 1.000; lithology class identical at
97% of sites; soil classes identical at 57% (USDA) / 70% (WRB), the
difference being majority-of-block vs single 0.1deg cell. `awc` is ~30%
lower than the site tables' values, whose source is undocumented (they do
not match any SoilGrids AWC definition or depth: AWCh1-3, 1 or 2 m); FLUXNET site tables use
site-specific texture/awc, so they agree less (r 0.3-0.4).

**PFTs.** QUINCY PFT ids (lctlib_quincy_nlct14.def): 1 BEM, 2 BED, 3 BDR,
4 BDS, 5 NE, 6 NS, 7 TeH, 8 TrH, 9 TeP, 10 TrP, 11 TeC, 12 TrC, 13 BSO,
14 UAR. QUINCY runs one PFT per simulation (lnd_veg_nml:plant_functional_type_id);
it reads no PFT map. `pft_dominant` (largest of 1-12) or `pft_dominant_natural`
(largest of 1-8, crops ignored) gives that id per cell; `pft_fraction(pft, lat, lon)`
(sums to 1) allows one run per PFT weighted afterwards. Source: CLM4 PFT
fractions (GEOS-Chem/MEGAN copy), mapped needleleaf evergreen -> NE, needleleaf
deciduous -> NS, broadleaf evergreen tropical -> BEM, temperate -> BED (also
evergreen shrubs), broadleaf deciduous tropical -> BDR, temperate/boreal -> BDS
(also deciduous shrubs; QUINCY has no shrub PFT), C3 grass -> TeH, C4 grass -> TrH,
corn -> TrC, other crops -> TeC, bare -> BSO. Pasture (TeP/TrP) and urban (UAR)
are 0: not separated in the source. `pft_dominant_natural` matches the GLOBAL
site table's PFT at 62% of 376 sites (PLUMBER2: 53%); the site PFT is present
in the cell at 97% of GLOBAL sites (median fraction 0.40), so most mismatches are
mixed cells. A rectangular BDR block in northern Australia comes from the source.

Not included (no gridded source here): LAI_max, stand-replacing year, Nleaf,
SLA, height.
"""
NOTES["static/0.5deg"] = (NOTES["static/0.25deg"]
                          .replace("0.25deg", "0.5deg").replace("720x1440", "360x720")
                          .replace("block mean |", "5x5 block mean of the 0.1deg cells |"))
NOTES["ISIMIP_3b"] = """\
# ISIMIP3b

ISIMIP3b bias-adjusted (W5E5) GCM daily forcing, not produced by the
climate_forcing toolkit.

- `dl/<gcm>/`: downloaded daily global files per GCM (gfdl-esm4,
  ipsl-cm6a-lr, mpi-esm1-2-hr, mri-esm2-0, ukesm1-0-ll), historical 1850-.
- `rechunk/<gcm>/`: the same files rechunked (`*_rc.nc`) for fast point
  extraction.
- `convert_to_quincy/`, `QUINCY_ready/`: Julia scripts and site extractions
  (e.g. DE-Hai, SSP1-2.6/3-7.0/5-8.5) converted to QUINCY's site forcing format.
"""
NOTES["LAI_prescribe"] = """\
# Prescribed LAI

Site LAI time series for QUINCY's prescribed-LAI mode (`DE-Hai/`). Not
climate forcing; not produced by the climate_forcing toolkit.
"""


# ---------------------------------------------------------------- tables
def _time_range(ds) -> str:
    if "time" not in ds.variables or len(ds["time"]) == 0:
        return "static"
    t = ds["time"]
    vals = t[[0, -1]]
    if hasattr(vals, "mask") and vals.mask.any():
        return f"**time axis empty/masked** ({len(t)} steps)"
    d = nc.num2date(vals, t.units, getattr(t, "calendar", "standard"))
    return f"{d[0].year}-{d[0].month:02d} .. {d[1].year}-{d[1].month:02d} ({len(t)})"


def _grid(ds) -> str:
    lat = next((n for n in ("lat", "latitude") if n in ds.variables), None)
    lon = next((n for n in ("lon", "longitude") if n in ds.variables), None)
    if not lat or not lon:
        return ""
    la, lo = ds[lat], ds[lon]
    return f"{len(la)}x{len(lo)}, lat {float(la[0]):.2f}..{float(la[-1]):.2f}"


def file_rows(folder: Path) -> list[str]:
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix == ".nc")
    rows = []
    for p in files:
        size = f"{p.stat().st_size / 1e9:.2f} GB"
        try:
            with nc.Dataset(p) as ds:
                skip = set(ds.dimensions) | {"number", "expver", "time_bnds", "crs"}
                vs = [v for v in ds.variables if v not in skip]
                desc = "<br>".join(
                    f"`{v}` [{getattr(ds[v], 'units', '') or '--'}] {getattr(ds[v], 'long_name', '')}"
                    for v in vs)
                rows.append(f"| `{p.name}` | {desc} | {_time_range(ds)} | {_grid(ds)} | {size} |")
        except Exception as e:  # noqa: BLE001 -- unreadable file is itself worth documenting
            rows.append(f"| `{p.name}` | **unreadable** ({type(e).__name__}) | | | {size} |")
    return rows


def summary(folder: Path) -> str:
    files = [p for p in folder.iterdir() if p.is_file()]
    size = sum(p.stat().st_size for p in files) / 1e9
    pattern = Counter(re.sub(r"\d{4}", "YYYY", p.name) for p in files)
    lines = [f"{len(files)} files, {size:.1f} GB:", ""]
    lines += [f"- `{k}` x {n}" for k, n in pattern.most_common(15)]
    return "\n".join(lines)


def build(folder: Path, root: Path) -> str | None:
    rel = str(folder.relative_to(root)) if folder != root else "."
    note = NOTES.get(rel)
    nc_files = [p for p in folder.iterdir() if p.is_file() and p.suffix == ".nc"]
    if note is None and not nc_files:
        return None
    parts = [note.rstrip() if note else f"# {rel}\n\n(No hand-written notes for this folder yet.)"]
    if nc_files:
        if len(nc_files) > MAX_TABLE_FILES:
            parts.append("## Files\n\n" + summary(folder))
        else:
            parts.append("## Files\n\n| File | Variables [units attribute] | Period (steps) | Grid | Size |\n"
                         "|---|---|---|---|---|\n" + "\n".join(file_rows(folder)))
            parts.append(CONVENTIONS)
    subdirs = sorted(d.name for d in folder.iterdir() if d.is_dir())
    if subdirs:
        parts.append("## Subfolders\n\n" + "\n".join(f"- `{d}/`" for d in subdirs))
    parts.append(f"_Generated {dt.date.today()} by `{TOOLKIT}/write_data_readmes.py` "
                 f"(hand-written notes + file metadata). Edit the notes there, not here._")
    return "\n\n".join(parts) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for dirpath, dirnames, _ in os.walk(args.root):
        dirnames[:] = sorted(d for d in dirnames if Path(d).suffix not in SKIP_DIRS)
        folder = Path(dirpath)
        rel = str(folder.relative_to(args.root)) if folder != args.root else "."
        # raw per-variable / per-model / per-day subfolders are covered by their parent's README
        if rel != "." and any(s in rel.split("/") for s in ("raw", "dl", "rechunk", "derived_yearly_cache")) \
                and rel not in NOTES:
            continue
        text = build(folder, args.root)
        if text is None:
            continue
        if args.dry_run:
            print(f"--- {rel}/README.md ({len(text)} chars)")
        else:
            (folder / "README.md").write_text(text)
            print(f"wrote {rel}/README.md")
    missing = [k for k in NOTES if not (args.root / k).is_dir()]
    if missing:
        print("note: NOTES entries without a folder:", missing)


if __name__ == "__main__":
    main()
