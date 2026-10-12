#!/usr/bin/env python3
"""
Add QUINCY plant functional type (PFT) maps to the static input file written
by build_static_inputs.py (quincy_static_inputs_<res>.nc).

QUINCY PFTs (lctlib_quincy_nlct14.def, src/quincy/base/PFTTypes.py)
--------------------------------------------------------------------
   1 BEM  moist broadleaved evergreen       8 TrH  C4 grass
   2 BED  dry broadleaved evergreen         9 TeP  C3 pasture
   3 BDR  raingreen broadleaved deciduous  10 TrP  C4 pasture
   4 BDS  summergreen broadleaved decid.   11 TeC  C3 crop
   5 NE   needle-leaved evergreen          12 TrC  C4 crop
   6 NS   summergreen needle-leaved        13 BSO  bare soil
   7 TeH  C3 grass                         14 UAR  urban area

QUINCY standalone simulates ONE tile with ONE PFT per run
(lnd_veg_nml:plant_functional_type_id -> mo_jsb_model_init.f90); it reads no
PFT map. A gridded run therefore needs one PFT id per cell (`pft_dominant`,
or `pft_dominant_natural` for natural vegetation only), or one run per PFT
weighted afterwards by `pft_fraction`.

Source: CLM4 PFT fractions (Lawrence & Chase 2007; CLM4.5 surface data), the
0.25 x 0.3125deg file shipped with GEOS-Chem/MEGAN. Fractions refer to the
land part of a cell and sum to 1 there; glacier, lake and urban are separate
land units in CLM and are not in this file.

CLM4 -> QUINCY (CLM_TO_QUINCY below):
  needleleaf evergreen temperate/boreal tree -> NE
  needleleaf deciduous boreal tree           -> NS
  broadleaf evergreen tropical tree          -> BEM
  broadleaf evergreen temperate tree, shrub  -> BED
  broadleaf deciduous tropical tree          -> BDR
  broadleaf deciduous temperate/boreal tree  -> BDS
  broadleaf deciduous temperate/boreal shrub -> BDS  (QUINCY has no shrub PFT)
  C3 arctic / non-arctic grass               -> TeH
  C4 grass                                   -> TrH
  corn (rainfed + irrigated)                 -> TrC
  all other crops                            -> TeC
  bare                                       -> BSO
TeP/TrP (pasture) and UAR stay 0: CLM4 does not separate pasture from natural
grass and has no urban PFT. (In the lctlib pasture is a copy of grass anyway.)

Regridding: first-order conservative (separable 1-D overlap weights in lat and
lon, longitude wraps), over CLM cells with land; renormalised to sum 1 and
masked to the SoilGrids land cells of the static file; land cells without
CLM data take the nearest cell's fractions.

Variables written:
  pft                  (pft)            1..14
  pft_fraction         (pft, lat, lon)  fraction of the land cell
  veg_fraction         (lat, lon)       1 - bare soil fraction
  pft_dominant         (lat, lon)       largest of PFTs 1-12 (13 = no vegetation)
  pft_dominant_natural (lat, lon)       largest of PFTs 1-8  (13 = no natural vegetation)

Usage:
  python build_pft_map.py               # 0.25deg
  python build_pft_map.py --res 0.5
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import netCDF4 as nc
import numpy as np

from build_static_inputs import FLOAT_FILL, INT_FILL, OUT_ROOT, fill_nearest

CLM4 = Path("/Net/Groups/BSI/data/GEOS_Chem_forcing/HEMCO/MEGAN/v2018-05/CLM4_PFT.geos.025x03125.v201805.nc")

QUINCY_PFTS = ["BEM", "BED", "BDR", "BDS", "NE", "NS", "TeH", "TrH",
               "TeP", "TrP", "TeC", "TrC", "BSO", "UAR"]
QUINCY_PFT_NAMES = ["moist broadleaved evergreen", "dry broadleaved evergreen",
                    "raingreen broadleaved deciduous", "summergreen broadleaved deciduous",
                    "needle-leaved evergreen", "summergreen needle-leaved",
                    "C3 grass", "C4 grass", "C3 pasture", "C4 pasture",
                    "C3 crop", "C4 crop", "bare soil", "urban area"]
CLM_TO_QUINCY = {
    "PFT_BARE": "BSO",
    "PFT_NDLF_EVGN_TMPT_TREE": "NE",
    "PFT_NDLF_EVGN_BORL_TREE": "NE",
    "PFT_NDLF_DECD_BORL_TREE": "NS",
    "PFT_BDLF_EVGN_TROP_TREE": "BEM",
    "PFT_BDLF_EVGN_TMPT_TREE": "BED",
    "PFT_BDLF_DECD_TROP_TREE": "BDR",
    "PFT_BDLF_DECD_TMPT_TREE": "BDS",
    "PFT_BDLF_DECD_BORL_TREE": "BDS",
    "PFT_BDLF_EVGN_SHRB": "BED",
    "PFT_BDLF_DECD_TMPT_SHRB": "BDS",
    "PFT_BDLF_DECD_BORL_SHRB": "BDS",
    "PFT_C3_ARCT_GRSS": "TeH",
    "PFT_C3_NARC_GRSS": "TeH",
    "PFT_C4_GRSS": "TrH",
    "PFT_C3_UNMANAGED_RAINFED_CROP": "TeC",
    "PFT_C3_UNMANAGED_IRRIGATED_CROP": "TeC",
    "PFT_RAINFED_CORN": "TrC",
    "PFT_IRRIGATED_CORN": "TrC",
    "PFT_RAINFED_TMPT_CEREALS": "TeC",
    "PFT_IRRIGATED_TMPT_CEREALS": "TeC",
    "PFT_RAINFED_WINTER_CEREALS": "TeC",
    "PFT_IRRIGATED_WINTER_CEREALS": "TeC",
    "PFT_RAINFED_SOYBEAN": "TeC",
    "PFT_IRRIGATED_SOYBEAN": "TeC",
    # PFT_CROP is the sum of the crop types above and is not used
}
N_VEG, N_NATURAL = 12, 8   # PFTs 1..12 vegetated, 1..8 natural
FRACTION_DECIMALS, FRACTION_SIG_DIGITS = 3, 3


# ------------------------------------------------------------------ regridding
def _edges(centres: np.ndarray, lo: float, hi: float) -> np.ndarray:
    mid = 0.5 * (centres[1:] + centres[:-1])
    return np.clip(np.concatenate([[2 * centres[0] - mid[0]], mid, [2 * centres[-1] - mid[-1]]]), lo, hi)


def overlap(src_edges: np.ndarray, tgt_edges: np.ndarray) -> np.ndarray:
    """(n_tgt, n_src) length of the overlap of each target and source interval."""
    lo = np.maximum(tgt_edges[:-1, None], src_edges[None, :-1])
    hi = np.minimum(tgt_edges[1:, None], src_edges[None, 1:])
    return np.clip(hi - lo, 0, None)


def overlap_lon(src_lon: np.ndarray, tgt_edges: np.ndarray) -> np.ndarray:
    """As overlap(), with source cells shifted by +-360 so the dateline wraps."""
    e = _edges(src_lon, -np.inf, np.inf)
    w = sum(overlap(e + s, tgt_edges) for s in (-360.0, 0.0, 360.0))
    return w


def read_clm4(lat_t: np.ndarray, lon_t: np.ndarray, res: float) -> np.ndarray:
    """QUINCY PFT fractions (14, lat asc, lon) on the target grid, NaN off CLM land."""
    with nc.Dataset(CLM4) as ds:
        lat_s, lon_s = np.asarray(ds["lat"][:], float), np.asarray(ds["lon"][:], float)
        src = np.zeros((len(QUINCY_PFTS), len(lat_s), len(lon_s)))
        for clm, q in CLM_TO_QUINCY.items():
            src[QUINCY_PFTS.index(q)] += np.ma.filled(ds[clm][0].astype(float), 0.0)
    assert np.all(np.diff(lat_s) > 0) and np.all(np.diff(lon_s) > 0)
    valid = (src.sum(0) > 0).astype(float)

    w_lat = overlap(_edges(lat_s, -90, 90), np.concatenate([lat_t - res / 2, [lat_t[-1] + res / 2]]))
    w_lon = overlap_lon(lon_s, np.concatenate([lon_t - res / 2, [lon_t[-1] + res / 2]]))
    # area weight of the source rows (cos lat) so polar rows count less
    w_lat = w_lat * np.cos(np.deg2rad(lat_s))[None, :]
    norm = w_lat @ valid @ w_lon.T
    out = np.einsum("ys,psx,tx->pyt", w_lat, src * valid, w_lon, optimize=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(norm > 0, out / norm, np.nan)
    return out


# ------------------------------------------------------------------ build
def dominant(frac: np.ndarray, n: int) -> np.ndarray:
    """1-based id of the largest of the first n PFTs; 13 (BSO) where they are all 0."""
    sub = np.nan_to_num(frac[:n])
    idx = sub.argmax(0) + 1
    return np.where(sub.sum(0) > 0, idx, QUINCY_PFTS.index("BSO") + 1)


def build(static_file: Path) -> None:
    with nc.Dataset(static_file) as ds:
        lat, lon = np.asarray(ds["lat"][:], float), np.asarray(ds["lon"][:], float)
        land = ~np.ma.getmaskarray(ds["sand_fraction"][:])
    res = float(np.round(lat[1] - lat[0], 6))

    frac = read_clm4(lat, lon, res)
    frac = np.stack([fill_nearest(f, land) for f in frac])
    total = frac.sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(land & (total > 0), frac / total, np.nan)
    veg = 1.0 - frac[QUINCY_PFTS.index("BSO")]
    dom = np.where(land, dominant(frac, N_VEG), INT_FILL)
    dom_nat = np.where(land, dominant(frac, N_NATURAL), INT_FILL)

    legend = ", ".join(f"{i} {s} ({n})" for i, (s, n) in enumerate(zip(QUINCY_PFTS, QUINCY_PFT_NAMES), 1))
    mapping = "; ".join(f"{k.removeprefix('PFT_')}->{v}" for k, v in CLM_TO_QUINCY.items())
    source = f"CLM4 PFT fractions (CLM4.5 surface data, GEOS-Chem/MEGAN v2018-05), {CLM4}"
    ny, nx = land.shape
    common = dict(zlib=True, complevel=9, shuffle=True)

    with nc.Dataset(static_file, "a") as ds:
        if "pft" not in ds.dimensions:
            ds.createDimension("pft", len(QUINCY_PFTS))
        v = ds["pft"] if "pft" in ds.variables else ds.createVariable("pft", "i2", ("pft",))
        v[:] = np.arange(1, len(QUINCY_PFTS) + 1)
        v.setncatts({"long_name": "QUINCY plant functional type id (lctlib_quincy_nlct14.def)",
                     "short_names": " ".join(QUINCY_PFTS), "legend": legend})

        def var(name, dtype, dims, **kw):
            if name in ds.variables:
                return ds[name]
            chunks = tuple(1 if d == "pft" else len(ds.dimensions[d]) for d in dims)
            return ds.createVariable(name, dtype, dims, chunksizes=chunks, **common, **kw)

        groom = dict(fill_value=FLOAT_FILL, significant_digits=FRACTION_SIG_DIGITS,
                     quantize_mode="GranularBitRound")
        precision = f"rounded to {FRACTION_DECIMALS} decimal(s), {FRACTION_SIG_DIGITS} significant digits kept"
        v = var("pft_fraction", "f4", ("pft", "lat", "lon"), **groom)
        v[:] = np.where(np.isfinite(frac), np.round(frac, FRACTION_DECIMALS), FLOAT_FILL).astype(np.float32)
        v.setncatts({"units": "1", "long_name": "fraction of the land cell covered by each QUINCY PFT",
                     "comment": "sums to 1 over pft; TeP, TrP (pasture) and UAR (urban) are 0 -- not in the source",
                     "mapping": mapping, "source": source, "precision": precision})

        v = var("veg_fraction", "f4", ("lat", "lon"), **groom)
        v[:] = np.where(np.isfinite(veg), np.round(veg, FRACTION_DECIMALS), FLOAT_FILL).astype(np.float32)
        v.setncatts({"units": "1", "long_name": "vegetated fraction of the land cell (1 - BSO fraction)",
                     "source": source, "precision": precision})

        for name, n, what in [("pft_dominant", N_VEG, "PFTs 1-12 (natural, pasture, crops)"),
                              ("pft_dominant_natural", N_NATURAL, "natural PFTs 1-8 (crops ignored)")]:
            v = var(name, "i2", ("lat", "lon"), fill_value=INT_FILL)
            v[:] = dom if name == "pft_dominant" else dom_nat
            v.setncatts({"units": "class", "long_name": f"QUINCY PFT with the largest fraction among {what}",
                         "comment": "13 (BSO) where none of these PFTs is present",
                         "quincy_namelist": "lnd_veg_nml:plant_functional_type_id",
                         "legend": legend, "source": source})

        ds.setncattr("history", ds.getncattr("history") +
                     f"\n{dt.datetime.now():%Y-%m-%d %H:%M} PFT maps added by "
                     f"climate_forcing/conversion/build_pft_map.py")
        ds.setncattr("title", ds.getncattr("title").replace("phosphorus)", "phosphorus, PFTs)"))
    print(f"added PFT maps to {static_file} ({static_file.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--res", type=float, default=0.25)
    ap.add_argument("--static-file", type=Path, default=None,
                    help="static file to extend (default: the build_static_inputs.py output for --res)")
    args = ap.parse_args()
    tag = f"{args.res:g}deg"
    build(args.static_file or OUT_ROOT / tag / f"quincy_static_inputs_{tag}.nc")


if __name__ == "__main__":
    main()
