#!/usr/bin/env python3
"""Calibrate QUINCY parameters against observations in several rounds.

Usage:
    python run_calibration.py my_site_config.py

See config_example.py for the config format (a plain Python script, same
style as the existing QPy runscripts) and README.md for the method. The code
lives in src/calibration. This can be expensive: every round runs
ensemble.size full transient QUINCY runs, for up to ensemble.max_rounds rounds.
"""
import argparse
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
QPY_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir))
sys.path.append(QPY_ROOT)

from src.calibration.calibrate import run_calibration
from src.calibration.config import CalibrationConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", help="Path to a calibration config script (see config_example.py)")
    args = parser.parse_args()

    config = CalibrationConfig.from_pyfile(args.config)
    run_calibration(config)


if __name__ == "__main__":
    main()
