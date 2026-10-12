#!/usr/bin/env python3
"""
Compress the raw CRU-JRA 6-hourly files in place: CEDA ships them as
uncompressed netCDF-3 (1.5 GB per variable-year, ~1.85 TB per version);
netCDF-4 with zlib level 1 + shuffle makes them ~5.6x smaller, losslessly
(most of the grid is ocean fill).

Per file: nccopy to <file>.part next to it, check that every variable's
values, mask and attributes and the global attributes are identical, then
replace the original under the same name. A file that fails the check is
left untouched (and reported); files already in netCDF-4 are skipped, so a
rerun resumes. Chunks are one time step (1 x 360 x 720), the nccopy default.

Usage:
  python compress_crujra_raw.py v2.5/tmp            # one variable folder under crujra/raw/
  python compress_crujra_raw.py v2.5/tmp --dry-run
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import netCDF4 as nc
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import get_logger  # noqa: E402

RAW = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/crujra/raw")
SLAB = 365          # time steps compared at once (~380 MB per array)
LOG = get_logger("crujra-compress")


def identical(src: Path, dst: Path) -> str | None:
    """None if dst holds exactly src's data and attributes, else what differs."""
    with nc.Dataset(src) as a, nc.Dataset(dst) as b:
        if a.ncattrs() != b.ncattrs() or any(a.getncattr(k) != b.getncattr(k) for k in a.ncattrs()):
            return "global attributes"
        if {k: len(d) for k, d in a.dimensions.items()} != {k: len(d) for k, d in b.dimensions.items()}:
            return "dimensions"
        if set(a.variables) != set(b.variables):
            return "variable names"
        for name, va in a.variables.items():
            vb = b[name]
            if va.dimensions != vb.dimensions or va.dtype != vb.dtype:
                return f"{name}: dimensions/dtype"
            attrs_a = {k: va.getncattr(k) for k in va.ncattrs()}
            attrs_b = {k: vb.getncattr(k) for k in vb.ncattrs()}
            if attrs_a.keys() != attrs_b.keys() or any(not np.array_equal(attrs_a[k], attrs_b[k]) for k in attrs_a):
                return f"{name}: attributes"
            n = va.shape[0] if va.ndim else 1
            for i in range(0, n, SLAB) if va.ndim else [None]:
                x = va[i:i + SLAB] if i is not None else va[...]
                y = vb[i:i + SLAB] if i is not None else vb[...]
                mx, my = np.ma.getmaskarray(x), np.ma.getmaskarray(y)
                if not np.array_equal(mx, my) or not np.array_equal(np.ma.filled(x, 0), np.ma.filled(y, 0)):
                    return f"{name}: values"
    return None


def compress(path: Path) -> str:
    with nc.Dataset(path) as ds:
        if ds.data_model.startswith("NETCDF4"):
            return "skip"
    part = path.with_name(path.name + ".part")
    part.unlink(missing_ok=True)
    subprocess.run(["nccopy", "-k", "nc4", "-d", "1", "-s", str(path), str(part)], check=True)
    problem = identical(path, part)
    if problem:
        part.unlink()
        raise RuntimeError(f"compressed copy differs ({problem}); original kept")
    os.replace(part, path)
    return "ok"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="variable folder relative to crujra/raw/, e.g. v2.5/tmp")
    ap.add_argument("--root", type=Path, default=RAW, help=f"raw folder (default {RAW})")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    files = sorted((args.root / args.folder).glob("*.nc"))
    if not files:
        sys.exit(f"no .nc files in {args.root / args.folder}")
    before = sum(f.stat().st_size for f in files)
    LOG.info(f"{args.folder}: {len(files)} files, {before / 1e9:.1f} GB")
    failed, done = [], 0
    for i, f in enumerate(files, 1):
        if args.dry_run:
            LOG.info(f"  would compress {f.name}")
            continue
        t0 = time.time()
        try:
            status = compress(f)
        except Exception as e:      # keep going; report at the end
            failed.append(f.name)
            LOG.error(f"  [{i}/{len(files)}] {f.name}: {e}")
            continue
        done += status == "ok"
        LOG.info(f"  [{i}/{len(files)}] {f.name}: {status} "
                 f"({f.stat().st_size / 1e9:.2f} GB, {time.time() - t0:.0f} s)")
    after = sum(f.stat().st_size for f in files)
    LOG.info(f"{args.folder}: compressed {done}, failed {len(failed)}, "
             f"{before / 1e9:.1f} GB -> {after / 1e9:.1f} GB")
    if failed:
        LOG.error("failed: " + " ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
