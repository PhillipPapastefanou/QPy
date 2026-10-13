"""Consistency checks for a QUINCY namelist.

Python translation of the option checks of QUINCY's run scripts
(contrib/site_level/prepare_sim_quincy.sh, contrib/test_bed/run_quincy_testbed.sh,
contrib/site_level/run_sim_quincy.sh: allowed values, maximum lengths,
transient / fluxnet-timestep / EucFACE constraints, mycorrhiza flags), of the
option combinations QUINCY itself aborts on at start-up (marked "Fortran"),
and a few checks QPy users ran into (marked "QPy").

NamelistWriter.export runs these checks on every namelist QPy writes.

ERROR   QUINCY or prepare_sim_quincy.sh would refuse or silently change this
WARNING allowed, but most likely not what you want (e.g. an option without effect)

Usage in a runscript (NamelistWriter does this already):

    from src.quincy.auxil.check_namelist import check_namelist, assert_valid_namelist
    issues = check_namelist(namelist)       # list of Issue
    assert_valid_namelist(namelist)         # prints warnings, raises on errors

From the command line, for namelist files:

    python src/quincy/auxil/check_namelist.py path/to/qs.namelist [...]
"""
import enum
import os
import sys
from dataclasses import dataclass

if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, os.pardir))

from src.quincy.base.Namelist import Namelist
from src.quincy.base.NamelistTypes import NamelistItem

ERROR = "ERROR"
WARNING = "WARNING"

# Allowed values, as validated by prepare_sim_quincy.sh (validate* lists)
ALLOWED_VALUES = {
    ("jsb_forcing_ctl", "forcing_mode"): ["static", "transient"],
    ("base_ctl", "quincy_model_name"): ["land", "plant", "soil", "canopy", "test_canopy", "test_radiation"],
    ("base_ctl", "sim_siteset_specific"): ["none", "eucface_trans"],
    ("lnd_q_assimi_nml", "gs_beta_type"): ["plant", "soil"],
    ("lnd_veg_nml", "veg_bnf_scheme"): ["none", "dynamic", "unlimited", "fixed"],
    ("lnd_sb_nml", "sb_bnf_scheme"): ["none", "dynamic", "unlimited", "fixed"],
    ("jsb_forcing_ctl", "n_deposition_scheme"): ["none", "constant", "dynamic"],
    ("jsb_forcing_ctl", "p_deposition_scheme"): ["none", "constant", "dynamic"],
    ("lnd_q_assimi_nml", "canopy_layer_scheme"): ["standard", "fapar"],
    ("lnd_q_assimi_nml", "canopy_conductance_scheme_string"): ["medlyn", "ballberry"],
    ("lnd_sb_nml", "sb_model_scheme"): ["simple_1d", "jsm"],
    ("lnd_sb_nml", "sb_nloss_scheme"): ["none", "fixed", "dynamic"],
    ("lnd_veg_nml", "veg_dynamics_scheme"): ["none", "population"],
    ("lnd_veg_nml", "biomass_alloc_scheme"): ["fixed", "dynamic", "optimal"],
    ("lnd_veg_nml", "leaf_stoichom_scheme"): ["fixed", "dynamic", "optimal"],
    ("lnd_sb_nml", "sb_adsorp_scheme"): ["eca_full", "eca_part", "eca_none"],
    ("lnd_dist_fire_nml", "dfire_modelname"): ["spitfire"],
    ("base_ctl", "output_interval_pool"): ["timestep", "daily", "weekly", "monthly", "yearly"],
    ("base_ctl", "output_interval_flux"): ["timestep", "daily", "weekly", "monthly", "yearly"],
    ("base_ctl", "output_interval_pool_spinup"): ["none", "daily", "weekly", "monthly", "yearly"],
    ("base_ctl", "output_interval_flux_spinup"): ["none", "daily", "weekly", "monthly", "yearly"],
    ("base_ctl", "output_txt_file_set"): ["default", "all", "basic", "minimal", "plant", "canopy", "soil"],
}

# Character options with a fixed length in QUINCY (mo_jsb_config_class)
MAX_LENGTH = {
    ("base_ctl", "quincy_model_name"): 20,
    ("base_ctl", "sim_siteset_specific"): 20,
}


@dataclass
class Issue:
    level: str
    message: str

    def __str__(self):
        return f"{self.level}: {self.message}"


class NamelistCheckError(ValueError):
    pass


# ----------------------------------------------------------------------
# Namelist -> {group: {name: value}} with plain python values
# ----------------------------------------------------------------------
def _plain(value):
    if isinstance(value, enum.Enum):
        return value.name.lower()
    if isinstance(value, str):
        return value.strip()
    return value


def namelist_values(namelist: Namelist):
    """Values of a QPy Namelist. If it was read from a file, only the entries
    of that file count (the others are not written, see NamelistWriter)."""
    categories = {type(c).__name__.lower(): c for c in vars(namelist).values()}
    only_parsed = any(item.parsed for c in categories.values() for item in vars(c).values()
                      if isinstance(item, NamelistItem))
    values = {}
    for group, cat in categories.items():
        values[group] = {name.lower(): _plain(item.value) for name, item in vars(cat).items()
                         if isinstance(item, NamelistItem) and (item.parsed or not only_parsed)}
    return values


def _parse_raw_value(value):
    value = value.strip().rstrip(",").strip().strip('"').strip("'").strip()
    low = value.lower()
    if low in (".true.", "t"):
        return True
    if low in (".false.", "f"):
        return False
    try:
        number = float(low.replace("d", "e"))
        return int(number) if number.is_integer() and "." not in low and "e" not in low else number
    except ValueError:
        return value


def read_namelist_file_values(path):
    """{group: {name: value}} of a namelist file, names in lower case."""
    values, group = {}, None
    with open(path) as f:
        lines = f.readlines()
    for line in lines:
        line = line.split("!")[0].strip()
        if not line:
            continue
        if line.startswith("&"):
            group = line[1:].strip().lower()
            values.setdefault(group, {})
        elif line.startswith("/"):
            group = None
        elif group is not None and "=" in line:
            name, value = line.split("=", 1)
            values[group][name.strip().lower()] = _parse_raw_value(value)
    return values


# ----------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------
def run_checks(values):
    """All checks on {group: {name: value}}. Returns a list of Issue."""
    issues = []

    def get(group, name, default=None):
        """Value of an entry; strings in lower case (Fortran options are case-insensitive)."""
        value = values.get(group, {}).get(name, default)
        return value.lower() if isinstance(value, str) else value

    def error(msg):
        issues.append(Issue(ERROR, msg))

    def warning(msg):
        issues.append(Issue(WARNING, msg))

    # --- allowed values and lengths (prepare_sim_quincy.sh: validateUserConfigValues)
    for (group, name), allowed in ALLOWED_VALUES.items():
        value = get(group, name)
        if value is None:
            continue
        if not isinstance(value, str) or value not in allowed:
            error(f"&{group} {name}={value!r} is not a valid value (allowed: {', '.join(allowed)})")
    for (group, name), max_len in MAX_LENGTH.items():
        value = get(group, name)
        if isinstance(value, str) and len(value) > max_len:
            error(f"&{group} {name}={value!r} is longer than {max_len} characters")

    # Flags must be logical (prepare_sim_quincy.sh: validateFlags)
    qpy_types = _qpy_types()
    for group, entries in values.items():
        for name, value in entries.items():
            if qpy_types.get((group, name)) is bool and not isinstance(value, bool):
                error(f"&{group} {name}={value!r} must be .TRUE. or .FALSE.")

    # --- output years
    first, last = get("base_ctl", "output_start_first_day_year"), get("base_ctl", "output_end_last_day_year")
    if isinstance(first, (int, float)) and isinstance(last, (int, float)):
        if first < 1:
            error(f"output_start_first_day_year ({first}) must be >= 1")
        if first > last:
            error(f"output_start_first_day_year ({first}) must be <= output_end_last_day_year ({last})")

    model = get("base_ctl", "quincy_model_name")
    transient = get("jsb_forcing_ctl", "forcing_mode") == "transient"
    length = get("jsb_forcing_ctl", "simulation_length_number")
    length_unit = get("jsb_forcing_ctl", "simulation_length_unit", "y")

    # --- PFT (run_quincy_testbed.sh: validatePlantFunctionalTypeID)
    pft = get("lnd_veg_nml", "plant_functional_type_id")
    if isinstance(pft, (int, float)) and not 1 <= pft <= 14:
        error(f"plant_functional_type_id ({pft}) must be between 1 and 14")

    # --- Fortran: quincy_qs_model_driver.f90
    if get("base_ctl", "output_interval_pool") != get("base_ctl", "output_interval_flux") \
            or get("base_ctl", "output_interval_pool_spinup") != get("base_ctl", "output_interval_flux_spinup"):
        error("output_interval_pool/_flux (and *_spinup) must be identical: QUINCY's NetCDF output aborts otherwise")
    if not transient and length_unit != "y":
        error(f"static simulations need simulation_length_unit='y' (is {length_unit!r})")
    if (get("base_ctl", "fluxnet_type_transient_timestep_output") is not True and length_unit == "y"
            and isinstance(length, (int, float)) and isinstance(first, (int, float)) and length < first):
        error(f"simulation_length_number ({length}) is shorter than output_start_first_day_year ({first}): "
              "no output would be written")

    # --- Fortran: soil layers and texture (mo_sse_config_class, mo_hydro_config_class, mo_sse_init, mo_jsb_model_init)
    nsoil_e, nsoil_w = get("jsb_sse_nml", "quincy_nsoil_e"), get("jsb_hydro_nml", "quincy_nsoil_w")
    for name, n in (("quincy_nsoil_e", nsoil_e), ("quincy_nsoil_w", nsoil_w)):
        if isinstance(n, (int, float)) and not 5 <= n <= 20:
            error(f"{name} ({n}) must be between 5 and 20")
    if isinstance(nsoil_e, (int, float)) and isinstance(nsoil_w, (int, float)) and nsoil_e != nsoil_w:
        error(f"quincy_nsoil_e ({nsoil_e}) and quincy_nsoil_w ({nsoil_w}) must be identical")
    tex_sse, tex_hydro = get("jsb_sse_nml", "l_soil_texture"), get("jsb_hydro_nml", "l_soil_texture")
    if isinstance(tex_sse, bool) and isinstance(tex_hydro, bool) and tex_sse != tex_hydro:
        error("l_soil_texture must be the same in &jsb_sse_nml and &jsb_hydro_nml")
    sand, silt, clay = (get("jsb_sse_nml", n) for n in ("qs_soil_sand", "qs_soil_silt", "qs_soil_clay"))
    if isinstance(clay, (int, float)) and clay < 1e-8:
        error(f"qs_soil_clay ({clay}) must be > 0")
    if all(isinstance(v, (int, float)) for v in (sand, silt, clay)) and abs(sand + silt + clay - 1) > 1e-3:
        warning(f"qs_soil_sand + qs_soil_silt + qs_soil_clay = {sand + silt + clay:.4g}, not 1")

    # --- transient simulations
    if transient:
        spinup_years = get("jsb_forcing_ctl", "transient_spinup_years")
        if isinstance(spinup_years, (int, float)):
            if spinup_years < 1:
                error(f"transient_spinup_years ({spinup_years}) must be >= 1")
            elif spinup_years < 100:
                warning(f"transient_spinup_years ({spinup_years}) might be too short for the model to reach "
                        "equilibrium (default 500)")
        spin_start = get("jsb_forcing_ctl", "transient_spinup_start_year")
        spin_end = get("jsb_forcing_ctl", "transient_spinup_end_year")
        sim_start = get("jsb_forcing_ctl", "transient_simulation_start_year")
        # Fortran (quincy_qs_model_driver.f90, NetCDF builds abort): all must equal the first forcing year
        forcing_start = get("base_ctl", "forcing_file_start_yr")
        for name, year in (("transient_spinup_start_year", spin_start), ("transient_simulation_start_year", sim_start)):
            if isinstance(year, (int, float)) and isinstance(forcing_start, (int, float)) and year != forcing_start:
                error(f"{name} ({year}) must equal forcing_file_start_yr ({forcing_start}), the first year of "
                      "the forcing file")
            elif isinstance(year, (int, float)) and year != 1901:
                warning(f"{name} is {year}; prepare_sim_quincy.sh only supports 1901 (fine if your forcing "
                        "file starts in that year)")
        if isinstance(spin_start, (int, float)) and isinstance(spin_end, (int, float)):
            period = spin_end - spin_start + 1
            if period < 2 or period > 49:
                warning(f"the forcing period repeated during spin-up is {period} years "
                        f"(transient_spinup_start_year..transient_spinup_end_year); 2 to 49 years are "
                        "recommended (prepare_sim_quincy.sh resets it to 30)")
        if model is not None and model not in ("land", "plant", "canopy", "soil"):
            error(f"transient simulations are not implemented for quincy_model_name={model!r}")

    # --- timestep output for the last forcing period of fluxnet-type sites
    if get("base_ctl", "fluxnet_type_transient_timestep_output") is True:
        if not transient:
            error("fluxnet_type_transient_timestep_output needs forcing_mode='transient'")
        if model is not None and model not in ("land", "plant"):
            error(f"fluxnet_type_transient_timestep_output is only implemented for the land and plant models, "
                  f"not {model!r}")
        start = get("base_ctl", "fluxnet_static_forc_start_yr")
        end = get("base_ctl", "fluxnet_static_forc_last_yr")
        sim_start = get("jsb_forcing_ctl", "transient_simulation_start_year")
        if all(isinstance(v, (int, float)) for v in (start, end, sim_start, length)) and length_unit == "y":
            sim_end = sim_start + length - 1
            if end < start:
                error(f"fluxnet_static_forc_last_yr ({end}) is before fluxnet_static_forc_start_yr ({start})")
            elif start < sim_start or end > sim_end:
                error(f"the timestep-output window {start}-{end} is outside the simulated years "
                      f"{sim_start}-{sim_end}")

    # --- EucFACE transient simulations
    if get("base_ctl", "sim_siteset_specific") == "eucface_trans":
        if model == "soil":
            error("sim_siteset_specific='eucface_trans' does not work with the QUINCY soil model")
        if get("base_ctl", "fluxnet_type_transient_timestep_output") is True:
            error("sim_siteset_specific='eucface_trans' does not work with fluxnet_type_transient_timestep_output")

    # --- Fortran warning: harvest without harvest in QUINCY standalone
    if get("lnd_q_syl_nml", "flag_stand_harvest") is True and get("lnd_q_syl_nml", "harvest_active_in_qs") is False:
        warning("flag_stand_harvest is .TRUE. but harvest_active_in_qs is .FALSE.: there will be no harvest")

    # --- mycorrhiza (prepare_sim_quincy.sh switches the sub-flags off)
    if get("lnd_sb_nml", "flag_mycorrhiza") is False:
        for name in ("flag_mycorrhiza_org", "flag_mycorrhiza_prim"):
            if get("lnd_sb_nml", name) is True:
                warning(f"{name} is .TRUE. but flag_mycorrhiza is .FALSE. (no effect)")

    # --- QPy: options without effect
    hydraulics = get("lnd_phyd_nml", "use_plant_hydraulics")
    if hydraulics is False:
        if get("lnd_phyd_nml", "use_hydaulic_failure_mort") is True:
            warning("use_hydaulic_failure_mort is .TRUE. but use_plant_hydraulics is .FALSE. (no effect)")
        if get("lnd_q_assimi_nml", "gs_beta_type") == "plant":
            warning("gs_beta_type='plant' (stomata regulated by the plant water status) but "
                    "use_plant_hydraulics is .FALSE.")
    if get("lnd_sb_nml", "sb_model_scheme") == "simple_1d":
        for name in ("flag_sb_jsm_transport", "flag_sb_jsm_litter_input", "flag_sb_jsm_om_sorption"):
            if get("lnd_sb_nml", name) is True:
                warning(f"{name} is .TRUE. but sb_model_scheme='simple_1d' (only used by JSM)")

    # --- QPy: referenced files
    var_list = values.get("base_ctl", {}).get("netcdf_output_var_list")  # paths are case-sensitive
    if isinstance(var_list, str) and var_list not in ("", "not_set") and not os.path.isfile(var_list):
        warning(f"netcdf_output_var_list file does not exist: {var_list}")

    return issues


def _qpy_types():
    """{(group, name): python type} of the entries QPy knows."""
    types = {}
    for cat in vars(Namelist()).values():
        for name, item in vars(cat).items():
            if isinstance(item, NamelistItem):
                types[(type(cat).__name__.lower(), name.lower())] = type(item.value)
    return types


def _qpy_representable(values):
    """Warnings for valid QUINCY values QPy's enums cannot hold: QPy would
    read them as its default instead."""
    issues = []
    for cat in vars(Namelist()).values():
        group = type(cat).__name__.lower()
        for name, item in vars(cat).items():
            if not isinstance(item.value, enum.Enum):
                continue
            value = values.get(group, {}).get(name.lower())
            value = value.lower() if isinstance(value, str) else value
            options = [m.name.lower() for m in type(item.value)]
            if isinstance(value, str) and value not in options \
                    and value in ALLOWED_VALUES.get((group, name.lower()), []):
                issues.append(Issue(WARNING, f"&{group} {name}={value!r} is valid for QUINCY but QPy can't "
                                             f"represent it (QPy knows: {', '.join(options)}); a QPy-written "
                                             "namelist would contain the QPy default instead"))
    return issues


def check_namelist(namelist: Namelist):
    """Check a QPy Namelist object. Returns a list of Issue."""
    return run_checks(namelist_values(namelist))


def check_namelist_file(path):
    """Check a namelist file as QUINCY would read it. Returns a list of Issue."""
    values = read_namelist_file_values(path)
    return run_checks(values) + _qpy_representable(values)


_REPORTED = set()


def assert_valid_namelist(namelist: Namelist, name="namelist"):
    """Print the issues of a Namelist and raise NamelistCheckError if there are errors.
    Each warning is printed only once per process (e.g. not for every member of an ensemble)."""
    issues = check_namelist(namelist)
    for issue in issues:
        if issue.level == ERROR or str(issue) not in _REPORTED:
            _REPORTED.add(str(issue))
            print(f"[check_namelist] {name}: {issue}")
    errors = [i for i in issues if i.level == ERROR]
    if errors:
        raise NamelistCheckError(f"{len(errors)} error(s) in {name}:\n" + "\n".join(str(i) for i in errors))
    return issues


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    n_errors = 0
    for path in sys.argv[1:]:
        issues = check_namelist_file(path)
        n_errors += sum(i.level == ERROR for i in issues)
        print(f"{path}: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  {issue}")
    sys.exit(1 if n_errors else 0)


if __name__ == "__main__":
    main()
