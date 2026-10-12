#!/usr/bin/env python3
"""CLI entry point for the LAVENDAR-style QUINCY plant-hydraulics calibration
tool.

Usage:
    python run_calibration.py my_site_config.py

See config_example.py for the config format (a plain Python script, same
style as the existing QPy runscripts) and README.md for the method and a
worked example. This can be expensive: with the example config it launches
ensemble.size (e.g. 150) full transient QUINCY runs per iteration, for up to
ensemble.max_iterations iterations.
"""
import argparse
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
QPY_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir, os.pardir, os.pardir))
sys.path.append(QPY_ROOT)
sys.path.append(THIS_DIR)

from qpy_calibrate.calibrate import run_calibration
from qpy_calibrate.config import CalibrationConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", help="Path to a calibration config script (see config_example.py)")
    args = parser.parse_args()

    config = CalibrationConfig.from_pyfile(args.config)
    run_calibration(config)


if __name__ == "__main__":
    main()
