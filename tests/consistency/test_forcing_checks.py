"""
Consistency tests for the monthly climate forcing products.

Three groups:

  Test_ForcingChecks_Synthetic      the generic checks in
                                    climate_forcing/checks/forcing_checks.py pass on
                                    a consistent synthetic forcing and catch
                                    deliberately broken versions of it
                                    (swapped Tmin/Tmax, wrong units, flipped
                                    latitude, shifted months, ...), on a grid
                                    and on sites alike.
  Test_Era5LandBuild_Functions      the array helpers of
                                    climate_forcing/conversion/build_era5land_monthly.py.
  Test_ForcingDatasets_OnDisk       the same checks on the real products.
                                    Datasets that aren't on disk are skipped.
                                    Only runs if FORCING_TEST_ON_DISK=1 is set.

The on-disk tests are configured with environment variables so they can be
pointed at any dataset, resolution, region or set of sites:

  FORCING_TEST_DATASETS  comma list of dataset:res
                         (default era5:0.5deg,gldas:0.5deg,terraclimate:0.5deg,era5land:0.5deg)
  FORCING_TEST_YEARS     comma list of years (default 2010)
  FORCING_TEST_BBOX      lat_min,lat_max,lon_min,lon_max (default: global)
  FORCING_TEST_SITES     semicolon list of lat,lon (default: five sites on
                         different continents)
  FORCING_TEST_REFERENCE dataset:res every dataset is compared with
                         (default era5:0.5deg; empty to disable)
  FORCING_DRIVER_DATA    root folder instead of the default driver_data

Run:  python -m unittest tests.consistency.test_forcing_checks -v
      FORCING_TEST_ON_DISK=1 python -m unittest tests.consistency.test_forcing_checks -v
"""
import os
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

from climate_forcing.checks import forcing_checks as fc
from climate_forcing.conversion import build_era5land_monthly as e5l

DEFAULT_SITES = "50.95,10.45;-2.6,-60.2;62.0,129.7;-33.9,18.4;40.0,-105.0"


def synthetic_forcing(lat=np.arange(75.0, -76.0, -5.0), lon=np.arange(-180.0, 180.0, 10.0),
                      start="2009-01-01", n_months=24):
    """A physically consistent monthly forcing on a small global grid."""
    time = pd.date_range(start, periods=n_months, freq="MS")
    lat2 = lat[None, :, None]
    month = time.month.values[:, None, None]
    season = np.cos(2 * np.pi * (month - 7) / 12.0) * np.sign(lat2) * (np.abs(lat2) / 90.0)
    t_air = 300.0 - 40.0 * (np.abs(lat2) / 90.0) ** 2 + 15.0 * season + 0.0 * lon[None, None, :]
    press = np.full_like(t_air, 98000.0)
    toa = np.stack([fc.toa_monthly_insolation(lat, t.year, t.month) for t in time])[:, :, None]
    coords = {"time": time, "lat": lat, "lon": lon}
    dims = ("time", "lat", "lon")

    def da(values, var):
        return xr.DataArray(np.broadcast_to(values, t_air.shape).astype(np.float64), coords, dims,
                            attrs={"units": fc.CANONICAL_UNITS[var]})

    return {
        "t_air": da(t_air, "t_air"),
        "t_air_min": da(t_air - 5.0, "t_air_min"),
        "t_air_max": da(t_air + 5.0, "t_air_max"),
        "q_air": da(0.7 * fc.saturation_specific_humidity(t_air - 5.0, press), "q_air"),
        "press_srf": da(press, "press_srf"),
        "swvis_srf_down": da(0.6 * toa, "swvis_srf_down"),
        "lw_srf_down": da(np.full_like(t_air, 320.0), "lw_srf_down"),
        "precip_total": da(np.full_like(t_air, 2.0), "precip_total"),
        "wind_air": da(np.full_like(t_air, 3.0), "wind_air"),
    }


def failed(results):
    return {r.name for r in results if not r.passed}


class Test_ForcingChecks_Synthetic(unittest.TestCase):

    def test_consistent_forcing_passes_every_check(self):
        results = fc.run_all_checks(synthetic_forcing())
        self.assertEqual(failed(results), set(), "\n".join(map(str, results)))

    def test_checks_work_unchanged_on_sites_and_boxes(self):
        fields = synthetic_forcing()
        sites = [(50.95, 10.45), (-2.6, -60.2), (62.0, 129.7), (-33.9, 18.4)]
        on_sites = {v: fc.select_locations(da, sites=sites) for v, da in fields.items()}
        self.assertEqual(on_sites["t_air"].dims, ("time", "site"))
        self.assertEqual(failed(fc.run_all_checks(on_sites)), set())
        boxed = {v: fc.select_locations(da, bbox=(30, 60, -20, 40)) for v, da in fields.items()}
        self.assertEqual(failed(fc.run_all_checks(boxed)), set())

    def test_swapped_tmin_tmax_is_caught(self):
        f = synthetic_forcing()
        f["t_air_min"], f["t_air_max"] = f["t_air_max"], f["t_air_min"]
        self.assertIn("temperature_order", failed(fc.run_all_checks(f)))

    def test_humidity_in_g_per_kg_is_caught(self):
        f = synthetic_forcing()
        f["q_air"] = f["q_air"] * 1000.0
        self.assertTrue({"physical_ranges", "humidity_saturation"} <= failed(fc.run_all_checks(f)))

    def test_shortwave_as_daily_joules_is_caught(self):
        f = synthetic_forcing()
        f["swvis_srf_down"] = f["swvis_srf_down"] * 86400.0
        self.assertTrue({"physical_ranges", "shortwave_vs_toa"} <= failed(fc.run_all_checks(f)))

    def test_flipped_latitude_is_caught(self):
        f = {v: da.copy(data=da.values[:, ::-1, :]) for v, da in synthetic_forcing().items()}
        self.assertIn("seasonality", failed(fc.run_all_checks(f)))

    def test_six_month_shift_is_caught(self):
        f = {v: da.copy(data=np.roll(da.values, 6, axis=0)) for v, da in synthetic_forcing().items()}
        self.assertIn("seasonality", failed(fc.run_all_checks(f)))

    def test_non_contiguous_year_selection_is_not_a_gap(self):
        f = {v: da.sel(time=da["time"].dt.year.isin([2009])) for v, da in synthetic_forcing(n_months=36).items()}
        f2 = {v: xr.concat([da, synthetic_forcing(start="2011-01-01", n_months=12)[v]], "time") for v, da in f.items()}
        self.assertTrue(fc.check_time_axis(f2, expected_years=[2009, 2011]).passed)
        self.assertFalse(fc.check_time_axis(f2).passed)

    def test_missing_month_is_caught(self):
        f = synthetic_forcing()
        f["precip_total"] = f["precip_total"].drop_isel(time=5)
        self.assertIn("time_axis", failed(fc.run_all_checks(f)))

    def test_mask_mismatch_is_caught(self):
        f = synthetic_forcing()
        f["wind_air"] = f["wind_air"].copy()
        f["wind_air"][:, 3, 4] = np.nan
        self.assertIn("common_mask", failed(fc.run_all_checks(f)))

    def test_unit_conversions(self):
        def conv(value, units, var):
            return float(fc.to_canonical_units(xr.DataArray([value], attrs={"units": units}), var)[0])
        self.assertAlmostEqual(conv(10.0, "degC", "t_air"), 283.15)
        self.assertAlmostEqual(conv(300.0, "Degrees Kelvin", "t_air"), 300.0)
        self.assertAlmostEqual(conv(1013.25, "hPa", "press_srf"), 101325.0)
        self.assertAlmostEqual(conv(8.0, "g/kg", "q_air"), 0.008)
        self.assertAlmostEqual(conv(1.0 / 86400.0, "kg m-2 s-1", "precip_total"), 1.0)
        with self.assertRaises(ValueError):
            conv(1.0, "furlongs", "wind_air")
        with self.assertRaises(ValueError):
            conv(1.0, "K", "precip_total")

    def test_grid_normalisation(self):
        da = xr.DataArray(np.arange(12.0).reshape(1, 3, 4), dims=("time", "latitude", "longitude"),
                          coords={"time": [0], "latitude": [-10.0, 0.0, 10.0],
                                  "longitude": [0.0, 90.0, 180.0, 270.0]})
        out = fc.normalise_grid(da)
        np.testing.assert_array_equal(out["lat"], [10.0, 0.0, -10.0])
        np.testing.assert_array_equal(out["lon"], [-180.0, -90.0, 0.0, 90.0])
        # the value at (10N, 270E) must still sit at (10N, 90W)
        self.assertEqual(float(out.sel(lat=10.0, lon=-90.0)), float(da.sel(latitude=10.0, longitude=270.0)))

    def test_top_of_atmosphere_insolation(self):
        # equator at equinox ~ S0/pi; polar night 0; pole at June solstice ~ 520-530 W m-2
        self.assertAlmostEqual(float(fc.toa_daily_insolation(0.0, 80)), fc.SOLAR_CONSTANT / np.pi, delta=15)
        self.assertEqual(float(fc.toa_daily_insolation(85.0, 355)), 0.0)
        self.assertTrue(500 < float(fc.toa_daily_insolation(90.0, 172)) < 540)

    def test_coarsening_check(self):
        lat = np.arange(89.95, -90, -0.1)[:50]
        fine = xr.DataArray(np.random.default_rng(0).random((2, 50, 100)), dims=("time", "lat", "lon"))
        fine[:, :5, :5] = np.nan
        for factor in (2.5, 5.0):
            coarse = xr.DataArray(e5l.coarsen(fine.values, factor), dims=("time", "lat", "lon"))
            self.assertTrue(fc.check_coarsening(fine, coarse, atol=1e-5).passed)
            self.assertFalse(fc.check_coarsening(fine, coarse + 0.01, atol=1e-5).passed)
        del lat

    def test_reference_comparison_catches_units(self):
        f = synthetic_forcing()
        self.assertEqual(failed(fc.compare_to_reference(f, f)), set())
        broken = dict(f, precip_total=f["precip_total"] * 1000.0)
        self.assertIn("reference_precip_total", failed(fc.compare_to_reference(broken, f)))


class Test_Era5LandBuild_Functions(unittest.TestCase):

    def test_clean_turns_fill_and_garbage_into_nan(self):
        a = e5l.clean(np.array([1.0, -9999.0, -32767.0, -21837.3, np.inf, 0.0, -50.0]))
        np.testing.assert_array_equal(np.isnan(a), [False, True, True, True, True, False, False])

    def test_month_index_handles_leap_years(self):
        self.assertEqual(len(e5l.month_index(2023)), 365)
        self.assertEqual(len(e5l.month_index(2024)), 366)
        self.assertEqual(int(np.sum(e5l.month_index(2024) == 1)), 29)

    def test_monthly_mean_and_completeness(self):
        months = e5l.month_index(2010)
        daily = np.ones((365, 2, 2), np.float32) * np.arange(365, dtype=np.float32)[:, None, None]
        daily[3, 0, 0] = np.nan
        daily[:, 1, 1] = np.nan
        mean = e5l.monthly_mean(daily, months)
        complete = e5l.monthly_complete(daily, months)
        self.assertAlmostEqual(float(mean[0, 0, 1]), 15.0)
        self.assertAlmostEqual(float(mean[0, 0, 0]), (np.sum(np.arange(31)) - 3) / 30.0, places=4)
        self.assertTrue(np.isnan(mean[0, 1, 1]))
        self.assertFalse(complete[0, 0, 0])
        self.assertTrue(complete[1, 0, 0])

    def test_coarsening_is_a_nan_aware_block_mean(self):
        rng = np.random.default_rng(1)
        x = rng.random((3, 90, 3600)).astype(np.float32)
        x[:, :7, :13] = np.nan
        for factor, shape in ((2.5, (3, 36, 1440)), (5.0, (3, 18, 720))):
            c = e5l.coarsen(x, factor)
            self.assertEqual(c.shape, shape)
            # every coarse cell's value is the mean of the valid fine pixels it covers
            self.assertAlmostEqual(float(np.nanmean(c[:, 5:, 5:])), float(np.nanmean(x[:, 15:, 15:])), places=2)
        np.testing.assert_allclose(e5l.coarsen(x, 5.0)[0, 2, 3], np.nanmean(x[0, 10:15, 15:20]), rtol=1e-6)

    def test_half_row_shift_uses_whichever_row_has_data(self):
        a = np.array([[[1.0, 2.0, np.nan], [np.nan, 4.0, np.nan], [3.0, 6.0, 5.0]]])
        np.testing.assert_array_equal(e5l.pair_mean_rows(a), [[[1.0, 3.0, np.nan], [3.0, 5.0, 5.0]]])

    def test_neighbour_fill_only_where_asked(self):
        a = np.array([[[1.0, 2.0, 3.0], [4.0, np.nan, 6.0], [np.nan, np.nan, np.nan]]])
        where = np.array([[0, 0, 0], [0, 1, 0], [1, 0, 0]], bool)
        out = e5l.fill_from_neighbours(a, where)
        self.assertAlmostEqual(out[0, 1, 1], np.mean([1, 2, 3, 4, 6]))
        self.assertAlmostEqual(out[0, 2, 0], np.mean([4, 6]))       # wraps in longitude
        self.assertTrue(np.isnan(out[0, 2, 1]))                       # not asked for

    def test_humidity_matches_toolkit_formula(self):
        from climate_forcing.common import specific_humidity_from_dewpoint
        td = xr.DataArray(np.array([250.0, 273.15, 290.0, 300.0]))
        p = xr.DataArray(np.array([70000.0, 90000.0, 101325.0, 100000.0]))
        expected = specific_humidity_from_dewpoint(td, p).values
        got = e5l.specific_humidity(e5l.vapour_pressure_from_dewpoint(td.values), p.values)
        np.testing.assert_allclose(got, expected, rtol=1e-12)

    def test_bilinear_is_exact_on_linear_fields_and_wraps(self):
        lat_src = np.arange(90.0, -90.25, -0.25)
        lon_src = np.arange(0.0, 360.0, 0.25)
        field = (2.0 * lat_src[:, None] + 0.0 * lon_src[None, :])[None]
        lat_t, lon_t = e5l.target_axes("0.5deg")
        out = e5l.bilinear_from_point_grid(field, lat_src, lon_src, lat_t, lon_t)
        np.testing.assert_allclose(out[0, :, 0], 2.0 * lat_t, atol=1e-4)
        # longitude-periodic field: value just west of the dateline wraps correctly
        ring = np.cos(np.deg2rad(lon_src))[None, None, :] * np.ones((1, len(lat_src), 1))
        out = e5l.bilinear_from_point_grid(ring, lat_src, lon_src, lat_t, lon_t)
        np.testing.assert_allclose(out[0, 100], np.cos(np.deg2rad(lon_t)), atol=1e-4)

    def test_target_grids(self):
        for res, shape in (("0.1deg", (1800, 3600)), ("0.25deg", (720, 1440)), ("0.5deg", (360, 720))):
            lat, lon = e5l.target_axes(res)
            self.assertEqual((len(lat), len(lon)), shape)
            self.assertAlmostEqual(lat[0] + lat[-1], 0.0)
            self.assertAlmostEqual(lon[0] + lon[-1], 0.0)


def _env_list(name, default, sep=","):
    raw = os.environ.get(name, default)
    return [s.strip() for s in raw.split(sep) if s.strip()]


@unittest.skipUnless(os.environ.get("FORCING_TEST_ON_DISK") == "1",
                     "on-disk forcing checks are opt-in, set FORCING_TEST_ON_DISK=1")
class Test_ForcingDatasets_OnDisk(unittest.TestCase):
    """The generic checks on the real products (each dataset that exists)."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ.get("FORCING_DRIVER_DATA", fc.DRIVER_DATA))
        cls.years = [int(y) for y in _env_list("FORCING_TEST_YEARS", "2010")]
        bbox = _env_list("FORCING_TEST_BBOX", "")
        cls.bbox = [float(b) for b in bbox] if bbox else None
        cls.sites = [tuple(float(x) for x in s.split(",")) for s in _env_list("FORCING_TEST_SITES", DEFAULT_SITES, ";")]
        cls.datasets = [tuple(d.split(":")) for d in
                        _env_list("FORCING_TEST_DATASETS",
                                  "era5:0.5deg,gldas:0.5deg,terraclimate:0.5deg,era5land:0.5deg")]
        ref = os.environ.get("FORCING_TEST_REFERENCE", "era5:0.5deg")
        cls.reference = tuple(ref.split(":")) if ref else None

    def _load(self, dataset, res, sites=None):
        directory = fc.dataset_dir(dataset, res, self.root)
        if not fc.find_variable_files(directory, fc.DATASETS[dataset][1]):
            return None
        return fc.load_monthly(directory, fc.DATASETS[dataset][1], self.years, self.bbox, sites)

    def _run(self, sites):
        ran = 0
        for dataset, res in self.datasets:
            fields = self._load(dataset, res, sites)
            if not fields:
                continue
            ran += 1
            reference = None
            if self.reference and self.reference != (dataset, res):
                reference = self._load(*self.reference, sites=sites)
            for r in fc.run_all_checks(fields, reference, self.years):
                with self.subTest(dataset=dataset, res=res, check=r.name):
                    self.assertTrue(r.passed, str(r))
        if not ran:
            self.skipTest("none of the configured datasets are on disk")

    def test_gridded(self):
        self._run(sites=None)

    def test_sites(self):
        self._run(sites=self.sites)

    def test_era5land_resolutions_are_exact_coarsenings(self):
        """0.25/0.5deg ERA5-Land equal the 0.1deg data block-averaged (per-year cache)."""
        cache = self.root / "era5_land" / "monthly_yearly_cache"
        year = self.years[0]
        files = {res: cache / res / f"era5land_monthly_{year}.nc" for res in ("0.1deg", "0.25deg", "0.5deg")}
        if not all(f.exists() for f in files.values()):
            self.skipTest(f"no ERA5-Land cache for {year}")
        with xr.open_dataset(files["0.1deg"]) as fine_ds:
            for res in ("0.25deg", "0.5deg"):
                with xr.open_dataset(files[res]) as coarse_ds:
                    # lw_srf_down is interpolated per grid, not coarsened
                    for var in ("t_air_max", "precip_total", "swvis_srf_down", "press_srf", "land_fraction"):
                        fine, coarse = fine_ds[var], coarse_ds[var]
                        if var == "land_fraction":
                            fine, coarse = fine.expand_dims("time"), coarse.expand_dims("time")
                        else:
                            fine, coarse = fine.isel(time=[0, 6]), coarse.isel(time=[0, 6])
                        r = fc.check_coarsening(fine.load(), coarse.load(), atol=1e-3 * float(abs(coarse).max()),
                                                name=f"{var}_{res}")
                        with self.subTest(var=var, res=res):
                            self.assertTrue(r.passed, str(r))


if __name__ == "__main__":
    unittest.main()
