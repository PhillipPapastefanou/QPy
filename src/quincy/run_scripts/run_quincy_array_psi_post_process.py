#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import datetime
import fcntl  # file locking on HPC Linux


def run_quincy(setup_root_path: str, quincy_binary_path: str, total_runs: int ):
    print(f"[INFO] Running Quincy in: {setup_root_path}")
    print(f"[INFO] Binary: {quincy_binary_path}")

    start = time.monotonic()

    # Launch QUINCY
    p = subprocess.Popen(
        [quincy_binary_path],
        cwd=setup_root_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout, stderr = p.communicate()
    returncode = p.returncode
    
    
    duration = time.monotonic() - start
    rejected = 0

    # Optional: forward Quincy’s stdout/stderr
    if stdout:
        print("[STDOUT]")
        print(stdout)
    if stderr:
        print("[STDERR]", file=sys.stderr)
        print(stderr, file=sys.stderr)
            
    try:
        import xarray as xr
        import numpy as np
        import pandas as pd
        import shutil
        from time import perf_counter
        
        qpy_dir = '/Net/Groups/BSI/work_scratch/ppapastefanou/src/QPy'
        sys.path.append(qpy_dir)


        from src.postprocessing.py.qnc_defintions import Output_format
        from src.postprocessing.py.qnc_output_parser import QNC_output_parser
        from src.postprocessing.py.qnc_ncdf_reader import QNC_ncdf_reader
        
        parser = QNC_output_parser(setup_root_path)
        parser.Read()
        output = parser.Available_outputs['fluxnetdata']
        nc_output = QNC_ncdf_reader(setup_root_path,
                                                output.Categories,
                                                output.Identifier,
                                                output.Time_resolution
                                                )

        nc_output.Parse_env_and_variables()
        nc_output.Read_all_1D()
        nc_output.Close()

        RTOBSPATH = "/Net/Groups/BSI/work_scratch/ppapastefanou/data/Fluxnet_detail/eval_processed"

        df_psi_stem = pd.read_csv(os.path.join(RTOBSPATH, "PsiStem2023.csv"))
        df_psi_stem['date'] = pd.to_datetime(df_psi_stem['date'])

        df_mod_hyd = nc_output.Datasets_1D['PHYD']
        df_merge = pd.merge(df_mod_hyd, df_psi_stem, on='date', how='inner')   
        rmse = np.sqrt(((df_merge['psi_stem_avg'] - df_merge['FAG']) ** 2).mean())
        
        if rmse > 0.13:
            rejected = 1
            shutil.rmtree(setup_root_path)
            
            
                
    except Exception as e:
        print("Error performing post processing:")
        print(e)
        rejected = 0
        
        

    log_run(setup_root_path, returncode, duration, total_runs=total_runs, rejected=rejected)
    return returncode


def log_run(setup_root_path: str, returncode: int, duration: float,
            total_runs: int, rejected: int):
    """
    Write one line to ../../progress.txt with:
    - idx based on completion order (1,2,3,...)
    - progress 'X out of N' (if total_runs provided)
    - duration_s: runtime of this run
    - elapsed_s: time since earliest run started
    - node: short node name
    """
    logfile = os.path.join(setup_root_path, os.pardir, os.pardir, "progress.txt")
    logfile = os.path.abspath(logfile)
    logdir = os.path.dirname(logfile)
    os.makedirs(logdir, exist_ok=True)

    job_id = os.environ.get("SLURM_JOB_ID", "no_jobid")
    task_id_str = os.environ.get("SLURM_ARRAY_TASK_ID", "no_taskid")
    node_full = os.uname().nodename
    node = node_full.split(".")[0]  # strip domain

    now_dt = datetime.datetime.now()
    timestamp = now_dt.isoformat(timespec="seconds")

    header = (
        "timestamp\t"
        "job\t"
        "task\t"
        "progress\t"
        "rc\t"
        "duration_s\t"
        "elapsed_s\t"
        "rejected\t"
        "node\n"
    )

    from datetime import timedelta

    with open(logfile, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0, os.SEEK_SET)
            lines = f.readlines()

            # Compute earliest start time from existing lines
            earliest_start = None
            completed_before = 0

            if lines:
                data_lines = lines[1:]  # skip header
                completed_before = len(data_lines)
                for dl in data_lines:
                    parts = dl.rstrip("\n").split("\t")
                    if len(parts) < 8:
                        continue
                    ts_str = parts[0]          # timestamp
                    dur_str = parts[6]         # duration_s
                    try:
                        ts = datetime.datetime.fromisoformat(ts_str)
                        dur = float(dur_str)
                        start_i = ts - timedelta(seconds=dur)
                    except Exception:
                        continue
                    if (earliest_start is None) or (start_i < earliest_start):
                        earliest_start = start_i

            # Start time of current run
            current_start = now_dt - timedelta(seconds=duration)

            if earliest_start is None:
                earliest_start = current_start

            # Index and progress
            idx = completed_before + 1  # completion order 1..N
            if total_runs is not None:
                progress_text = f"{idx} out of {total_runs}"
            else:
                progress_text = str(idx)

            elapsed_s = (now_dt - earliest_start).total_seconds()

            # Move to end and write header (if new) + line
            f.seek(0, os.SEEK_END)
            if not lines:
                f.write(header)

            line = (
                f"{timestamp}\t"
                f"{job_id}\t"
                f"{task_id_str}\t"
                f"{progress_text}\t"
                f"{returncode}\t"
                f"{duration:.2f}\t"
                f"{elapsed_s:.2f}\t"
                f"{rejected}\t"
                f"{node}\n"
            )

            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)



def main():
    # Usage: run_quincy.py SETUP_DIR QUINCY_BINARY_PATH [TOTAL_RUNS]
    if len(sys.argv) not in (3, 4):
        print("Usage: run_quincy.py SETUP_DIR QUINCY_BINARY_PATH [TOTAL_RUNS]", file=sys.stderr)
        sys.exit(1)

    setup_root_path = sys.argv[1]
    quincy_binary_path = sys.argv[2]
    total_runs = None

    if len(sys.argv) == 4:
        try:
            total_runs = int(sys.argv[3])
        except ValueError:
            print(f"[WARN] TOTAL_RUNS is not a valid integer: {sys.argv[3]}", file=sys.stderr)

    if not os.path.isdir(setup_root_path):
        print(f"[ERROR] Setup directory does not exist: {setup_root_path}", file=sys.stderr)
        sys.exit(2)

    if not os.path.isfile(quincy_binary_path):
        print(f"[ERROR] Quincy binary not found: {quincy_binary_path}", file=sys.stderr)
        sys.exit(3)

    returncode = run_quincy(setup_root_path, quincy_binary_path, total_runs=total_runs)
    sys.exit(returncode)

if __name__ == "__main__":
    main()
