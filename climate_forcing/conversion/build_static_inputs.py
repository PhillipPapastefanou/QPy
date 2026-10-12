#!/usr/bin/env python3
"""
Build one NetCDF with every time-invariant (static) input QUINCY needs per
grid cell -- soil texture, bulk density, pH, water capacity, bedrock depth,
soil classes, lithology and soil phosphorus pools -- on a regular global
grid (default 0.25deg).

What QUINCY reads, and where each field comes from
---------------------------------------------------
Gridded runs read `bc_quincy_soil.nc` (mo_sb_init.f90 / mo_sse_init.f90),
2-D fields with these exact names, which this file uses unchanged:

  BLDFIE               bulk density, kg m-3          SoilGrids, 7-layer mean
  PHIHOX               pH x 10 (model divides by 10) SoilGrids, 7-layer mean
  TAXOUSDA_10km        USDA soil class               SoilGrids, majority class
  TAXNWRB              WRB soil class                SoilGrids, majority class
  Labile_Inorganic_P   g P m-2                       Yang et al. 2013 (0.5deg)
  Seconday_Mineral__P  g P m-2 (sic, model's name)   Yang et al. 2013 (0.5deg)
  Occluded_P           g P m-2                       Yang et al. 2013 (0.5deg)
  Apatite_P            g P m-2                       Yang et al. 2013 (0.5deg)
  qmax_org             see below

Site runs set the same quantities through the namelist from the site list
(EnvironmentalInputSite.parse_single_site); those extra fields are here too:

  sand_fraction / silt_fraction / clay_fraction   (jsb_sse_nml qs_soil_*)
  awc                (jsb_hydro_nml qs_soil_awc_prescribe), mm
  bedrock_depth      m (candidate for jsb_hydro_nml qs_soil_depth)
  lith_glim          GLiM lithology class

Derivation (checked against the GLOBAL site table, which used the nearest
0.1deg SoilGrids cell: BLDFIE, PHIHOX, classes, GLiM and P pools reproduce
exactly):
  - continuous 0.1deg SoilGrids fields are block-averaged (NaN-aware) to the
    target grid; 0.25deg via 2x upsampling to 0.05deg then 5x5 blocks.
  - classes: majority of the 0.1deg cells in the block (nearest-neighbour
    for 0.5deg sources).
  - texture: SoilGrids gives sand/silt/clay at 7 depths (0, 5, 15, 30, 60,
    100, 200 cm); depth-averaged over 0-2 m with the trapezoid rule and
    renormalised to sum to 1. (The site tables' texture and awc come from a
    different, undocumented source and do not match SoilGrids under any
    depth weighting -- differences of a few % texture are expected.)
  - awc: plant-available water (SoilGrids AWCh1, field capacity at
    -10 kPa / pF 2.0, minus wilting point, vol %) integrated over
    0 .. min(bedrock depth, 2 m), in mm.
  - 0.5deg sources (P pools, GLiM) are sampled at the nearest cell; land
    cells they leave empty are filled from the nearest valid cell (same
    idea as gridded_input.Phosphorus_Inputs.extend_search).
  - qmax_org (max. organic fine-particle C capacity) has no gridded source:
    the site tables use 4 discrete values (3.666, 6.2442, 6.5537, 12.7381)
    that follow neither soil class nor PFT. It is written as -9999, for which
    QUINCY falls back to its default 6.5537 (MERGE(..., ptr_2D > 0)).
  - soil_p_depth is 0.5 m everywhere (as in gridded_input.Phosphorus_Inputs).

Grid: cell-centred, latitude ascending (south to north), longitude -180..180,
like the global forcing stores. Cells without SoilGrids data (ocean, ice
sheets) hold the fill value (-9999 for floats, -1 for classes; masked/NaN
when read with netCDF4/xarray); `land_fraction` is the fraction of 0.1deg soil cells per cell.

Usage:
  python build_static_inputs.py                 # 0.25deg
  python build_static_inputs.py --res 0.5
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import netCDF4 as nc
import numpy as np
from scipy import ndimage

SOILGRIDS = Path("/Net/Groups/BSI/data/datastructure_bgi_cpy/grid/Global/0d10_static/soilgrids/v0_5_1/Data")
PHOSPHORUS = Path("/Net/Groups/BSI/data/datastructure_bgi_cpy/grid/Global/0d50_static/Phosphorous/v2014_06/Data")
GLIM = Path("/Net/Groups/BSI/data/datastructure_bgi_cpy/grid/Global/0d50_static/GLiM/v1_0/Data/GLim.720.360.nc")
OUT_ROOT = Path("/Net/Groups/BSI/work_scratch/ppapastefanou/driver_data/static")

DEPTHS_CM = np.array([0, 5, 15, 30, 60, 100, 200], dtype=float)
# trapezoid weights of the 7 depth nodes over 0-200 cm
TRAPEZOID_W = np.array([2.5, 7.5, 12.5, 22.5, 35.0, 70.0, 50.0]) / 200.0
# storage precision (decimal places) of the continuous fields -- well below
# the uncertainty of the source data
DECIMALS = {"land_fraction": 3, "sand_fraction": 3, "silt_fraction": 3, "clay_fraction": 3,
            "BLDFIE": 0, "PHIHOX": 1, "soil_ph": 2, "bedrock_depth": 2,
            "awc": 1, "awc_pF23": 1, "awc_pF25": 1,
            "Labile_Inorganic_P": 2, "Seconday_Mineral__P": 2, "Occluded_P": 2, "Apatite_P": 2,
            "organic_P": 2, "Total_P": 2}
SIG_DIGITS = {"land_fraction": 3, "sand_fraction": 3, "silt_fraction": 3, "clay_fraction": 3,
              "BLDFIE": 4, "PHIHOX": 3, "soil_ph": 3, "bedrock_depth": 3,
              "awc": 4, "awc_pF23": 4, "awc_pF25": 4,
              "Labile_Inorganic_P": 4, "Seconday_Mineral__P": 4, "Occluded_P": 4, "Apatite_P": 4,
              "organic_P": 4, "Total_P": 4}
INT_VARS = {"TAXOUSDA_10km", "TAXNWRB", "lith_glim", "qmax_org"}
INT_FILL = np.int16(-1)
FLOAT_FILL = np.float32(-9999.0)
P_POOLS = ["Labile_Inorganic_P", "Seconday_Mineral__P", "Occluded_P", "Apatite_P"]


# ------------------------------------------------------------------ reading
def read_grid(path: Path, var: str):
    """Values (layer?, lat desc, lon asc -180..180) as float NaN-filled, + lat, lon."""
    with nc.Dataset(path) as ds:
        lat_n = "latitude" if "latitude" in ds.variables else "lat"
        lon_n = "longitude" if "longitude" in ds.variables else "lon"
        lat, lon = ds[lat_n][:].astype(float), ds[lon_n][:].astype(float)
        x = np.ma.filled(ds[var][:].astype(np.float32), np.nan)
    x[(x <= -9999) | (x >= 1e20)] = np.nan
    lon = np.where(lon >= 180, lon - 360, lon)
    order = np.argsort(lon)
    x, lon = x[..., order], lon[order]
    if lat[0] < lat[-1]:
        x, lat = x[..., ::-1, :], lat[::-1]
    return x, lat, lon


def soilgrids(name: str):
    files = sorted(SOILGRIDS.glob(f"{name}.soilgrid.3600.1800*.nc"))
    if not files:
        raise FileNotFoundError(name)
    var = name
    x, lat, lon = read_grid(files[0], var)
    assert x.shape[-2:] == (1800, 3600), (name, x.shape)
    return x


# ------------------------------------------------------------------ regridding
def _blocks(x: np.ndarray, res: float) -> np.ndarray:
    """(..., 1800, 3600) at 0.1deg -> (..., ny, nx, k) samples per target cell."""
    f = res / 0.1
    if abs(f - round(f)) < 1e-9:
        f = int(round(f))
    else:
        up = 2
        x = np.repeat(np.repeat(x, up, axis=-2), up, axis=-1)
        f = int(round(res / 0.05))
    ny, nx = x.shape[-2] // f, x.shape[-1] // f
    x = x.reshape(*x.shape[:-2], ny, f, nx, f)
    x = np.moveaxis(x, -3, -2)  # (..., ny, nx, f, f)
    return x.reshape(*x.shape[:-2], f * f)


def block_mean(x: np.ndarray, res: float) -> np.ndarray:
    b = _blocks(x, res)
    with np.errstate(invalid="ignore"):
        n = np.isfinite(b).sum(-1)
        s = np.nansum(b, -1)
        return np.where(n > 0, s / np.maximum(n, 1), np.nan).astype(np.float32)


def block_fraction(x: np.ndarray, res: float) -> np.ndarray:
    return np.isfinite(_blocks(x, res)).mean(-1).astype(np.float32)


def block_majority(x: np.ndarray, res: float, chunk_rows: int = 60) -> np.ndarray:
    """Most frequent finite value per target cell (ties: smallest class)."""
    b = _blocks(x, res)
    out = np.full(b.shape[:-1], np.nan, dtype=np.float32)
    for r0 in range(0, b.shape[0], chunk_rows):
        s = np.sort(b[r0:r0 + chunk_rows], axis=-1)  # NaN last
        k = s.shape[-1]
        counts = np.zeros(s.shape, dtype=np.int16)
        for j in range(k):
            counts += (s == s[..., j:j + 1])
        counts[~np.isfinite(s)] = -1
        idx = counts.argmax(-1)
        out[r0:r0 + chunk_rows] = np.take_along_axis(s, idx[..., None], -1)[..., 0]
    return out


def from_half_degree(x: np.ndarray, res: float) -> np.ndarray:
    """(360, 720) at 0.5deg (lat desc) -> target grid by nearest neighbour."""
    if abs(res - 0.5) < 1e-9:
        return x
    f = 0.5 / res
    if abs(f - round(f)) > 1e-9:
        raise ValueError("target resolution must divide 0.5deg")
    f = int(round(f))
    return np.repeat(np.repeat(x, f, 0), f, 1)


def fill_nearest(x: np.ndarray, where: np.ndarray) -> np.ndarray:
    """Fill NaNs inside `where` from the nearest finite cell (longitude wraps)."""
    need = where & ~np.isfinite(x)
    if not need.any() or not np.isfinite(x).any():
        return x
    nx = x.shape[1]
    pad = nx // 4
    xp = np.concatenate([x[:, -pad:], x, x[:, :pad]], axis=1)
    _, (ii, jj) = ndimage.distance_transform_edt(~np.isfinite(xp), return_indices=True)
    filled = xp[ii, jj][:, pad:pad + nx]
    out = x.copy()
    out[need] = filled[need]
    return out


# ------------------------------------------------------------------ build
def build(res: float, out: Path) -> None:
    ny, nx = int(round(180 / res)), int(round(360 / res))
    lat_desc = 90 - res * (np.arange(ny) + 0.5)
    lon = -180 + res * (np.arange(nx) + 0.5)
    fields: dict[str, tuple[np.ndarray, dict]] = {}

    clay = soilgrids("CLYPPT")
    land_frac = block_fraction(clay[0], res)
    land = land_frac > 0
    fields["land_fraction"] = (land_frac, {"units": "1", "long_name": "fraction of 0.1deg SoilGrids cells with soil data"})

    # texture: 0-2 m trapezoid mean, renormalised
    tex = {}
    for name, key in [("CLYPPT", "clay"), ("SLTPPT", "silt"), ("SNDPPT", "sand")]:
        x = clay if name == "CLYPPT" else soilgrids(name)
        tex[key] = np.tensordot(TRAPEZOID_W, x, axes=(0, 0)).astype(np.float32)
    total = tex["clay"] + tex["silt"] + tex["sand"]
    for key in ("sand", "silt", "clay"):
        frac = np.where(total > 0, tex[key] / total, np.nan)
        fields[f"{key}_fraction"] = (block_mean(frac, res), {
            "units": "1", "long_name": f"{key} mass fraction of the fine earth, 0-2 m depth average",
            "quincy_namelist": f"jsb_sse_nml:qs_soil_{key}",
            "source": f"SoilGrids v0.5.1 {'CLYPPT SLTPPT SNDPPT'.split()[['clay', 'silt', 'sand'].index(key)]}, "
                      "trapezoid mean over 0,5,15,30,60,100,200 cm, sand+silt+clay = 1"})
    del clay, tex, total

    bld = soilgrids("BLDFIE")
    fields["BLDFIE"] = (block_mean(np.nanmean(bld, 0), res), {
        "units": "kg m-3", "long_name": "soil bulk density (fine earth), mean of the 7 SoilGrids depths",
        "quincy_namelist": "jsb_sse_nml:qs_bulk_density", "source": "SoilGrids v0.5.1 BLDFIE"})
    del bld
    ph = block_mean(np.nanmean(soilgrids("PHIHOX"), 0), res)
    fields["PHIHOX"] = (ph, {"units": "pH x 10", "long_name": "soil pH (H2O) x 10, mean of the 7 SoilGrids depths",
                             "comment": "QUINCY divides by 10 (mo_sb_init.f90); site runs: lnd_sb_nml:soil_ph = PHIHOX / 10",
                             "source": "SoilGrids v0.5.1 PHIHOX"})

    bdr = soilgrids("BDRICM")  # cm, capped at 200
    fields["bedrock_depth"] = (block_mean(bdr, res) / 100.0, {
        "units": "m", "long_name": "depth to bedrock (R horizon), capped at 2 m by SoilGrids",
        "source": "SoilGrids v0.5.1 BDRICM"})
    zmax = np.where(np.isfinite(bdr), np.clip(bdr, 0, 200), 200.0)
    # thickness each depth node represents within 0..zmax (trapezoid on clipped depths)
    zz = np.minimum(DEPTHS_CM[:, None, None], zmax[None])
    seg = np.diff(zz, axis=0)                               # (6, lat, lon) cm
    node_w = np.zeros((7,) + bdr.shape, dtype=np.float32)
    node_w[:-1] += seg / 2
    node_w[1:] += seg / 2
    for name, key, label in [("AWCh1", "awc", "-10 kPa (pF 2.0)")]:
        vol = soilgrids(name)                               # vol %
        mm = np.nansum(vol / 100.0 * node_w * 10.0, axis=0)  # cm -> mm
        mm[~np.isfinite(vol[0])] = np.nan
        attrs = {"units": "mm", "long_name": f"plant-available water capacity, field capacity at {label}, "
                                             f"integrated over 0..min(bedrock, 2 m)",
                 "source": f"SoilGrids v0.5.1 {name}"}
        if key == "awc":
            attrs["quincy_namelist"] = "jsb_hydro_nml:qs_soil_awc_prescribe"
        fields[key] = (block_mean(mm, res), attrs)
    del bdr, zz, seg, node_w, vol

    for name, key, lname in [("TAXOUSDA_10km", "TAXOUSDA_10km", "USDA 2014 soil suborder class"),
                             ("TAXNWRB", "TAXNWRB", "WRB 2006 soil class")]:
        cls = soilgrids(name)
        fields[key] = (fill_nearest(block_majority(cls, res), land), {
            "units": "class", "long_name": f"{lname} (majority of the 0.1deg cells; land cells without "
                                           f"a class take the nearest cell's)",
            "quincy_namelist": "lnd_sb_nml:" + ("usda_taxonomy_class" if "USDA" in lname else "nwrb_taxonomy_class"),
            "source": f"SoilGrids v0.5.1 {name}"})
        del cls

    glim, _, _ = read_grid(GLIM, "GLim")
    with nc.Dataset(GLIM) as ds:
        legend = ds["GLim"].legend
    fields["lith_glim"] = (fill_nearest(from_half_degree(glim, res), land), {
        "units": "class", "long_name": "GLiM v1.0 lithology class (nearest 0.5deg cell)",
        "legend": "1..16 = " + legend, "source": str(GLIM)})

    for pool in P_POOLS:
        x, _, _ = read_grid(PHOSPHORUS / f"{pool}.nc", pool)
        with nc.Dataset(PHOSPHORUS / f"{pool}.nc") as ds:
            v = ds[pool]
            lname, units = getattr(v, "long_name", pool), getattr(v, "units", "")
        attrs = {"units": units, "long_name": f"{lname} (nearest 0.5deg cell, gaps on land from nearest valid cell)",
                 "source": f"Yang et al. 2013 soil P map, {PHOSPHORUS / (pool + '.nc')}"}
        if pool in ("Labile_Inorganic_P", "Seconday_Mineral__P", "Occluded_P", "Apatite_P"):
            attrs["quincy_namelist"] = {"Labile_Inorganic_P": "lnd_sb_nml:soil_p_labile",
                                        "Seconday_Mineral__P": "lnd_sb_nml:soil_p_slow",
                                        "Occluded_P": "lnd_sb_nml:soil_p_occluded",
                                        "Apatite_P": "lnd_sb_nml:soil_p_primary"}[pool]
        fields[pool] = (fill_nearest(from_half_degree(x, res), land), attrs)

    fields["qmax_org"] = (np.full((ny, nx), -9999.0, dtype=np.float32), {
        "units": "mg C g-1 soil", "long_name": "maximum organic carbon on fine particles -- NO gridded source",
        "comment": "-9999 everywhere: QUINCY then uses its default 6.5537 (mo_sb_init.f90). The site tables use "
                   "3.666 / 6.2442 / 6.5537 / 12.7381 with no documented spatial rule.",
        "quincy_namelist": "lnd_sb_nml:qmax_org_fine_particle"})

    # mask everything to the SoilGrids land cells
    for k, (arr, attrs) in fields.items():
        if k not in ("land_fraction", "qmax_org"):
            arr = np.where(land, arr, np.nan)
        fields[k] = (arr[::-1].astype(np.float32), attrs)  # -> latitude ascending

    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(out.name + ".part")
    with nc.Dataset(part, "w") as ds:
        ds.createDimension("lat", ny)
        ds.createDimension("lon", nx)
        v = ds.createVariable("lat", "f8", ("lat",))
        v[:] = lat_desc[::-1]
        v.setncatts({"units": "degrees_north", "standard_name": "latitude"})
        v = ds.createVariable("lon", "f8", ("lon",))
        v[:] = lon
        v.setncatts({"units": "degrees_east", "standard_name": "longitude"})
        for k, (arr, attrs) in fields.items():
            # compact storage: classes as int16, continuous fields rounded to a
            # physically meaningful precision (DECIMALS) so zlib + shuffle can
            # compress them well; one chunk per field
            common = dict(zlib=True, complevel=9, shuffle=True, chunksizes=(ny, nx))
            if k in INT_VARS:
                data = np.where(np.isfinite(arr), arr, INT_FILL).astype(np.int16)
                v = ds.createVariable(k, "i2", ("lat", "lon"), fill_value=None if k == "qmax_org" else INT_FILL,
                                      **common)
            else:
                # rounding to DECIMALS, then netCDF bit grooming (GranularBitRound to
                # SIG_DIGITS significant digits): unused mantissa bits are zeroed so
                # zlib compresses them away; values stay plain float32 for any reader
                # finite fill value: quantization skips _FillValue, but NaN never compares
                # equal to itself, so NaN fills would be quantized into numbers
                data = np.where(np.isfinite(arr), np.round(arr, DECIMALS[k]), FLOAT_FILL).astype(np.float32)
                v = ds.createVariable(k, "f4", ("lat", "lon"), fill_value=FLOAT_FILL,
                                      significant_digits=SIG_DIGITS[k], quantize_mode="GranularBitRound",
                                      **common)
                attrs = {**attrs, "precision": f"rounded to {DECIMALS[k]} decimal(s), "
                                               f"{SIG_DIGITS[k]} significant digits kept"}
            v[:] = data
            v.setncatts(attrs)
        ds.setncatts({
            "title": f"QUINCY static inputs (soil, lithology, phosphorus), {res}deg",
            "soil_p_depth": "0.5 m (depth the P pools refer to; lnd_sb_nml:soil_p_depth)",
            "conventions_note": "BLDFIE, PHIHOX, TAXOUSDA_10km, TAXNWRB, *_P and qmax_org use the variable "
                                "names QUINCY reads from bc_quincy_soil.nc",
            "history": f"created {dt.datetime.now():%Y-%m-%d %H:%M} by climate_forcing/conversion/build_static_inputs.py",
        })
    part.rename(out)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--res", type=float, default=0.25)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    tag = f"{args.res:g}deg"
    build(args.res, args.output or OUT_ROOT / tag / f"quincy_static_inputs_{tag}.nc")


if __name__ == "__main__":
    main()
