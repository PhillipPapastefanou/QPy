import os
import sys
import tempfile
import unittest

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

from src.quincy.base.Namelist import Namelist
from src.quincy.base.NamelistTypes import ForcingMode
from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.auxil.find_quincy_paths import QuincyPathFinder
from src.quincy.auxil.check_namelist import (check_namelist, check_namelist_file, assert_valid_namelist,
                                             NamelistCheckError, ERROR, WARNING)


def transient_namelist():
    nlm = Namelist()
    nlm.jsb_forcing_ctl.forcing_mode.value = ForcingMode.TRANSIENT
    nlm.base_ctl.forcing_file_start_yr.value = 1901
    nlm.jsb_forcing_ctl.transient_spinup_years.value = 500
    nlm.jsb_forcing_ctl.simulation_length_number.value = 124
    nlm.base_ctl.output_end_last_day_year.value = 124
    return nlm


def messages(issues, level):
    return [i.message for i in issues if i.level == level]


class Test_NamelistChecks(unittest.TestCase):

    def test_quincy_default_namelist_has_no_errors(self):
        qpf = QuincyPathFinder()
        if not qpf.found_quincy:
            self.skipTest("QUINCY directory not found")
        for issues in (check_namelist_file(qpf.namelist_root_path),
                       check_namelist(NamelistReader(qpf.namelist_root_path).parse())):
            self.assertEqual(messages(issues, ERROR), [])

    def test_valid_transient_namelist(self):
        self.assertEqual(messages(check_namelist(transient_namelist()), ERROR), [])

    def test_netcdf_output_intervals(self):
        nlm = transient_namelist()
        nlm.base_ctl.output_interval_pool.value = nlm.base_ctl.output_interval_pool.value.__class__.DAILY
        nlm.base_ctl.output_interval_flux.value = nlm.base_ctl.output_interval_flux.value.__class__.WEEKLY
        self.assertTrue(any("must be identical" in m for m in messages(check_namelist(nlm), ERROR)))

    def test_soil_layers_and_texture(self):
        nlm = transient_namelist()
        nlm.jsb_sse_nml.quincy_nsoil_e.value = 10
        nlm.jsb_hydro_nml.quincy_nsoil_w.value = 25
        nlm.jsb_sse_nml.l_soil_texture.value = False
        nlm.jsb_sse_nml.qs_soil_clay.value = 0.0
        errors = messages(check_namelist(nlm), ERROR)
        for text in ("quincy_nsoil_w (25)", "must be identical", "l_soil_texture", "qs_soil_clay"):
            self.assertTrue(any(text in m for m in errors), text)

    def test_output_years(self):
        nlm = transient_namelist()
        nlm.base_ctl.output_start_first_day_year.value = 50
        nlm.base_ctl.output_end_last_day_year.value = 10
        self.assertTrue(any("output_start_first_day_year" in m for m in messages(check_namelist(nlm), ERROR)))

    def test_transient_years(self):
        nlm = transient_namelist()
        nlm.jsb_forcing_ctl.transient_spinup_start_year.value = 1950
        nlm.jsb_forcing_ctl.transient_spinup_years.value = 30
        issues = check_namelist(nlm)
        self.assertTrue(any("transient_spinup_start_year" in m for m in messages(issues, ERROR)))
        self.assertTrue(any("transient_spinup_years" in m for m in messages(issues, WARNING)))

        # e.g. ISIMIP forcing starting 1850: consistent years are fine, 1901 is only a warning
        nlm = transient_namelist()
        nlm.base_ctl.forcing_file_start_yr.value = 1850
        nlm.jsb_forcing_ctl.transient_spinup_start_year.value = 1850
        nlm.jsb_forcing_ctl.transient_simulation_start_year.value = 1850
        issues = check_namelist(nlm)
        self.assertEqual(messages(issues, ERROR), [])
        self.assertTrue(any("only supports 1901" in m for m in messages(issues, WARNING)))

    def test_fluxnet_timestep_window(self):
        nlm = transient_namelist()
        nlm.base_ctl.fluxnet_type_transient_timestep_output.value = True
        nlm.base_ctl.fluxnet_static_forc_start_yr.value = 2023
        nlm.base_ctl.fluxnet_static_forc_last_yr.value = 2024
        self.assertEqual(messages(check_namelist(nlm), ERROR), [])

        # The whole simulation as timestep output works too (e.g. science/phillip/output/08_...)
        nlm.base_ctl.fluxnet_static_forc_start_yr.value = 1901
        self.assertEqual(messages(check_namelist(nlm), ERROR), [])

        nlm.base_ctl.fluxnet_static_forc_last_yr.value = 2030
        self.assertTrue(any("outside the simulated years" in m for m in messages(check_namelist(nlm), ERROR)))

        nlm.jsb_forcing_ctl.forcing_mode.value = ForcingMode.STATIC
        self.assertTrue(any("needs forcing_mode" in m for m in messages(check_namelist(nlm), ERROR)))

    def test_invalid_value_and_length(self):
        nlm = transient_namelist()
        nlm.jsb_forcing_ctl.n_deposition_scheme.value = "sometimes"
        nlm.base_ctl.sim_siteset_specific.value = "a_much_too_long_siteset_name"
        errors = messages(check_namelist(nlm), ERROR)
        self.assertTrue(any("n_deposition_scheme" in m for m in errors))
        self.assertTrue(any("longer than 20" in m for m in errors))
        with self.assertRaises(NamelistCheckError):
            assert_valid_namelist(nlm)

    def test_options_without_effect(self):
        nlm = transient_namelist()
        nlm.lnd_sb_nml.flag_mycorrhiza.value = False
        nlm.lnd_sb_nml.flag_mycorrhiza_org.value = True
        nlm.lnd_phyd_nml.use_plant_hydraulics.value = False
        nlm.lnd_phyd_nml.use_hydaulic_failure_mort.value = True
        warnings = messages(check_namelist(nlm), WARNING)
        self.assertTrue(any("flag_mycorrhiza_org" in m for m in warnings))
        self.assertTrue(any("use_hydaulic_failure_mort" in m for m in warnings))

    def test_file_values(self):
        with tempfile.NamedTemporaryFile("w", suffix=".namelist", delete=False) as f:
            f.write("&base_ctl\n  output_interval_pool = 'monthly'\n  flag_write_veg_output = yes\n/\n")
        try:
            issues = check_namelist_file(f.name)
        finally:
            os.remove(f.name)
        self.assertTrue(any("flag_write_veg_output" in m for m in messages(issues, ERROR)))
        self.assertTrue(any("can't represent" in m for m in messages(issues, WARNING)))


if __name__ == "__main__":
    unittest.main()
