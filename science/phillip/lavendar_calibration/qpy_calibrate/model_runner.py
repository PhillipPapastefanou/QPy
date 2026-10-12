"""Wraps QPy's namelist/lctlib/paramlist machinery and QUINCY's run
executable so the rest of the calibration package only has to deal with
"here is a (n_ensemble, n_params) array, go run it and hand back run
directories and success flags".

Reuses the same building blocks as the hand-written scripts under
science/phillip/DE-Hai/runscripts/ (Quincy_Setup, Quincy_Multi_Run,
EnvironmentalInputSite, ApplyDefaultSiteLevel) instead of re-implementing
namelist/lctlib handling.
"""
import glob
import os
import shutil
import subprocess
import time
from copy import deepcopy
from multiprocessing import Pool

import numpy as np

from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.LctlibReader import LctlibReader
from src.quincy.base.PFTTypes import PftQuincy
from src.quincy.base.Paramlist import Paramlist
from src.quincy.base.EnvironmentalInputTypes import ForcingDataset
from src.quincy.base.NamelistTypes import ForcingMode, GsBetaType, OutputIntervalFlux, OutputIntervalPool
from src.quincy.base.EnvironmentalInput import EnvironmentalInputSite
from src.quincy.base.user_git_information import UserGitInformation
from src.quincy.run_scripts.default import ApplyDefaultSiteLevel
from src.quincy.run_scripts.submit import GenerateSlurmScriptArrayBased
from src.quincy.auxil.find_quincy_paths import QuincyPathFinder
from src.sens.base import Quincy_Setup, Quincy_Multi_Run


def _has_nc_output(run_dir):
    """QUINCY writes its *.nc output files directly into its working
    directory (cwd) -- it does NOT create its own nested "output/"
    subfolder. (Existing QPy scripts create a directory *called* "output"
    themselves, one level above the individual run folders, to hold one
    subfolder per ensemble member -- that is a convention of the calling
    script, not something QUINCY itself produces inside a run folder.)"""
    return len(glob.glob(os.path.join(run_dir, "*.nc"))) > 0


def _run_one_local(args):
    """Module-level so multiprocessing can pickle it cheaply (just a binary
    path + a run dir) instead of pickling the whole QuincyModelRunner
    (namelist/lctlib objects) into every worker task."""
    quincy_binary, run_dir = args
    try:
        p = subprocess.Popen([quincy_binary], cwd=run_dir,
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        _, stderr = p.communicate()
        ok = (p.returncode == 0) and _has_nc_output(run_dir)
        if not ok and stderr:
            with open(os.path.join(run_dir, "quincy_stderr.log"), "wb") as f:
                f.write(stderr)
        return ok
    except Exception as exc:
        print(f"[LAVENDAR] run failed in {run_dir}: {exc}")
        return False


class QuincyModelRunner:
    def __init__(self, config):
        self.config = config

        if config.quincy_root:
            self.quincy_root = config.quincy_root
        else:
            finder = QuincyPathFinder()
            if not finder.found_quincy:
                raise RuntimeError(
                    "Could not locate a QUINCY installation. Set 'quincy_root' in the "
                    "calibration config, or export the QUINCY environment variable."
                )
            self.quincy_root = finder.quincy_root_path

        self.quincy_binary = os.path.join(self.quincy_root, "x86_64-gfortran", "bin", "qs.bin")
        if not os.path.isfile(self.quincy_binary):
            raise RuntimeError(f"QUINCY binary not found at {self.quincy_binary}. Compile QUINCY first.")

        self._build_base_setup()

    # ------------------------------------------------------------------
    # Base namelist/lctlib construction (once per calibration run)
    # ------------------------------------------------------------------
    def _build_base_setup(self):
        cfg = self.config
        sim = cfg.simulation

        namelist_root_path = os.path.join(self.quincy_root, "contrib", "namelist", "qs.namelist")
        lctlib_root_path = os.path.join(self.quincy_root, "data", "lctlib_quincy_nlct14.def")

        namelist_base = NamelistReader(namelist_root_path).parse()

        forcing_dataset = getattr(ForcingDataset, sim.forcing_dataset)
        env_input = EnvironmentalInputSite(forcing_mode=ForcingMode.TRANSIENT, forcing_dataset=forcing_dataset)
        namelist_base, self.forcing_file = env_input.parse_single_site(namelist=namelist_base, site=cfg.site)
        if sim.forcing_file_override:
            self.forcing_file = sim.forcing_file_override

        ApplyDefaultSiteLevel(namelist=namelist_base)

        namelist_base.base_ctl.netcdf_output_var_list.value = os.path.join(
            self.quincy_root, "data", "basic_output_variables.txt")

        namelist_base.base_ctl.output_start_first_day_year.value = sim.output_start_first_day_year
        namelist_base.base_ctl.output_end_last_day_year.value = sim.output_end_last_day_year
        namelist_base.jsb_forcing_ctl.transient_simulation_start_year.value = sim.transient_start_year
        namelist_base.jsb_forcing_ctl.transient_spinup_start_year.value = sim.spinup_start_year
        namelist_base.jsb_forcing_ctl.transient_spinup_end_year.value = sim.spinup_end_year
        namelist_base.jsb_forcing_ctl.transient_spinup_years.value = sim.spinup_years
        namelist_base.jsb_forcing_ctl.simulation_length_number.value = sim.simulation_length_years

        namelist_base.base_ctl.output_interval_flux.value = OutputIntervalFlux.DAILY
        namelist_base.base_ctl.output_interval_pool.value = OutputIntervalPool.DAILY

        if sim.output_interval == "fluxnet_timestep":
            # Switches output for the trailing fluxnet_forc_start_yr..
            # fluxnet_forc_last_yr window from daily to half-hourly
            # ("fluxnetdata_*_timestep.nc"). config.py's validation already
            # guarantees a positive leading (ordinary daily-output) window.
            namelist_base.base_ctl.fluxnet_type_transient_timestep_output.value = True
            namelist_base.base_ctl.fluxnet_static_forc_start_yr.value = sim.fluxnet_forc_start_yr
            namelist_base.base_ctl.fluxnet_static_forc_last_yr.value = sim.fluxnet_forc_last_yr

        namelist_base.lnd_phyd_nml.use_plant_hydraulics.value = sim.use_plant_hydraulics
        namelist_base.lnd_phyd_nml.use_hydaulic_failure_mort.value = sim.use_hydraulic_failure_mort
        if sim.use_plant_hydraulics:
            namelist_base.lnd_q_assimi_nml.gs_beta_type.value = GsBetaType.PLANT

        if sim.soil_sand is not None:
            namelist_base.jsb_sse_nml.qs_soil_sand.value = sim.soil_sand
            namelist_base.jsb_sse_nml.qs_soil_silt.value = sim.soil_silt
            namelist_base.jsb_sse_nml.qs_soil_clay.value = 1.0 - sim.soil_sand - sim.soil_silt

        lctlib_base = LctlibReader(lctlib_root_path).parse()

        pft_id = namelist_base.lnd_veg_nml.plant_functional_type_id.value
        self.pft = PftQuincy(pft_id)

        needs_paramlist = any(p.target == "paramlist" for p in cfg.parameters)
        if needs_paramlist:
            namelist_base.base_ctl.set_parameter_values_from_file.value = True
        paramlist_base = Paramlist() if needs_paramlist else None

        # Fail fast on typo'd parameter names instead of silently creating a
        # stray attribute that the writer then ignores (this class of bug
        # exists in a couple of the older, hand-written sweep scripts).
        for p in cfg.parameters:
            if p.target == "lctlib":
                if not hasattr(lctlib_base[self.pft], p.name):
                    raise ValueError(f"Unknown lctlib parameter '{p.name}' for PFT {self.pft.name}.")
            else:
                cat = getattr(paramlist_base, p.category, None)
                if cat is None or not hasattr(cat, p.name):
                    raise ValueError(f"Unknown paramlist parameter '{p.category}.{p.name}'.")

        self.namelist_base = namelist_base
        self.lctlib_base = lctlib_base
        self.paramlist_base = paramlist_base

    # ------------------------------------------------------------------
    # Per-member setup construction
    # ------------------------------------------------------------------
    def _make_setup(self, param_vector, out_dir):
        namelist = deepcopy(self.namelist_base)
        lctlib = deepcopy(self.lctlib_base)
        paramlist = deepcopy(self.paramlist_base) if self.paramlist_base is not None else None

        for spec, value in zip(self.config.parameters, param_vector):
            value = float(value)
            if spec.target == "lctlib":
                setattr(lctlib[self.pft], spec.name, value)
            else:
                item = getattr(getattr(paramlist, spec.category), spec.name)
                item.value = value
                item.parsed = True

        user_git_info = UserGitInformation(self.quincy_root, out_dir, self.config.site)

        return Quincy_Setup(
            folder=out_dir,
            namelist=namelist,
            lctlib=lctlib,
            forcing_path=self.forcing_file,
            user_git_info=user_git_info,
            paramlist=paramlist,
        )

    # ------------------------------------------------------------------
    # Ensemble dispatch
    # ------------------------------------------------------------------
    def run_ensemble(self, members: np.ndarray, iter_dir: str):
        """Write out one QUINCY setup per ensemble member under
        iter_dir/output/<i>, run them all, and report which ones finished
        successfully (returncode 0 and produced output)."""
        output_root = os.path.join(iter_dir, "output")
        multi_run = Quincy_Multi_Run(iter_dir)
        run_dirs = []
        for i, param_vector in enumerate(members):
            out_dir = os.path.join(output_root, str(i))
            setup = self._make_setup(param_vector, out_dir)
            multi_run.add_setup(setup)
            run_dirs.append(out_dir)

        multi_run.generate_files()

        if self.config.run_mode == "local":
            success = self._run_local(run_dirs)
        elif self.config.run_mode == "slurm_array":
            success = self._run_slurm_array(iter_dir, run_dirs)
        else:
            raise ValueError(f"Unknown run_mode '{self.config.run_mode}'")

        return run_dirs, success

    def _run_local(self, run_dirs):
        n_parallel = max(1, min(self.config.n_parallel, len(run_dirs)))
        tasks = [(self.quincy_binary, rd) for rd in run_dirs]
        with Pool(processes=n_parallel) as pool:
            success = pool.map(_run_one_local, tasks)
        return success

    def _run_slurm_array(self, iter_dir, run_dirs):
        n = len(run_dirs)
        # submit.py's generated script does f'{path}wd.txt' with no separator,
        # so `path` must carry a trailing slash.
        path_with_sep = iter_dir if iter_dir.endswith(os.sep) else iter_dir + os.sep

        GenerateSlurmScriptArrayBased(
            # --array=0-{ntasks} is *inclusive* on both ends, and wd.txt has
            # exactly `n` lines (indices 0..n-1), so this must be n-1, not n.
            ntasks=n - 1,
            path=path_with_sep,
            quincy_binary=self.quincy_binary,
            ntasksmax=max(1, min(self.config.n_parallel, n)),
            ram_in_gb=self.config.slurm_ram_in_gb,
            partition=self.config.slurm_partition,
        )

        this_dir = os.path.dirname(os.path.abspath(__file__))
        qpy_root = os.path.abspath(os.path.join(this_dir, os.pardir, os.pardir, os.pardir, os.pardir))
        run_array_script = os.path.join(qpy_root, "src", "quincy", "run_scripts", "run_quincy_array.py")
        if not os.path.isfile(run_array_script):
            raise RuntimeError(f"Could not find run_quincy_array.py at {run_array_script}")
        shutil.copyfile(run_array_script, os.path.join(iter_dir, "run_quincy_array.py"))

        time.sleep(1.0)
        scriptpath = os.path.join(iter_dir, "submit.sh")
        # --wait blocks until every array task has finished, so the
        # calibration loop can synchronously move on to extracting metrics.
        p = subprocess.Popen(f"/usr/bin/sbatch --wait {scriptpath}", shell=True, cwd=iter_dir)
        p.communicate()

        return [_has_nc_output(rd) for rd in run_dirs]
