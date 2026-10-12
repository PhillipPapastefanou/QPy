# Notes 2026-10-10: download status, emulator Tmin/Tmax, GWGEN evaluation

Snapshot of where things stood on 2026-10-10. Data root throughout:
`/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/`.

## 1. Download status

| Dataset | Raw | Processed products | Status |
|---|---|---|---|
| CRU-JRA (3.8 T) | v2.5 + v3.0 raw, per-year daily cache 1901–2024 | daily 0.5° v3.0 1901–2024 (12 vars); monthly 0.5° v2.5 1901–2023 and v3.0 1901–2024 (incl. `wetdays`) | complete; three `*_2020-2021_daily.nc` test leftovers in `crujra/daily/0.5deg/` |
| ERA5 (24 G) | daily Tmax 1940–1954 only, no Tmin | monthly 0.5° + 0.25° 1940–2025 (8 vars, mean `t_air`, has `cloud_cover`) | **daily Tmin/Tmax in progress** (see below) |
| GLDAS (1.5 T) | 3-hourly 2000–2025, monthly 2000–2025, daily-yearly 2000–2025 | monthly 0.5° + 0.25° 2000–2025 (8 vars + derived Tmin/Tmax); daily 0.5° + 0.25° **2018–2025 only** | complete; daily 2000–2017 would need processing only, no download |
| TerraClimate (247 G) | 1958–2025, tmin/tmax/ppt/srad/vap/ws + DEM | 4 km monthly stacks; 0.5° monthly | complete; no longwave, pressure is a static climatology |
| ISIMIP 3b (9 T) | 5 GCMs | `rechunk/`, `QUINCY_ready/` | older, not part of these scripts |

Global forcings in `global_forcing/`: ERA5 1940–2025, GLDAS 2000–2025, TerraClimate
1958–2025 (`.nc` + `.zarr`, plus `.bak` copies). GLDAS and TerraClimate were rebuilt
with `t_air_min`/`t_air_max` on 2026-09-11; ERA5 still has mean `t_air` only.

WFDE5 and GSWP3-W5E5 have download scripts but no data in `driver_data/`.

Archiving candidates: CRU-JRA raw (3.7 T) and GLDAS 3-hourly (~1.5 T) now that
products are built; `.bak` copies in `global_forcing/` once the rebuilds are accepted.

### ERA5 daily Tmin/Tmax

- Previous run (job 7374551) failed after 2d12h on an SSL EOF from
  `cds.climate.copernicus.eu` (transient, not a code bug), with ~14 years done.
- Resubmitted as **job 7472823** on 2026-10-10 20:21 with two changes:
  - `download/download_era5_daily.py` downloads to `<name>.part` and renames on
    success, so an interrupted transfer is never skipped as "already have" on rerun.
  - `download/download_era5_daily_tmintmax_full.sbatch` retries the whole script
    up to 20× with 10 min pauses (the script skips years already on disk).
- Progress at 23:25: 15/172 yearly files (Tmax 1940–1954). 1954 took 32 min end to
  end; the 1955 request had been sitting in CDS's "accepted" queue for 2.5 h.
- Throughput is set by the CDS queue, not by us: 30 min to 4 h per year observed.
  At the slow end the 14-day job limit is not enough; resubmitting resumes.
  Running Tmin and Tmax (or year ranges) as parallel jobs would cut wall time.
- Size: ~200 MB per file, ~35 GB total; monthly aggregates < 1 GB. Scratch had
  37 T free (86% used).

Remaining ERA5 steps once the download is done:
1. Aggregate daily → monthly Tmin/Tmax (a `derive_era5_tmin_tmax_monthly.py`
   modelled on `conversion/derive_gldas_tmin_tmax.py`).
2. Rebuild the ERA5 global forcing with `t_air_min`/`t_air_max`.
3. Retrain the ERA5 emulator (§2).

## 2. Emulator: Tmin/Tmax instead of mean t_air

- `emulator/train_emulator.py` `VARIABLES` now lists `t_air_min`, `t_air_max` in
  place of `t_air`, matching `src/forcing/global_forcing_builder.py` (the daily
  generator's `MonthlyForcingRecord` has only tmin/tmax). The eval plot shows both;
  `emulator/viewer.html` has labels for them.
- Before this change a retrain of GLDAS or TerraClimate would have silently dropped
  temperature (`main()` drops variables missing from the input).
- An ERA5 retrain (jobs 7472824/7472825) was submitted and cancelled before it ran,
  since the ERA5 forcing has no Tmin/Tmax yet. A backup of the old ERA5 weights is in
  `emulator/models/backups/era_backup_2026-09-07/`.
- All three existing emulators (ERA5 2026-09-07, GLDAS 2026-09-07, TerraClimate
  2026-09-08) were trained on mean `t_air`. GLDAS and TerraClimate can be retrained
  now; ERA5 has to wait for §1.

Old ERA5 held-out R² for reference: t_air 0.99, SW 0.99, LW 0.99, q_air 0.98,
noy 0.98, press 0.96, nhx 0.94, wind 0.91, cloud 0.88, precip 0.76.

## 3. Monthly → daily: GWGEN from LPJ-GUESS

### What exists

- **QUINCY cpp_port** `cpp_port/src/monthly_to_daily_forcing.cpp`: committed only on
  quincy branch `feature/plant-hydraulics-physics-mpich-cc` (b533df2f6); the checked-out
  `feature/plant-hydraulics-physics` has build artifacts but no `cpp_port/src`.
  It uses LPJ-GUESS's *simple* scheme: mean-conserving linear interpolation
  (`interp_monthly_means_conserve`) for all continuous variables, and the
  Gerten/Geng Markov rain chain (`prdaily`) with a wet-day count backed out from a
  fixed 5 mm per wet day. No day-to-day weather in temperature, radiation, etc.
- **QPy** `src/weather_generator/src/gwgen.cpp`: an earlier GWGEN port, entirely
  commented out (2745 lines) and unused.
- **LPJ-GUESS** `modules/weathergen.cpp`: working GWGEN (Sommer & Kaplan 2017,
  GMD 10:3771), C++ translation of the Fortran original, MPL-2.0.

### How GWGEN works

Per month: smooth the monthly Tmin/Tmax/cloud/wind to daily means (`rmsmooth`,
mean-preserving), then generate days: wet/dry from a second-order Markov chain,
amounts from a gamma distribution with a generalised-Pareto tail, and correlated
Tmin/Tmax/cloud/wind anomalies conditioned on wet/dry status (globally calibrated
constants from GHCN, no parameter files). The month is regenerated up to 20 times and
the best match on wet-day count, precipitation total and Tmin is kept. Finally
everything is rescaled so monthly Tmean, DTR, precipitation, wind and SW match the
input exactly.

### Variable coverage (our `MonthlyForcingRecord`)

| Variable | GWGEN | Plan |
|---|---|---|
| tmin, tmax | yes | native |
| precip | yes | needs wet-day count: only CRU-JRA has it; otherwise intensity estimate or CRU-JRA wet-day climatology |
| wind | yes | native |
| swvis_srf_down | indirect | SW → cloud fraction → daily cloud → SW, rescaled to monthly mean; ERA5 could pass `cloud_cover` directly |
| q_air | no | derive from GWGEN's RH output + daily T + p, rescale to monthly mean |
| lw_srf_down | no | interpolate (current), optionally adjust for daily T/cloud and rescale |
| press_srf | no | interpolate (current) |
| snow | — | stays 0 (QUINCY partitions) |

Also usable from LPJ-GUESS: `distribute_ndep` (`modules/driver.cpp:313`) places wet
N deposition on generated rain days, but our NHx/NOy have no wet/dry split.

### Isolation work needed

- Remove framework coupling: `Gridcell`, global `date`/`restart`/`state_year`,
  `fail`, `roundoff`, and the **file-global `metvars`** (not thread-safe). Wrap as a
  per-gridcell generator object holding RNG state + residuals.
- Known defects in the LPJ-GUESS code:
  - `normal_01_cdf_inv(double p, double x)` takes `x` by value, so it returns
    nothing; only reached with `thresh_pctl = true` (default false).
  - `if (i == 1000)` inside `for (i = 0; i < 1000; …)` is unreachable, so a failed
    rain draw keeps a stale value silently.
  - `exit(-1)` on unphysical temperatures; should throw.
  - January is smoothed with itself as left boundary (`lm = max(mon-1, 0)`);
    with multi-year input we can pass the real neighbouring months. The cpp_port
    simple generator has the analogous seam (wraps Dec→Jan within one year).

### Benchmark (2026-10-10)

Harness: `gwgen/bench/` (`./build_and_run.sh [n_points]`); compiles
LPJ-GUESS `weathergen.cpp` unchanged against a minimal framework shim, and the
cpp_port simple generator from git, on random GLDAS 0.5° land points
(lat > −60°), 2000–2025, wet days from the 5 mm/day estimate, no RH input.

1987 points (13 skipped for NaN rain) × 26 years = 51,662 cell-years:

| | per cell-year | relative |
|---|---|---|
| GWGEN | 10.5 ms | 259× |
| simple (current cpp_port) | 0.04 ms | 1× |

- Global 0.5° land (86k cells): ~15 CPU-min per year, ~22 CPU-h for 1940–2025.
  Single site, 100 years: ~1 s.
- gprof: **~66% in `rmsmooth`** (deterministic smoothing, 48 calls/year, O(n²)
  passes) → should be computed once per year outside the retry loop, expect ~3×
  (not yet measured). The rest is the retry loop: ~14 attempts per month on average
  (cap 20), so many months end at the cap.
- Conservation: max monthly error Tmean 2.8e-14 K, precip 1.3e-15 rel, SW 1.2e-15 rel.
- Within-month SD of daily Tmax: GWGEN 3.05 K vs simple 1.37 K (simple = seasonal
  slope only). Wet-day fraction 0.33 for both (same wet-day input).
- No crashes or `exit(-1)` across all points. Memory ~6 MB.

### Not yet done

- Realism of the daily statistics: aggregate real daily data (GLDAS daily 2018–2025,
  CRU-JRA daily 1901–2024, ERA5 when available) to monthly, regenerate with both
  generators, compare wet-day frequency, spell lengths, daily variance, lag-1
  autocorrelation, precipitation extremes, Tmin/Tmax–rain correlation.
- Decide which quincy branch carries the cpp_port integration.
