"""
preprocess.py  —  Satellite Image Preprocessor (v1)
=====================================================
Accepts raw Landsat Collection 2 GeoTIFFs (DN or already-scaled),
auto-detects the sensor from band count / metadata, reorders bands,
computes NDVI and NDBI, casts everything to Float32 and writes a
GeoSight-ready 8-band file.

Supported inputs
  • Landsat 5/7 TM  — bands B1-B5, B7    (6 SR bands)
  • Landsat 8/9 OLI — bands B2-B7        (6 SR bands)
  • Already 8-band  — treated as ready, just re-scales if needed

Output band order (matches GeoSight expectation):
  SR_B2 (Blue), SR_B3 (Green), SR_B4 (Red),
  SR_B5 (NIR),  SR_B6 (SWIR1), SR_B7 (SWIR2),
  NDVI, NDBI
"""

import numpy as np
import rasterio
from rasterio.transform import from_bounds
import os


# ── Scale factor detection ────────────────────────────────────────────────────
def _needs_dn_scale(band, valid_mask):
    med = float(np.nanmedian(band[valid_mask]))
    return med > 1.0          # DN values are typically in thousands


def _apply_l2_scale(band):
    """Landsat Collection 2 Level-2 SR DN → reflectance."""
    return np.clip(band.astype(np.float32) * 0.0000275 + (-0.2), 0.0, 1.0)


# ── Band mapping ──────────────────────────────────────────────────────────────
def _map_bands(raw, n_bands, log_fn=None):
    """
    Return (blue, green, red, nir, swir1, swir2) as 2-D arrays
    in 0-1 reflectance, regardless of input sensor.

    Band count heuristics:
      6  → Landsat 5/7 TM SR bands (B1-B5, B7 — no thermal)
      7  → Landsat 8/9 OLI SR  B1-B7 (coastal + 6 SR bands)
      8  → already GeoSight-ready (skip reordering, just re-scale)
     >8  → try to extract bands 2-7 (OLI order assumed)
    """
    def _log(m):
        if log_fn: log_fn(m)

    if n_bands == 8:
        _log("       8-band input detected — treating as pre-arranged (Blue…SWIR2,NDVI,NDBI)")
        b = raw[:6]
    elif n_bands == 6:
        _log("       6-band input — assuming Landsat 5/7 TM order: B1,B2,B3,B4,B5,B7")
        # TM: B1=Blue, B2=Green, B3=Red, B4=NIR, B5=SWIR1, B7=SWIR2
        b = raw[0:6]          # already in the right order for our output
    elif n_bands == 7:
        _log("       7-band input — assuming Landsat 8/9 OLI: B1(coastal),B2-B7")
        b = raw[1:7]          # drop coastal aerosol (band 0), take B2-B7
    else:
        _log(f"       {n_bands}-band input — extracting bands 2-7 (0-indexed 1-6)")
        b = raw[1:7]

    # Scale each band if still in DN
    valid = np.any(b != 0, axis=0)
    scaled = []
    for i, band in enumerate(b):
        if _needs_dn_scale(band, valid):
            scaled.append(_apply_l2_scale(band))
        else:
            scaled.append(np.clip(band.astype(np.float32), 0.0, 1.0))

    blue, green, red, nir, swir1, swir2 = scaled
    return blue, green, red, nir, swir1, swir2


# ── Indices ───────────────────────────────────────────────────────────────────
def _indices(red, nir, swir1):
    eps = 1e-10
    ndvi = ((nir - red) / (nir + red + eps)).astype(np.float32)
    ndbi = ((swir1 - nir) / (swir1 + nir + eps)).astype(np.float32)
    ndvi = np.clip(ndvi, -1.0, 1.0)
    ndbi = np.clip(ndbi, -1.0, 1.0)
    return ndvi, ndbi


# ── Public entry point ────────────────────────────────────────────────────────
def preprocess(input_path, output_path, log_fn=None):
    """
    Read any supported Landsat image, produce a GeoSight-ready 8-band
    Float32 GeoTIFF at output_path.

    Returns output_path on success.
    """
    def _log(m):
        if log_fn: log_fn(m)

    _log(f"       Opening: {os.path.basename(input_path)}")

    with rasterio.open(input_path) as src:
        raw     = src.read().astype(np.float32)
        profile = src.profile.copy()
        n_bands = src.count

    _log(f"       Bands: {n_bands}  |  Size: {raw.shape[2]}×{raw.shape[1]} px")

    blue, green, red, nir, swir1, swir2 = _map_bands(raw, n_bands, log_fn=log_fn)

    _log("       Computing NDVI and NDBI…")
    ndvi, ndbi = _indices(red, nir, swir1)

    # Stack into 8-band output
    stack = np.stack([blue, green, red, nir, swir1, swir2, ndvi, ndbi], axis=0)

    # Update profile
    profile.update(
        count=8,
        dtype="float32",
        nodata=None,
    )

    _log(f"       Writing preprocessed image → {os.path.basename(output_path)}")
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(stack)

    _log("       ✓ Preprocessing complete")
    return output_path
