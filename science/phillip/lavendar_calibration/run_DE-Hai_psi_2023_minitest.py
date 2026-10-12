#!/usr/bin/env python3
"""Mini smoke test for config_DE-Hai_psi_2023.py: loads the real production
config (same parameter space, forcing, fixed/log-scaled parameters, and
metrics), shrinks it to a tiny ensemble and a single iteration in a scratch
output_root, and still dispatches via run_mode="slurm_array" (as the real
run must) so the module-loading path (gnu12/mpich/netcdf, via
GenerateSlurmScriptArrayBased) is exercised for real before committing to
the full 512-member run.

Usage: python run_DE-Hai_psi_2023_minitest.py
"""
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
QPY_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir))
sys.path.append(QPY_ROOT)
sys.path.append(THIS_DIR)

from qpy_calibrate.calibrate import run_calibration
from qpy_calibrate.config import CalibrationConfig, EnsembleSpec

config = CalibrationConfig.from_pyfile(os.path.join(THIS_DIR, "config_DE-Hai_psi_2023.py"))
config.output_root = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/lavendar_calibration/DE-Hai_psi_2023_minitest"
config.ensemble = EnsembleSpec(size=8, max_iterations=1, seed=42, run_gradient_check=True, min_success_fraction=0.5)
config.n_parallel = 8

if __name__ == "__main__":
    run_calibration(config)
