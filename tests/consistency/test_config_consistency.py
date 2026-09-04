import unittest
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(THIS_DIR, os.pardir, os.pardir))

from src.quincy.base.Namelist import Namelist
from src.quincy.base.Paramlist import Paramlist
from src.quincy.base.Lctlib import Lctlib
from src.quincy.base.NamelistTypes import NamelistItem
from tests.consistency.quincy_source_scan import scan_namelist_groups, scan_lctlib_case_keys

# Namelist group -> quincy Fortran source file (relative to the QUINCY root) that
# declares the *main model namelist* NAMELIST block for that group, i.e. the group as
# read from qs.namelist.
NAMELIST_GROUP_SOURCE_FILES = {
    "grid_ctl":          "src/base/mo_jsb_config_class.f90",
    "base_ctl":          "src/base/mo_jsb_config_class.f90",
    "lnd_dist_fire_nml": "src/dist_fire/mo_dfire_config_class.f90",
    "jsb_hydro_nml":     "src/hydrology/mo_hydro_config_class.f90",
    "lnd_phyd_nml":      "src/plant_hydraulics/mo_phyd_config_class.f90",
    "lnd_q_agr_nml":     "src/q_agriculture/mo_q_agr_config_class.f90",
    "lnd_q_assimi_nml":  "src/q_assimilation/mo_q_assimi_config_class.f90",
    "lnd_q_pheno_nml":   "src/q_phenology/mo_q_pheno_config_class.f90",
    "lnd_sb_nml":        "src/q_soil_biogeochemistry/mo_sb_config_class.f90",
    "lnd_q_syl_nml":     "src/q_sylviculture/mo_q_syl_config_class.f90",
    "lnd_veg_nml":       "src/q_vegetation/mo_veg_config_class.f90",
    "jsb_forcing_ctl":   "src/quincy_standalone/mo_qs_forcing.f90",
    "jsb_rad_nml":       "src/radiation/mo_rad_config_class.f90",
    "jsb_sse_nml":       "src/soil_snow_energy/mo_sse_config_class.f90",
    "jsb_seb_nml":       "src/srf_energy_bal/mo_seb_config_class.f90",
    "jsb_turb_nml":      "src/turbulence/mo_turb_config_class.f90",
}

# The parameter-override file: read separately from qs.namelist, via
# parameter_slm_run.list, by mo_qs_set_parameters.f90. Some group names here
# (e.g. lnd_veg_nml) coincide with a main-namelist group name above but declare an
# entirely different (nml_-parameter-override) variable set - the two are scanned and
# compared independently and must not be conflated.
PARAMLIST_SOURCE_FILE = "src/quincy_standalone/mo_qs_set_parameters.f90"

LCTLIB_SOURCE_FILE = "src/base/mo_jsb_lctlib_class.f90"

_BAR = "=" * 88


def _category_field_names(instance):
    """Attribute names of every NamelistItem field on a Namelist/Paramlist category
    instance - these are the literal variable names QPy writes into the namelist
    file, see NamelistWriter.iadd_category / ParamlistWriter.iadd_category."""
    return {name for name, item in vars(instance).items() if isinstance(item, NamelistItem)}


def _print_report(title, source_hint, rows):
    """Print one clearly-delimited report block.

    rows: list of (label, source, status, stale, missing) where status is one of
    "OK", "STALE" or "SKIPPED"; source is the quincy source file the label was
    checked against (or None if skipped); stale/missing are sets of field names.
    """
    print(f"\n{_BAR}\n{title}\n{_BAR}")
    if source_hint:
        print(source_hint)

    for label, source, status, stale, missing in sorted(rows, key=lambda r: r[0]):
        loc = f"  <- {source}" if source else ""
        print(f"  [{status:7s}] {label}{loc}")
        if stale:
            print(f"            stale, quincy no longer recognizes: {', '.join(sorted(stale))}")
        if missing:
            print(f"            not exposed by QPy (informational): {', '.join(sorted(missing))}")

    n = len(rows)
    n_ok = sum(1 for *_, status, _, _ in rows if status == "OK")
    n_stale = sum(1 for *_, stale, _ in rows if stale)
    n_gap = sum(1 for *_, missing in rows if missing)
    n_skipped = sum(1 for *_, status, _, _ in rows if status == "SKIPPED")
    print(f"  ----\n  {n} categories checked: {n_ok} clean match, {n_stale} with stale "
          f"fields, {n_gap} with informational gaps, {n_skipped} skipped")


class Test_ConfigConsistency(unittest.TestCase):
    """Cross-checks QPy's Namelist, Paramlist and Lctlib field/group definitions
    against the real quincy Fortran source at a given QUINCY_ROOT_PATH.

    This does NOT run quincy - it is a static contract check that is meant to catch
    the same class of bugs that previously only surfaced as a live Fortran runtime
    crash ("Cannot match namelist object name ...") or as silently-ignored config
    (wrong NAMELIST group name), by directly comparing QPy's field names against the
    NAMELIST / lctlib CASE declarations quincy's Fortran source actually contains.

    Each of the three checks below (Namelist / Paramlist / Lctlib) is independent -
    they read from different quincy source files and are reported in their own
    clearly-separated block, so a failure in one immediately shows which of the three
    file/option sets it belongs to.
    """

    def init(self):
        if 'QUINCY' in os.environ:
            self.QUINCY_ROOT_PATH = os.environ.get("QUINCY")
        else:
            print("Environmental variable QUINCY is not defined")
            print("Please set QUINCY to the directory of your quincy root path")
            exit(99)

    def test_namelist_categories_match_quincy_source(self):
        self.init()

        namelist = Namelist()
        rows = []
        stale_categories = {}

        for cat_str in vars(namelist):
            cat = getattr(namelist, cat_str)
            cat_name = type(cat).__name__

            src_rel_path = NAMELIST_GROUP_SOURCE_FILES.get(cat_name.lower())
            if src_rel_path is None:
                rows.append((cat_name, None, "SKIPPED", set(), set()))
                continue

            src_path = os.path.join(self.QUINCY_ROOT_PATH, src_rel_path)
            self.assertTrue(os.path.exists(src_path), f"Expected quincy source file not found: {src_path}")

            fortran_vars = scan_namelist_groups(src_path).get(cat_name.lower())
            self.assertIsNotNone(
                fortran_vars,
                f"Could not find 'NAMELIST /{cat_name.lower()}/' in {src_rel_path} - "
                f"has quincy renamed or moved this group?")

            qpy_fields = _category_field_names(cat)
            stale = {v for v in qpy_fields if v.lower() not in fortran_vars}
            missing = fortran_vars - {v.lower() for v in qpy_fields}

            if stale:
                stale_categories[cat_name] = stale
            rows.append((cat_name, src_rel_path, "STALE" if stale else "OK", stale, missing))

        _print_report(
            "NAMELIST  (qs.namelist, matched against each process's mo_*_config_class.f90)",
            None,
            rows)

        self.assertEqual(
            stale_categories, {},
            "QPy Namelist fields no longer recognized by quincy's Fortran NAMELIST declaration "
            "(these WILL crash quincy with 'Cannot match namelist object name ...'):\n" +
            "\n".join(f"  {cat}: {', '.join(sorted(fields))}" for cat, fields in sorted(stale_categories.items())))

    def test_paramlist_categories_match_quincy_source(self):
        self.init()

        paramlist = Paramlist()
        src_path = os.path.join(self.QUINCY_ROOT_PATH, PARAMLIST_SOURCE_FILE)
        self.assertTrue(os.path.exists(src_path), f"Expected quincy source file not found: {src_path}")
        fortran_groups = scan_namelist_groups(src_path)

        rows = []
        stale_categories = {}

        for cat_str in vars(paramlist):
            cat = getattr(paramlist, cat_str)
            cat_name = type(cat).__name__

            fortran_vars = fortran_groups.get(cat_name.lower())
            self.assertIsNotNone(
                fortran_vars,
                f"Could not find 'NAMELIST /{cat_name.lower()}/' in {PARAMLIST_SOURCE_FILE} - "
                f"has quincy renamed or moved this parameter-override group?")

            qpy_fields = _category_field_names(cat)
            stale = {v for v in qpy_fields if v.lower() not in fortran_vars}
            missing = fortran_vars - {v.lower() for v in qpy_fields}

            if stale:
                stale_categories[cat_name] = stale
            rows.append((cat_name, PARAMLIST_SOURCE_FILE, "STALE" if stale else "OK", stale, missing))

        _print_report(
            "PARAMLIST  (parameter_slm_run.list, matched against mo_qs_set_parameters.f90)",
            "Note: the lctlib_pft1_nml..lctlib_pft8_nml per-PFT override groups further down "
            "in this file are a separate mechanism QPy's Paramlist does not model - out of scope here.",
            rows)

        self.assertEqual(
            stale_categories, {},
            "QPy Paramlist fields no longer recognized by quincy's parameter-override NAMELIST "
            "(these WILL crash quincy when reading parameter_slm_run.list):\n" +
            "\n".join(f"  {cat}: {', '.join(sorted(fields))}" for cat, fields in sorted(stale_categories.items())))

    def test_lctlib_fields_match_quincy_source(self):
        self.init()

        lctlib_src = os.path.join(self.QUINCY_ROOT_PATH, LCTLIB_SOURCE_FILE)
        self.assertTrue(os.path.exists(lctlib_src), f"Expected quincy source file not found: {lctlib_src}")

        valid_keys = scan_lctlib_case_keys(lctlib_src)
        self.assertGreater(len(valid_keys), 0,
                            "Could not find any lctlib CASE(...) keys - has quincy restructured the lctlib reader?")
        # 'nlct' is handled by a dedicated pre-scan loop in Read_lctlib(), not a CASE
        # arm of the per-key SELECT block scan_lctlib_case_keys() extracts from, but it
        # is still a valid keyword the reader accepts.
        valid_keys.add("nlct")

        lctlib = Lctlib()
        sample_item = next(iter(lctlib.data.values()))

        # 'name' is a QPy-only bookkeeping field (the PFT's Python enum name), never
        # written to the .def file - see LctlibWriter.iadd_lctlib.
        qpy_fields = {f for f in vars(sample_item) if f != "name"}

        stale = {f for f in qpy_fields if f.lower() not in valid_keys}
        # 'nlct' is consumed separately by quincy's reader (Lctlib.title_string in QPy), not a per-PFT field.
        missing = {k for k in valid_keys if k not in {f.lower() for f in qpy_fields} and k != "nlct"}

        _print_report(
            "LCTLIB  (lctlib_quincy_nlct14.def, matched against mo_jsb_lctlib_class.f90)",
            None,
            [("Lctlib_Item (all PFTs share the same field set)", LCTLIB_SOURCE_FILE,
              "STALE" if stale else "OK", stale, missing)])

        self.assertEqual(
            stale, set(),
            "QPy Lctlib fields not recognized by quincy's lctlib reader (mo_jsb_lctlib_class.f90) - "
            f"these are silently DROPPED (CASE default branch), not applied: {', '.join(sorted(stale))}")


if __name__ == "__main__":
    unittest.main()
