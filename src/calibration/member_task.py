#!/usr/bin/env python3
"""Runs one ensemble member: QUINCY, then the metrics, then the clean-up.

Used as the SLURM array task (see runner.py) and, in local mode, called
directly. Everything a member produces that the calibration needs is written
into the round directory:

    <round_dir>/results/<member>.json    ok flag, reason, rmse/nmse/n per metric
    <round_dir>/series/<member>.csv.gz   model and obs at the observation timestamps

so the raw NetCDF output can be deleted right away.

Usage: member_task.py ROUND_DIR MEMBER_ID QUINCY_BINARY [TOTAL_RUNS]
"""
import glob
import json
import os
import pickle
import sys
import traceback

QPY_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir))
if QPY_ROOT not in sys.path:
    sys.path.insert(0, QPY_ROOT)

TASK_FILE = "task.pkl"


def write_task_file(round_dir, metrics, keep_run_outputs, keep_netcdf=False):
    """keep_run_outputs: keep everything. keep_netcdf: keep the NetCDF output
    (the calibration deletes it after the round except for the best members),
    but remove the Fortran debug units."""
    with open(os.path.join(round_dir, TASK_FILE), "wb") as f:
        pickle.dump({"metrics": metrics, "keep_run_outputs": keep_run_outputs,
                     "keep_netcdf": keep_netcdf}, f)


def result_path(round_dir, member):
    return os.path.join(round_dir, "results", f"{member}.json")


def series_path(round_dir, member):
    return os.path.join(round_dir, "series", f"{member}.csv.gz")


def evaluate_and_clean(round_dir, member, run_dir, returncode):
    """Score a finished run and write its result file. Never raises."""
    from src.calibration.metrics import evaluate_member

    with open(os.path.join(round_dir, TASK_FILE), "rb") as f:
        task = pickle.load(f)

    result = {"member": member, "ok": False, "reason": ""}
    try:
        if returncode != 0:
            result["reason"] = f"QUINCY exited with code {returncode}"
        elif not glob.glob(os.path.join(run_dir, "*.nc")):
            result["reason"] = "QUINCY wrote no NetCDF output"
        else:
            scores, series = evaluate_member(run_dir, task["metrics"])
            result.update(scores)
            os.makedirs(os.path.dirname(series_path(round_dir, member)), exist_ok=True)
            series.to_csv(series_path(round_dir, member), index=False)
    except Exception:
        result["ok"] = False
        result["reason"] = "evaluation failed: " + traceback.format_exc(limit=3).strip().splitlines()[-1]

    os.makedirs(os.path.dirname(result_path(round_dir, member)), exist_ok=True)
    with open(result_path(round_dir, member), "w") as f:
        json.dump(result, f)

    if not task["keep_run_outputs"]:
        # fort.* are Fortran debug units (e.g. fort.782 from a debug WRITE in
        # QUINCY's snow code, ~3 GB per run)
        paths = glob.glob(os.path.join(run_dir, "fort.*"))
        if not task.get("keep_netcdf", False):
            paths += glob.glob(os.path.join(run_dir, "*.nc"))
        for path in paths:
            os.remove(path)
    return result


def run_member(round_dir, member, quincy_binary, total_runs=None):
    from src.quincy.run_scripts.run_quincy_array import run_quincy

    with open(os.path.join(round_dir, "wd.txt")) as f:
        run_dirs = [line.strip() for line in f]
    run_dir = run_dirs[member]

    try:
        returncode = run_quincy(run_dir, round_dir, quincy_binary, total_runs=total_runs)
    except Exception:
        traceback.print_exc()
        returncode = -1
    return evaluate_and_clean(round_dir, member, run_dir, returncode)


def main():
    if len(sys.argv) not in (4, 5):
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    round_dir, member, quincy_binary = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    total_runs = int(sys.argv[4]) + 1 if len(sys.argv) == 5 else None
    result = run_member(round_dir, member, quincy_binary, total_runs)
    print(f"[calibration] member {member}: ok={result['ok']} {result['reason']}")


if __name__ == "__main__":
    main()
