# climate_forcing

Global meteorological forcing datasets for QUINCY, and scripts to pull them
down as monthly NetCDF. This is a data-acquisition toolkit, separate from
`src/forcing/` (which turns a forcing file + CO2/N/P deposition into the
final QUINCY input) — its job is to get you from "raw global reanalysis"
to "monthly per-variable NetCDF" that the rest of the pipeline (or the
weather generator) can consume.

## 1. What QUINCY actually needs

`src/forcing/quinct_input_generator.py` builds the QUINCY sub-daily forcing
table with these columns (`quincy_full_forcing_columns`):

| QUINCY column      | Meaning                    | Unit      |
|---------------------|----------------------------|-----------|
| `swvis_srf_down`   | downwelling shortwave rad. | W m⁻²     |
| `lw_srf_down`      | downwelling longwave rad.  | W m⁻²     |
| `t_air`            | air temperature            | K         |
| `q_air`            | specific humidity          | g/kg      |
| `press_srf`        | surface pressure           | hPa       |
| `rain`             | rainfall                   | mm/day    |
| `snow`             | snowfall                   | mm/day    |
| `wind_air`         | wind speed                 | m/s       |

(CO2/¹³C/¹⁴C and N/P deposition are separate, non-meteorological inputs
already handled elsewhere in `src/forcing/` — out of scope here.)

The repo already runs on **CRU-JRA**: `src/quincy_ui/forcing_prep.py` reads
pre-built monthly files `kmcrujra.v2.4.5d.{var}.1981-2022.365d.nc` with
variables `pre, pres, spfh, tmin, tmax, tmp, tswrf, wetdays, wind, dlwrf`.
That's the baseline this toolkit reproduces and extends.

## 2. Dataset comparison

Five candidate global datasets, all confirmed to still be live and
downloadable as of **2026-09-05** (I checked each access path against the
real server, not just documentation):

| Dataset | Spatial res. | Native time step | Coverage (verified) | Rain/snow split? | Auth | Best for |
|---|---|---|---|---|---|---|
| **CRU-JRA v3.0** | 0.5° | 6-hourly | 1901–**2024** | No (total precip only) | CEDA account + token | Primary — already what the repo uses. Added to CEDA in Apr 2025; v2.5 (to 2023) still available via `--ceda-version 2.5` |
| **GSWP3-W5E5** (ISIMIP3a) | 0.5° | daily | 1901–**2019** | **Yes** (`pr`/`prsn`) | none | ISIMIP-standard cross-check / TRENDY-style runs |
| **ERA5 monthly means** | 0.25° | native monthly | 1940–**near-present (into 2025/2026)** | No | CDS account (free) | Fastest path to recent years; global fallback |
| **WFDE5** (CDS "derived-near-surface-meteorological-variables") | 0.5° | daily/monthly options | 1979–**2024** | **Yes** (`rainfall_flux`/`snowfall_flux`) | CDS account (free) | Bias-corrected, direct rain/snow split, reaches 2024 |
| **TerraClimate** | ~4 km (1/24°) | native monthly | 1958–**2025** | No (`ppt` total only, no LW) | none | Quick gap-fill / sanity check only — **not** self-sufficient (no longwave, no pressure) |
| **MSWX** (GloH2O) | 0.1° | 3-hourly (near-real-time, ~3h latency) | 1979–**present** | No (total precip only) | manual approval → Google Drive (see below) | Most variable-complete single source (all 8 QUINCY met variables + rel. humidity) but **not yet scriptable here** — see §8 |

TerraClimate has **no daily version** (confirmed live 2026-09-05 — it's
monthly by design). The closest same-methodology daily product,
**gridMET** (same group, Climatology Lab/UC Merced), is CONUS + southern
BC only, not global — not usable for most QUINCY sites. For global daily
resolution, use `download_era5_daily.py` (§4) instead.

**Coverage through 2024/2025, concretely:**
- CRU-JRA and GSWP3-W5E5 are historical, versioned products, not rolling
  updates — but CRU-JRA does get periodic new releases: **v3.0 was added
  to the CEDA archive in April 2025 and extends coverage to 2024** (up
  from v2.5's 2023), confirmed live against the archive on 2026-09-05.
  `download_crujra.py` defaults to v3.0; pass `--ceda-version 2.5` if you
  need the older release instead. GSWP3-W5E5 has had no equivalent update
  and still stops at 2019.
- **ERA5 monthly means** and **TerraClimate** are the two datasets here
  that are actively/continuously updated and reach into 2025 today.
- **WFDE5** (via CDS) currently reaches 2024.
- Practical recommendation for a forcing series that needs to run through
  2025: use CRU-JRA v3.0 (or GSWP3-W5E5) for the historical record, and
  splice in ERA5 monthly for the final year CRU-JRA doesn't have yet, the
  same way TRENDY/ISIMIP-adjacent workflows commonly bridge this gap.

### Variable mapping

| QUINCY column | CRU-JRA | GSWP3-W5E5 | ERA5 (raw / derived) | WFDE5 (CDS) | TerraClimate |
|---|---|---|---|---|---|
| `swvis_srf_down` | `dswrf` | `rsds` | `ssrd` | `surface_downwelling_shortwave_radiation` | `srad` |
| `lw_srf_down` | `dlwrf` | `rlds` | `strd` | `surface_downwelling_longwave_radiation` | — (not provided) |
| `t_air` | `tmp` | `tas` | `t2m` | `near_surface_air_temperature` | `tmax`/`tmin` only |
| `q_air` | `spfh` | `huss` | derived from `d2m`+`sp` | `near_surface_specific_humidity` | derived from `vap` (needs pressure elsewhere) |
| `press_srf` | `pres` | `ps` | `sp` | `surface_air_pressure` | — (not provided) |
| `rain` | `pre` (total, unsplit) | `pr` − `prsn` | `tp` (total, unsplit) | `rainfall_flux` (native) | `ppt` (total, unsplit) |
| `snow` | derived (threshold) | `prsn` (native) | derived (threshold) | `snowfall_flux` (native) | `swe` is storage, not a flux — unusable as-is |
| `wind_air` | `ugrd`+`vgrd` → speed | `sfcWind` | `u10`+`v10` → speed | `near_surface_wind_speed` | `ws` |

MSWX isn't in the table above because its exact variable/file naming isn't
public until you have approved Drive access (§8) — but per its BAMS 2022
paper it natively provides air temp, tmin/tmax, surface pressure, both
relative and specific humidity, wind speed, downward shortwave **and**
longwave radiation, and precipitation (total, unsplit) — i.e. every
QUINCY met variable except a native rain/snow split.

## 3. Recommendation

1. **Keep CRU-JRA as the primary source** — it's already integrated
   (`forcing_prep.py`), and this toolkit's `download_crujra.py` reproduces
   the same monthly product from raw CEDA data for years/variables beyond
   what's cached locally.
2. **Use GSWP3-W5E5 for cross-checks / ISIMIP-comparable runs** — it's the
   community-standard alternative and has a native rain/snow split CRU-JRA
   lacks, at the cost of stopping in 2019.
3. **Use ERA5 monthly (or WFDE5) to extend into 2024/2025** — neither
   CRU-JRA nor GSWP3-W5E5 can do this on their own right now.
4. **Treat TerraClimate as a lightweight supplement only** — missing
   longwave radiation and surface pressure make it insufficient alone for
   full QUINCY forcing.

## 4. Layout

```
climate_forcing/
├── README.md                        (this file)
├── requirements.txt
├── NOTES_*.md                       dated working notes (status, open steps)
├── common.py                        shared chunking / aggregation / derivation helpers
│                                     (imported by the scripts in the folders below)
├── write_data_readmes.py            writes the README.md files in driver_data/
├── download/                         fetch raw source data from each provider → monthly
│   ├── download_crujra.py            CEDA CRU-JRA v3.0 (or v2.5) → monthly (primary)
│   ├── download_gswp3_w5e5.py        ISIMIP3a GSWP3-W5E5, point-based → monthly
│   ├── download_era5_monthly.py      CDS ERA5 monthly means (native monthly)
│   ├── download_era5_daily.py        CDS ERA5 daily statistics (incl. real tmax/tmin)
│   ├── download_era5land_monthly_cds.py CDS ERA5-Land monthly means
│   ├── download_wfde5_monthly.py     CDS WFDE5 → monthly
│   ├── download_terraclimate_monthly.py TerraClimate, no auth, native monthly
│   ├── download_gldas.py             NASA GES DISC GLDAS Noah v2.1 → monthly (0.25/0.5deg) + daily (0.25deg)
│   ├── *.sbatch                      Slurm wrappers (retrying long CDS downloads)
│   └── download_mswx.py              not written yet -- blocked on Drive access, see §8
├── conversion/                       reprocess already-downloaded data, no network I/O
│   ├── build_daily_aggregates.py     CRU-JRA 6-hourly → daily (TerraClimate: not applicable, see §9)
│   ├── build_crujra_monthly.py, build_era5land_monthly.py, build_era5_tmintmax_monthly.py,
│   │   derive_gldas_tmin_tmax.py, derive_terraclimate_*.py, coarsen_*.py
│   ├── build_static_inputs.py        static soil/lithology/P file (driver_data/static/)
│   ├── build_pft_map.py              adds QUINCY PFT maps to that file
│   └── *.sbatch                      Slurm wrappers
├── emulator/                         monthly forcing emulator (train, evaluate, predict)
│   ├── train_emulator.py, evaluate_maps.py, emulator_predict.py, export_site_monthly.py, ...
│   ├── viewer.html                   browser viewer (?dataset=era|gldas|...)
│   └── models/                       trained weights: <dataset>/, experiments/, backups/
├── checks/                           consistency checks of built data
│   ├── forcing_checks.py             forcing files/stores (unit tests: QPy/tests/consistency/)
│   └── check_static_inputs.py        static file tests + overview maps
├── plotting/                         maps and site comparisons (output/ and driver_data/static/<res>/plots/)
│   ├── plot_forcing_maps.py, plot_site_cycles.py (+ .sbatch), plot_seasonal_cycles*.py
│   └── plot_static_inputs.py, plot_pft_maps.py
├── gwgen/                            monthly → daily weather generator work (LPJ-GUESS GWGEN)
│   ├── bench/                        C++ benchmark / port check harness
│   └── quincy/                       Hainich QUINCY runs with generated daily forcing
├── logs/, output/                    Slurm logs and plots (not in git)
```

`download/` and `conversion/` are a deliberate split: everything in
`download/` talks to an external service (CEDA, CDS, ISIMIP, GES DISC,
TerraClimate's plain HTTP) and writes the `<out-dir>/raw/` cache;
everything in `conversion/` only *reads* that cache and re-derives new
outputs from it (e.g. daily from 6-hourly) — it never makes a network
request. If a script needs credentials or hits a `requests`/`cdsapi` call,
it belongs in `download/`; if it only opens files already on disk, it
belongs in `conversion/`.

Every script writes one file per variable named
`{dataset}_{variable}_{start}-{end}_monthly.nc` (or `_daily.nc` for
`download_era5_daily.py`/`download_gldas.py`/`build_daily_aggregates.py`) under a
`<out-dir>/<time_resolution>/<spatial_resolution>/` layout, e.g.
`era5/monthly/0.25deg/era5_t_air_1940-2025_monthly.nc` and
`era5/monthly/0.5deg/era5_t_air_1940-2025_monthly.nc` for the regridded
copy. Filenames no longer carry a `_grid...` tag since the resolution is
now encoded in the directory. Raw downloads are cached under
`<out-dir>/raw/` (flat, not resolution-split) and skipped on re-run — this
makes every script cheaply resumable/reprocessable: if a bug is found in
the post-processing step (see the ERA5 unit-conversion note in §7), you
can regenerate corrected outputs from the cache without re-downloading
anything.

Run every script from inside its own folder (e.g. `cd download && python
download_era5_monthly.py ...`, or `cd conversion && python
build_daily_aggregates.py ...`) -- each one adds `climate_forcing/` (its
parent directory) to `sys.path` before importing the shared `common.py`,
so it works from any of the script folders (download/, conversion/,
checks/, plotting/); keep new scripts exactly one folder below
`climate_forcing/` for that reason. All of
them still default `--out-dir` to the shared `driver_data/<dataset>/`
locations regardless of where the script itself lives.

Each script's `DEFAULT_OUT_DIR` now points under
`/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/<dataset>/`
(pass `--out-dir` to override); this replaced an earlier `./data/...`
default used only during initial development. Current per-dataset native
resolutions: ERA5 0.25deg (or 0.5deg if `--grid 0.5/0.5` regridded),
CRU-JRA 0.5deg, TerraClimate 1/24deg (~4km, folder named `4km`),
GSWP3-W5E5 0.5deg.

## 5. Setup

```bash
pip install -r requirements.txt
# only if you'll use ERA5 / WFDE5:
pip install "cdsapi>=0.7.7"
# only if you'll use GSWP3-W5E5:
pip install isimip-client
```

**CEDA (CRU-JRA)** — free account at https://services.ceda.ac.uk/, then
either:
```bash
export CEDA_USERNAME=... CEDA_PASSWORD=...   # script mints a short-lived token itself
# or, to reuse a token you generated at https://services.ceda.ac.uk/account/token/:
export CEDA_TOKEN=...
```

**CDS (ERA5, WFDE5)** — free account at https://cds.climate.copernicus.eu/,
then create `~/.cdsapirc`:
```
url: https://cds.climate.copernicus.eu/api
key: <your personal access token from your CDS profile page>
```

**ISIMIP (GSWP3-W5E5)** and **TerraClimate** — no account needed.

## 6. Examples

All commands below assume `cd download` first (these are all download
scripts — see §9 for the `conversion/` aggregation script).

```bash
# CRU-JRA v3.0, primary source, full record (writes to driver_data/crujra by default)
python download_crujra.py --start-year 1901 --end-year 2024 --derive-wind --derive-wetdays

# ERA5 monthly, global, full record, at CRU-JRA's native 0.5deg grid
# (writes to driver_data/era5 by default; omit --grid to keep native 0.25deg)
python download_era5_monthly.py --start-year 1940 --end-year 2025 --grid "0.5/0.5"

# ERA5 daily, incl. real tmax/tmin (which the monthly product can't give you) --
# start bounded, this is much bigger than the monthly pull (see its docstring)
python download_era5_daily.py --start-year 2015 --end-year 2024 --area 55 5 47 16

# GSWP3-W5E5, single site (matches QuincyInputGenerator's lon/lat convention)
python download_gswp3_w5e5.py --lon 10.472944 --lat 51.080587 \
    --start-year 2010 --end-year 2019

# TerraClimate, global, full record
python download_terraclimate_monthly.py --variables tmax tmin ppt srad ws vap \
    --start-year 1958 --end-year 2025
```

## 7. Known assumptions to verify before a production run

- **ERA5 accumulated-variable units (fixed 2026-09-05, verify if you use
  an older checkout)**: `total_precipitation`, `surface_solar_radiation
  _downwards` and `surface_thermal_radiation_downwards` come back from CDS
  in their raw accumulated form — `tp` in metres/day, `ssrd`/`strd` in
  J/m2/day — not already normalized to QUINCY's mm/day and W/m2. This was
  caught empirically: a "W/m2" global mean of ~14 million is obviously
  wrong, and dividing by seconds/day landed exactly on the physically
  expected ~165 W/m2. `download_era5_monthly.py`'s `write_outputs()` now
  converts these (`tp * 1000`, `ssrd`/`strd` / 86400). If you have output
  files written before this fix, regenerate them — raw chunks are cached,
  so this is a local reprocessing step, no re-download needed (see the
  worked example in the session history / git log for the exact snippet).
  `download_era5_daily.py`'s CDS daily-statistics endpoint has **not**
  been checked for the same issue — verify magnitudes before trusting its
  radiation/precip output.
- **CRU-JRA precip units**: the script sums 6-hourly `pre` to a monthly
  total; confirm this matches the unit convention (`mm/day` mean vs.
  monthly total) that `src/forcing/quinct_input_generator.py` expects
  before wiring the output directly into that pipeline.
- **WFDE5 CDS request schema**: variable *names* are confirmed live on the
  CDS dataset page, but the exact request dict (e.g. a `reference_dataset`
  or `time_aggregation` key) was not confirmed against a working example —
  check "Show API request" on the CDS page before a large pull.
- **CRU-JRA/GSWP3-W5E5 coverage is fixed**, not rolling — re-check the
  CEDA/ISIMIP catalogue pages periodically in case a new version extends
  coverage closer to present.

## 8. MSWX (not yet scriptable)

MSWX (GloH2O, Beck et al., BAMS 2022) is the most variable-complete single
source found in this survey — 0.1°, 3-hourly, near-real-time (~3h
latency), 1979-present, with essentially the full QUINCY variable set
natively (temp, tmin/tmax, pressure, both humidity flavors, wind speed,
downward SW+LW radiation, precip) in one bias-corrected ERA5-derived
product. It's worth having if the access friction is worth it for your
use case.

**Why there's no `download_mswx.py` yet**: unlike every other dataset
here, MSWX has no public API, THREDDS/OPeNDAP endpoint, or catalog entry
(checked: not on Earth Engine, not on Zenodo) — the only distribution
channel is a Google Drive folder, shared only after GloH2O manually
approves a request submitted at https://www.gloh2o.org/mswx/. The folder
structure and file naming aren't published anywhere public, so a script
written without seeing them would just be guessing.

**To get this working**: submit the request form, and once you have the
Drive link, share the folder structure (or even just `ls` a couple of
subfolders) — then a script can be written against the real layout,
likely using `rclone` (Google Drive remote) or `gdown` for the actual
transfer, following the same chunked/cached/resumable pattern as the
other scripts here.

## 9. Daily aggregation (`conversion/build_daily_aggregates.py`)

Everything above produces *monthly* outputs. This script derives *daily*
outputs by resampling each dataset's cached raw source data -- it does
not download anything new, it only reprocesses what `download_crujra.py`
already cached under `<out-dir>/raw/`.

Whether daily is even possible depends on the dataset's native time
resolution, which this script checks per-dataset rather than assuming:

- **CRU-JRA**: native 6-hourly -- daily is a real, meaningful aggregation
  (mean for state variables, sum for `pre`). Reads the same
  `crujra/raw/v3.0/<var>/*.nc` yearly cache the monthly script uses, so it
  only works once that cache is populated (i.e. after running
  `download_crujra.py` at least once for the variables you want daily).
- **TerraClimate**: native monthly -- there is no finer-resolution
  TerraClimate product to derive daily from (confirmed against the public
  THREDDS catalog, see `download_terraclimate_monthly.py`'s docstring).
  The script recognizes this and skips TerraClimate with an explanatory
  message rather than attempting something the source data can't support.

Usage:
```bash
cd conversion
python build_daily_aggregates.py --variables tmp tmax tmin pre --start-year 1901 --end-year 2024
```
