#!/usr/bin/env python3
"""Mini smoke test for config_DE-Hai_psi_2023.py: loads the real production
config, shrinks it to 2 rounds of 8 members in a scratch output_root, and
still dispatches via run_mode="slurm_array" (as the real run must) so the
SLURM path (module loading, scoring inside each task, plots) is exercised
before committing to the full 3 x 512-member run.

Usage: python run_DE-Hai_psi_2023_minitest.py
"""
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
QPY_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir))
sys.path.append(QPY_ROOT)

from src.calibration.calibrate import run_calibration
from src.calibration.config import CalibrationConfig, EnsembleSpec

config = CalibrationConfig.from_pyfile(os.path.join(THIS_DIR, "config_DE-Hai_psi_2023.py"))
config.output_root = "/Net/Groups/BSI/scratch/ppapastefanou/simulations/QPy/adaptive_calibration/DE-Hai_psi_2023_minitest"
config.ensemble = EnsembleSpec(size=8, max_rounds=2, elite_fraction=0.25, seed=42, min_success_fraction=0.25)
config.n_parallel = 8
config.resume = False

if __name__ == "__main__":
    run_calibration(config)
