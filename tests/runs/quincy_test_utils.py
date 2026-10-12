"""Shared helpers for the QUINCY usecase tests (u30, u31).

The usecases are checked against the official QUINCY reference runs:
the reference directory contains the qs.bin it was produced with plus the
namelist/lctlib of every site, so QPy can be checked without any local build:

1. base namelist + lctlib are taken from the QUINCY git repo at the reference commit
2. QPy generates the usecase setup from them
3. the generated qs.namelist/lctlib are compared to the reference inputs
4. the reference binary is run on the QPy setup and the outputs are compared to the reference outputs

All reference checks are skipped if the reference runs (or the forcing data or the
reference commit) are not available, e.g. when not on the MPI-BGC cluster.
The location of the reference runs can be overwritten with QPY_REFERENCE_RUNS.
"""
import os
import re
import glob
import shlex
import filecmp
import subprocess

import numpy as np
import pandas as pd

from src.quincy.IO.NamelistReader import NamelistReader
from src.quincy.IO.LctlibReader import LctlibReader
from src.sens.base import Quincy_Setup
from src.sens.base import Quincy_Multi_Run
from src.quincy.base.EnvironmentalInputTypes import *
from src.quincy.base.NamelistTypes import ForcingMode
from src.quincy.base.EnvironmentalInput import EnvironmentalInputSite
from src.quincy.base.user_git_information import UserGitInformation

REFERENCE_RUNS_DIR = os.environ.get(
    "QPY_REFERENCE_RUNS",
    "/Net/Groups/BSI/work/quincy/model/reference_runs/cruncepv7_subset_u30_31")

# CruNCEP test sites of the usecases 30 & 31
SITES = ["ESP_01", "FIN_01", "HAI_01", "PUE_01", "US2_01"]

# Modules the QUINCY binary is linked against on the MPI-BGC cluster
HPC_MODULES = "gnu12 mpich phdf5 netcdf netcdf-fortran"

# Namelist entries that only describe who/what produced the run
METADATA_KEYS = {"git_branch", "git_commit_sha", "code_has_changed_since_sha",
                 "simulation_run_by", "netcdf_output_var_list"}


def binary_command(binary_path):
    """Command to run a QUINCY binary. On the cluster the required modules are loaded first."""
    if os.environ.get("LMOD_CMD") or os.environ.get("MODULESHOME"):
        return ["bash", "-lc",
                f"module -q purge; module -q load {HPC_MODULES}; exec {shlex.quote(binary_path)}"]
    return [binary_path]


def run_sites(binary_path, site_folders):
    """Run the binary in all site folders in parallel. Returns {site: returncode}."""
    procs = {}
    for site, folder in site_folders.items():
        log = open(os.path.join(folder, "run.log"), "w")
        procs[site] = (subprocess.Popen(binary_command(binary_path), cwd=folder,
                                        stdout=log, stderr=subprocess.STDOUT), log)
    returncodes = {}
    for site, (p, log) in procs.items():
        returncodes[site] = p.wait()
        log.close()
    return returncodes


def find_reference(usecase, quincy_root_path):
    """Newest reference run of the usecase whose commit is in the local QUINCY repo.

    Returns (experiment dir, commit) or (None, reason it could not be found).
    """
    if not os.path.isdir(REFERENCE_RUNS_DIR):
        return None, f"Reference runs not available at {REFERENCE_RUNS_DIR}"

    for run in sorted(os.listdir(REFERENCE_RUNS_DIR), reverse=True):
        m = re.match(r"^\d{8}(_\d+)?_develop_([0-9a-f]+)$", run)
        if not m:
            continue
        commit = m.group(2)
        exp_dirs = glob.glob(os.path.join(REFERENCE_RUNS_DIR, run, f"exp_{usecase}_*"))
        if len(exp_dirs) != 1 or not os.path.isfile(os.path.join(exp_dirs[0], "zz_binary", "qs.bin")):
            continue
        has_commit = subprocess.run(["git", "-C", quincy_root_path, "cat-file", "-e", f"{commit}^{{commit}}"],
                                    capture_output=True).returncode == 0
        if has_commit:
            return exp_dirs[0], commit

    return None, (f"No reference run of usecase {usecase} in {REFERENCE_RUNS_DIR} "
                  f"with a commit available in {quincy_root_path} (try git fetch)")


def export_from_git(quincy_root_path, commit, rel_path, out_path):
    """Write the file rel_path of the QUINCY repo at the given commit to out_path."""
    content = subprocess.run(["git", "-C", quincy_root_path, "show", f"{commit}:{rel_path}"],
                             capture_output=True, check=True).stdout
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(content)
    return out_path


def generate_usecase_setup(apply_usecase, namelist_path, lctlib_path, quincy_root_path,
                           setup_root_path, sel_out_var_path=None):
    """Generate the setups of all SITES with QPy. Returns {site: folder}."""
    namelist_base = NamelistReader(namelist_path).parse()
    apply_usecase(namelist=namelist_base)
    if sel_out_var_path is not None:
        namelist_base.base_ctl.netcdf_output_var_list.value = sel_out_var_path

    env_input = EnvironmentalInputSite(forcing_mode=ForcingMode.TRANSIENT,
                                       forcing_dataset=ForcingDataset.CRUNCEP)
    namelist_dicts, forcing_dicts = env_input.parse_multi_sites(namelist=namelist_base,
                                                                sitelist=list(SITES),
                                                                site_list_type=SimulationSiteType.CUSTOM)
    lctlib_base = LctlibReader(lctlib_path).parse()

    quincy_multi_run = Quincy_Multi_Run(setup_root_path)
    site_folders = {}
    for site in SITES:
        folder = os.path.join(setup_root_path, "output", site)
        user_git_info = UserGitInformation(quincy_root_path, folder, site)
        quincy_multi_run.add_setup(Quincy_Setup(folder=folder,
                                                namelist=namelist_dicts[site],
                                                lctlib=lctlib_base,
                                                forcing_path=forcing_dicts[site],
                                                user_git_info=user_git_info))
        site_folders[site] = folder
    quincy_multi_run.generate_files()
    return site_folders


def read_namelist_values(path):
    """{group: {name: value}} of a namelist file, with names and groups in lower case."""
    groups, group = {}, None
    with open(path) as f:
        lines = f.readlines()
    for line in lines:
        line = line.split('!')[0].strip()
        if not line:
            continue
        if line.startswith('&'):
            group = line[1:].strip().lower()
            groups[group] = {}
        elif line.startswith('/'):
            group = None
        elif group is not None and '=' in line:
            name, value = line.split('=', 1)
            groups[group][name.strip().lower()] = _normalise_value(value)
    return groups


def _normalise_value(value):
    value = value.strip().rstrip(',').strip().strip('"').strip("'").lower()
    if value in (".true.", "t"):
        return True
    if value in (".false.", "f"):
        return False
    try:
        return float(value.replace('d', 'e'))
    except ValueError:
        return value


def namelist_differences(qpy_path, ref_path):
    """List of differences between two namelists, ignoring METADATA_KEYS."""
    qpy, ref = read_namelist_values(qpy_path), read_namelist_values(ref_path)
    diffs = []
    for group in sorted(set(qpy) | set(ref)):
        if group not in ref or group not in qpy:
            diffs.append(f"&{group} only in {'QPy' if group in qpy else 'reference'}")
            continue
        for name in sorted((set(qpy[group]) | set(ref[group])) - METADATA_KEYS):
            q, r = qpy[group].get(name, "<missing>"), ref[group].get(name, "<missing>")
            if q != r:
                diffs.append(f"&{group} {name}: QPy={q} reference={r}")
    return diffs


def read_lctlib_values(path):
    rows = {}
    with open(path) as f:
        lines = f.readlines()
    for line in lines:
        line = line.split('!')[0].split('#')[0].strip()
        if line:
            name, *values = line.split()
            rows[name] = [_normalise_value(v) for v in values]
    return rows


def lctlib_differences(qpy_path, ref_path):
    qpy, ref = read_lctlib_values(qpy_path), read_lctlib_values(ref_path)
    return [f"{name}: QPy={qpy.get(name, '<missing>')} reference={ref.get(name, '<missing>')}"
            for name in sorted(set(qpy) | set(ref)) if qpy.get(name) != ref.get(name)]


def output_differences(qpy_output_dir, ref_output_dir):
    """Compare all reference txt outputs. Returns (number of files, list of differences)."""
    ref_files = sorted(os.path.basename(f) for f in glob.glob(os.path.join(ref_output_dir, "*.txt")))
    diffs = []
    for name in ref_files:
        qpy_file, ref_file = os.path.join(qpy_output_dir, name), os.path.join(ref_output_dir, name)
        if not os.path.exists(qpy_file):
            diffs.append(f"{name}: missing")
        elif not filecmp.cmp(qpy_file, ref_file, shallow=False):
            a = pd.read_csv(qpy_file, sep=r"\s+").select_dtypes("number").values
            b = pd.read_csv(ref_file, sep=r"\s+").select_dtypes("number").values
            if a.shape != b.shape:
                diffs.append(f"{name}: shape {a.shape} vs {b.shape}")
            else:
                diffs.append(f"{name}: max abs diff {np.nanmax(np.abs(a - b)):.3g}")
    return len(ref_files), diffs


class UseCaseTests:
    """Tests of one usecase, mixed into a unittest.TestCase by test_u30.py / test_u31.py.

    Subclasses set USECASE, OUTPUT_DIR (absolute) and apply_usecase.
    """
    USECASE = None
    OUTPUT_DIR = None

    @staticmethod
    def apply_usecase(namelist):
        raise NotImplementedError

    @classmethod
    def setUpClass(cls):
        import unittest
        from src.quincy.auxil.find_quincy_paths import QuincyPathFinder

        cls.qpf = QuincyPathFinder()
        if not cls.qpf.found_quincy:
            raise unittest.SkipTest("QUINCY directory not found")
        if not os.path.isdir(EnvironmentalInputSite(forcing_mode=ForcingMode.TRANSIENT,
                                                 forcing_dataset=ForcingDataset.CRUNCEP).SITE_DATA_DIR_BASE):
            raise unittest.SkipTest("CRUNCEP site forcing not available (not on the MPI-BGC cluster?)")

        # Reference setup: generated from the base files of the reference commit
        cls.ref_exp_dir, info = find_reference(cls.USECASE, cls.qpf.quincy_root_path)
        cls.ref_skip_reason = None
        if cls.ref_exp_dir is None:
            cls.ref_skip_reason = info
            print(f"Skipping the reference comparison of u{cls.USECASE}: {info}")
            return

        cls.ref_commit = info
        print(f"Comparing u{cls.USECASE} with reference run {cls.ref_exp_dir}")
        base_dir = os.path.join(cls.OUTPUT_DIR, "base_files")
        namelist_path = export_from_git(cls.qpf.quincy_root_path, cls.ref_commit,
                                        "contrib/namelist/qs.namelist", os.path.join(base_dir, "qs.namelist"))
        lctlib_path = export_from_git(cls.qpf.quincy_root_path, cls.ref_commit,
                                      "data/lctlib_quincy_nlct14.def",
                                      os.path.join(base_dir, "lctlib_quincy_nlct14.def"))
        cls.ref_site_folders = generate_usecase_setup(cls.apply_usecase, namelist_path, lctlib_path,
                                                      cls.qpf.quincy_root_path,
                                                      os.path.join(cls.OUTPUT_DIR, "reference_setup"))

    def skip_without_reference(self):
        if self.ref_skip_reason is not None:
            self.skipTest(self.ref_skip_reason)

    def test_namelist_matches_reference(self):
        self.skip_without_reference()
        for site, folder in self.ref_site_folders.items():
            with self.subTest(site=site):
                diffs = namelist_differences(os.path.join(folder, "qs.namelist"),
                                             os.path.join(self.ref_exp_dir, site, "input", "qs.namelist"))
                self.assertEqual(diffs, [], "QPy namelist differs from the reference:\n" + "\n".join(diffs))

    def test_lctlib_matches_reference(self):
        self.skip_without_reference()
        for site, folder in self.ref_site_folders.items():
            with self.subTest(site=site):
                diffs = lctlib_differences(os.path.join(folder, "lctlib_quincy_nlct14.def"),
                                           os.path.join(self.ref_exp_dir, site, "input", "lctlib_quincy_nlct14.def"))
                self.assertEqual(diffs, [], "QPy lctlib differs from the reference:\n" + "\n".join(diffs))

    def test_output_matches_reference(self):
        # Runs the reference binary on the QPy setup: all outputs must be identical
        self.skip_without_reference()
        ref_binary = os.path.join(self.ref_exp_dir, "zz_binary", "qs.bin")
        returncodes = run_sites(ref_binary, self.ref_site_folders)

        for site, folder in self.ref_site_folders.items():
            with self.subTest(site=site):
                self.assertEqual(returncodes[site], 0, f"QUINCY failed, see {folder}/run.log")
                n_files, diffs = output_differences(folder, os.path.join(self.ref_exp_dir, site, "output"))
                self.assertGreater(n_files, 0, "Reference run has no txt output")
                self.assertEqual(diffs, [], f"{len(diffs)} of {n_files} output files differ:\n" + "\n".join(diffs))

    def test_runs_with_local_quincy(self):
        # The usecase with the local QUINCY (base files + binary), e.g. a feature branch.
        # Only checks that all sites finish, the results may differ from the reference.
        if not os.path.isfile(self.qpf.binary_path):
            self.skipTest(f"No QUINCY binary at {self.qpf.binary_path}")
        site_folders = generate_usecase_setup(self.apply_usecase,
                                              self.qpf.namelist_root_path, self.qpf.lctlib_root_path,
                                              self.qpf.quincy_root_path,
                                              os.path.join(self.OUTPUT_DIR, "local_setup"),
                                              sel_out_var_path=self.qpf.sel_out_var_root_path)
        returncodes = run_sites(self.qpf.binary_path, site_folders)
        for site, folder in site_folders.items():
            with self.subTest(site=site):
                self.assertEqual(returncodes[site], 0, f"QUINCY failed, see {folder}/run.log")
