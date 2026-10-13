"""Wraps QPy's namelist/lctlib/paramlist machinery and QUINCY's run
executable so the rest of the calibration package only has to deal with
"here is a (n_members, n_params) array, go run and score it".

Reuses the same building blocks as the hand-written scripts under
science/phillip/DE-Hai/runscripts/ (Quincy_Setup, Quincy_Multi_Run,
EnvironmentalInputSite, ApplyDefaultSiteLevel) instead of re-implementing
namelist/lctlib handling.
"""
import json
import os
import subprocess
import sys
import time
from copy import deepcopy
from multiprocessing import Pool

import numpy as np
import pandas as pd

from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.LctlibReader import LctlibReader
from src.quincy.base.PFTTypes import PftQuincy
from src.quincy.base.Paramlist import Paramlist
from src.quincy.base.EnvironmentalInputTypes import ForcingDataset
from src.quincy.base.NamelistTypes import (ForcingMode, GsBetaType, OutputIntervalFlux, OutputIntervalPool,
                                          VegBnfScheme, LeafStoichomScheme, SbBnfScheme)
from src.quincy.base.EnvironmentalInput import EnvironmentalInputSite
from src.quincy.base.user_git_information import UserGitInformation
from src.quincy.run_scripts.default import ApplyDefaultSiteLevel
from src.quincy.run_scripts.submit import GenerateSlurmScriptArrayBased
from src.quincy.auxil.find_quincy_paths import QuincyPathFinder
from src.sens.base import Quincy_Setup, Quincy_Multi_Run
from src.calibration import member_task


def _run_one_local(args):
    """Module-level so multiprocessing can pickle it cheaply."""
    round_dir, member, quincy_binary, total_runs = args
    return member_task.run_member(round_dir, member, quincy_binary, total_runs)


class QuincyModelRunner:
    def __init__(self, config):
        self.config = config

        if config.quincy_root:
            self.paths = QuincyPathFinder.from_root(config.quincy_root)
        else:
            self.paths = QuincyPathFinder()
            if not self.paths.found_quincy:
                raise RuntimeError(
                    "Could not locate a QUINCY installation. Set 'quincy_root' in the "
                    "calibration config, or export the QUINCY environment variable."
                )
        self.quincy_root = self.paths.quincy_root_path

        self.quincy_binary = self.paths.binary_path
        if not os.path.isfile(self.quincy_binary):
            raise RuntimeError(f"QUINCY binary not found at {self.quincy_binary}. Compile QUINCY first.")

        self._build_base_setup()

    # ------------------------------------------------------------------
    # Base namelist/lctlib construction (once per calibration run)
    # ------------------------------------------------------------------
    def _build_base_setup(self):
        cfg = self.config
        sim = cfg.simulation

        namelist_root_path = self.paths.namelist_root_path
        lctlib_root_path = self.paths.lctlib_root_path

        namelist_base = NamelistReader(namelist_root_path).parse()

        forcing_dataset = getattr(ForcingDataset, sim.forcing_dataset)
        env_input = EnvironmentalInputSite(forcing_mode=ForcingMode.TRANSIENT, forcing_dataset=forcing_dataset)
        namelist_base, self.forcing_file = env_input.parse_single_site(namelist=namelist_base, site=cfg.site)
        if sim.forcing_file_override:
            self.forcing_file = sim.forcing_file_override

        ApplyDefaultSiteLevel(namelist=namelist_base)

        namelist_base.base_ctl.netcdf_output_var_list.value = self.paths.sel_out_var_root_path

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

        if sim.c_only:
            # Same settings as the "C only" block of the DE-Hai runscripts (e.g. 72_...)
            namelist_base.lnd_veg_nml.veg_bnf_scheme.value = VegBnfScheme.UNLIMITED
            namelist_base.lnd_veg_nml.leaf_stoichom_scheme.value = LeafStoichomScheme.FIXED
            namelist_base.lnd_sb_nml.flag_sb_prescribe_po4.value = True
            namelist_base.lnd_sb_nml.sb_bnf_scheme.value = SbBnfScheme.UNLIMITED
            namelist_base.base_ctl.flag_slow_sb_pool_spinup_accelerator.value = False

        namelist_base.lnd_veg_nml.flag_dynamic_roots.value = sim.dynamic_roots

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
    def run_round(self, members: np.ndarray, round_dir: str):
        """Write one QUINCY setup per member (natural units, one row each)
        under round_dir/output/<i>, run and score them all, and return one
        row per member with ok/reason and rmse/nmse/n per metric."""
        multi_run = Quincy_Multi_Run(round_dir)
        for i, param_vector in enumerate(members):
            multi_run.add_setup(self._make_setup(param_vector, os.path.join(round_dir, "output", str(i))))
        multi_run.generate_files()
        member_task.write_task_file(round_dir, self.config.metrics, self.config.keep_run_outputs,
                                    keep_netcdf=self.config.keep_best_outputs_fraction > 0)

        if self.config.run_mode == "local":
            self._run_local(round_dir, len(members))
        elif self.config.run_mode == "slurm_array":
            self._run_slurm_array(round_dir, len(members))
        else:
            raise ValueError(f"Unknown run_mode '{self.config.run_mode}'")

        rows = []
        for i in range(len(members)):
            path = member_task.result_path(round_dir, i)
            if os.path.isfile(path):
                with open(path) as f:
                    rows.append(json.load(f))
            else:
                rows.append({"member": i, "ok": False, "reason": "no result written (task killed?)"})
        return pd.DataFrame(rows)

    def _run_local(self, round_dir, n):
        n_parallel = max(1, min(self.config.n_parallel, n))
        tasks = [(round_dir, i, self.quincy_binary, n) for i in range(n)]
        with Pool(processes=n_parallel) as pool:
            pool.map(_run_one_local, tasks)

    def _run_slurm_array(self, round_dir, n):
        # submit.py's generated script does f'{path}wd.txt' with no separator,
        # so `path` must carry a trailing slash.
        path_with_sep = round_dir if round_dir.endswith(os.sep) else round_dir + os.sep

        GenerateSlurmScriptArrayBased(
            # --array=0-{ntasks} is *inclusive* on both ends, and wd.txt has
            # exactly `n` lines (indices 0..n-1), so this must be n-1, not n.
            ntasks=n - 1,
            path=path_with_sep,
            quincy_binary=self.quincy_binary,
            ntasksmax=max(1, min(self.config.n_parallel, n)),
            ram_in_gb=self.config.slurm_ram_in_gb,
            partition=self.config.slurm_partition,
            # The task scores its own output, so it needs QPy's environment
            python=sys.executable,
            script=os.path.abspath(member_task.__file__),
        )

        time.sleep(1.0)
        scriptpath = os.path.join(round_dir, "submit.sh")
        # --wait blocks until every array task has finished
        p = subprocess.Popen(f"/usr/bin/sbatch --wait {scriptpath}", shell=True, cwd=round_dir)
        p.communicate()
