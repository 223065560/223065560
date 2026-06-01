"""
classify.py  —  Land Cover Classification (v5)
================================================
Method: Random Forest + Confidence-guided refinement
- Adaptive thresholds based on image statistics
- Low-confidence pixels re-evaluated using spectral rules
- Temporal consistency: built-up pixels cannot revert to other classes
- Auto band scaling detection
"""

import numpy as np
import rasterio
from sklearn.ensemble import RandomForestClassifier

CLASS_NAMES  = {1: "Vegetation", 2: "Built-up", 3: "Water", 4: "Bare Land"}
CLASS_COLORS = {
    1: (34,  139,  34),
    2: (220,  50,  50),
    3: ( 30, 100, 200),
    4: (180, 140,  80),
}

CONFIDENCE_THRESHOLD = 0.65   # pixels below this get re-evaluated


# ─── 1. Read ──────────────────────────────────────────────────────────────────
def read_image(filepath):
    with rasterio.open(filepath) as src:
        raw     = src.read().astype(np.float32)
        profile = src.profile.copy()
        nodata  = src.nodata

    if nodata is not None:
        nodata_mask = np.any(raw == nodata, axis=0)
    else:
        nodata_mask = np.all(raw[:6] == 0, axis=0)
    nodata_mask |= np.any(~np.isfinite(raw), axis=0)

    return raw, profile, nodata_mask


# ─── 2. Scale ─────────────────────────────────────────────────────────────────
def scale_bands(raw, nodata_mask, log_fn=None):
    def _log(m):
        if log_fn: log_fn(m)

    data    = raw.copy()
    valid   = ~nodata_mask
    med_b0  = float(np.nanmedian(raw[0][valid]))

    if med_b0 > 1.0:
        _log(f"       Raw DN detected (median B2={med_b0:.1f}) — applying scale factors…")
        data[:6] = np.clip(raw[:6] * 0.0000275 + (-0.2), 0.0, 1.0)
    else:
        _log(f"       Pre-scaled reflectance detected (median B2={med_b0:.4f})")
        data[:6] = np.clip(raw[:6], 0.0, 1.0)

    data[6] = np.clip(raw[6], -1.0, 1.0)   # NDVI
    data[7] = np.clip(raw[7], -1.0, 1.0)   # NDBI
    data[:, nodata_mask] = np.nan
    return data


# ─── 3. Indices ───────────────────────────────────────────────────────────────
def _compute_indices(data):
    B2, B3, B4, B5, B6 = data[0], data[1], data[2], data[3], data[4]
    NDVI = data[6]
    eps  = 1e-10

    MNDWI = (B3 - B6) / (B3 + B6 + eps)
    EVI   = 2.5 * (B5 - B4) / (B5 + 6.0*B4 - 7.5*B2 + 1.0 + eps)
    BSI   = ((B6 + B4) - (B5 + B2)) / ((B6 + B4) + (B5 + B2) + eps)
    NDBI  = (B6 - B5) / (B6 + B5 + eps)

    return NDVI, NDBI, MNDWI, EVI, BSI


# ─── 4. Feature stack ─────────────────────────────────────────────────────────
def _build_feature_stack(data):
    NDVI, NDBI, MNDWI, EVI, BSI = _compute_indices(data)
    stack    = np.stack([data[0],data[1],data[2],data[3],data[4],data[5],
                         NDVI, NDBI, MNDWI, EVI, BSI], axis=0)
    features = stack.reshape(11, -1).T
    return features, NDVI, NDBI, MNDWI, EVI, BSI


# ─── 5. Adaptive training samples ─────────────────────────────────────────────
def _generate_training_samples(data, nodata_mask, n_per_class=2000, log_fn=None):
    def _log(m):
        if log_fn: log_fn(m)

    NDVI, NDBI, MNDWI, EVI, BSI = _compute_indices(data)
    B5    = data[3]
    valid = ~nodata_mask

    def pct(arr, p):
        return float(np.nanpercentile(arr[valid], p))

    ndvi_p25  = pct(NDVI,  25)
    ndvi_p50  = pct(NDVI,  50)
    ndvi_p75  = pct(NDVI,  75)
    ndvi_p90  = pct(NDVI,  90)
    mndwi_p25 = pct(MNDWI, 25)
    mndwi_p75 = pct(MNDWI, 75)
    ndbi_p60  = pct(NDBI,  60)   # lowered from p75 — catches CBD mixed surfaces
    ndbi_p75  = pct(NDBI,  75)
    ndbi_p90  = pct(NDBI,  90)
    bsi_p60   = pct(BSI,   60)   # separates built-up fabric from open bare soil
    b5_p25    = pct(B5,    25)

    _log(f"       NDVI  range: [{pct(NDVI,5):.3f} … {pct(NDVI,95):.3f}]")
    _log(f"       MNDWI range: [{pct(MNDWI,5):.3f} … {pct(MNDWI,95):.3f}]")
    _log(f"       NDBI  range: [{pct(NDBI,5):.3f} … {pct(NDBI,95):.3f}]")

    # Water: strongly positive MNDWI, low NIR
    water_mask = (valid & (MNDWI > max(mndwi_p75, 0.0))
                        & (NDVI  < ndvi_p25)
                        & (B5    < b5_p25 * 1.5))

    # Vegetation: clearly high NDVI + EVI
    veg_mask = (valid & (NDVI  > max(ndvi_p75, 0.15))
                      & (EVI   > 0.05)
                      & (MNDWI < mndwi_p75))

    # Built-up: NDBI above p60 (lowered from p75 to capture CBD mixed surfaces).
    # Rundu CBD has tin roofs, sandy yards and streets that push NDBI below
    # the old p75 threshold, causing dense urban pixels to fall into bare land.
    # BSI > p60 separates built fabric from open bare soil, which has similar
    # NDBI but lower BSI due to absence of impervious surface materials.
    built_mask = (valid & (NDBI  > max(ndbi_p60, -0.05))
                        & (NDVI  < ndvi_p50)
                        & (MNDWI < mndwi_p25)
                        & (BSI   > bsi_p60))

    # Bare land: low NDVI, low MNDWI, BSI below p60 so we do not steal
    # high-BSI urban pixels that belong in the built-up class.
    bare_mask = (valid & (NDVI  < ndvi_p50)
                       & (MNDWI < mndwi_p25)
                       & (NDBI  < ndbi_p75)
                       & (BSI   < bsi_p60)
                       & (~water_mask))

    masks  = [veg_mask, built_mask, water_mask, bare_mask]
    labels = [1, 2, 3, 4]

    features, *_ = _build_feature_stack(data)
    X_list, y_list = [], []

    for mask, label in zip(masks, labels):
        idx = np.where(mask.ravel())[0]
        _log(f"       {CLASS_NAMES[label]:12s}: {len(idx):,} candidate pixels")
        if len(idx) == 0:
            raise ValueError(
                f"No training pixels found for '{CLASS_NAMES[label]}'.\n"
                f"Check band order: SR_B2, SR_B3, SR_B4, SR_B5, SR_B6, SR_B7, NDVI, NDBI"
            )
        chosen = np.random.choice(idx, size=min(n_per_class, len(idx)), replace=False)
        X_list.append(features[chosen])
        y_list.append(np.full(len(chosen), label, dtype=np.uint8))

    return np.vstack(X_list), np.concatenate(y_list)


# ─── 6. Confidence-guided refinement ──────────────────────────────────────────
def _refine_with_confidence(classification, confidence, data, nodata_mask,
                             log_fn=None):
    """
    Pixels where RF confidence < CONFIDENCE_THRESHOLD are re-assigned
    using deterministic spectral rules applied to the scaled indices.
    This corrects misclassified pixels in spectrally ambiguous zones.
    """
    def _log(m):
        if log_fn: log_fn(m)

    NDVI, NDBI, MNDWI, EVI, BSI = _compute_indices(data)
    valid     = ~nodata_mask
    uncertain = valid & (confidence < CONFIDENCE_THRESHOLD)
    n_uncert  = int(np.sum(uncertain))
    _log(f"       Refining {n_uncert:,} low-confidence pixels…")

    refined = classification.copy()

    # Apply strict spectral rules to uncertain pixels only
    # Water: clearest rule — MNDWI positive
    w = uncertain & (MNDWI > 0.05) & (NDVI < 0.1)
    refined[w] = 3

    # Vegetation: high NDVI
    v = uncertain & (NDVI > 0.25) & (~w)
    refined[v] = 1

    # Built-up: NDBI > -0.05 (matches the relaxed training threshold so the
    # refinement step is consistent with how training samples were selected).
    b = uncertain & (NDBI > -0.05) & (NDVI < 0.2) & (~w) & (~v)
    refined[b] = 2

    # Remaining uncertain → Bare Land
    rem = uncertain & (~w) & (~v) & (~b)
    refined[rem] = 4

    changed = int(np.sum(refined != classification))
    _log(f"       Refinement changed {changed:,} pixels")
    return refined


# ─── 7. Temporal consistency ──────────────────────────────────────────────────
def apply_temporal_constraint(class1, class2, nodata_mask1=None, nodata_mask2=None, log_fn=None):
    """
    Enforce physically realistic change rules:
    - Built-up is permanent: once built-up (class1=2), keep as built-up in class2
    - Water bodies don't spontaneously become built-up (likely misclass)
    Optionally accepts nodata_mask1 and nodata_mask2 to exclude nodata pixels
    from temporal corrections.
    Returns corrected class2.
    """
    def _log(m):
        if log_fn: log_fn(m)

    corrected = class2.copy()

    # Build a combined valid-data mask (exclude nodata from both epochs)
    valid = np.ones(class1.shape, dtype=bool)
    if nodata_mask1 is not None:
        valid &= ~nodata_mask1
    if nodata_mask2 is not None:
        valid &= ~nodata_mask2

    # Rule 1: Built-up cannot revert — if it was built-up in year1, keep it
    built_in_1 = valid & (class1 == 2) & (class2 != 0)
    corrected[built_in_1] = 2
    n1 = int(np.sum(built_in_1 & (class2 != 2)))
    _log(f"       Temporal fix: {n1:,} pixels restored to Built-up")

    # Rule 2: Stable water — if it was water in year1 and class2 says built-up
    # (very unlikely physically), revert to water
    water_to_built = valid & (class1 == 3) & (class2 == 2)
    corrected[water_to_built] = 3
    n2 = int(np.sum(water_to_built))
    if n2 > 0:
        _log(f"       Temporal fix: {n2:,} water→built-up pixels corrected to water")

    return corrected


# ─── 8. Random Forest ─────────────────────────────────────────────────────────
def classify(data, nodata_mask, n_trees=200, n_per_class=2000,
             random_state=42, log_fn=None):
    def _log(m):
        if log_fn: log_fn(m)

    np.random.seed(random_state)
    rows, cols = data.shape[1], data.shape[2]

    features, *_ = _build_feature_stack(data)

    _log("       Generating adaptive training samples…")
    X_train, y_train = _generate_training_samples(
        data, nodata_mask, n_per_class=n_per_class, log_fn=log_fn)

    _log(f"       Training Random Forest ({n_trees} trees, "
         f"{len(X_train):,} samples)…")
    rf = RandomForestClassifier(
        n_estimators=n_trees,
        max_features="sqrt",
        min_samples_leaf=5,
        n_jobs=-1,
        random_state=random_state,
        class_weight="balanced"
    )
    rf.fit(X_train, y_train)

    valid_idx = np.where((~nodata_mask).ravel())[0]
    proba     = rf.predict_proba(features[valid_idx])
    pred      = rf.classes_[np.argmax(proba, axis=1)]
    conf      = np.max(proba, axis=1)

    classification            = np.zeros(rows * cols, dtype=np.uint8)
    confidence                = np.zeros(rows * cols, dtype=np.float32)
    classification[valid_idx] = pred
    confidence[valid_idx]     = conf

    classification = classification.reshape(rows, cols)
    confidence     = confidence.reshape(rows, cols)

    # Confidence-guided refinement
    classification = _refine_with_confidence(
        classification, confidence, data, nodata_mask, log_fn=log_fn)

    # Feature importances
    names = ["B2","B3","B4","B5","B6","B7","NDVI","NDBI","MNDWI","EVI","BSI"]
    top5  = sorted(zip(names, rf.feature_importances_), key=lambda x: -x[1])[:5]
    _log(f"       Top features: { {n: round(v,3) for n,v in top5} }")

    return classification, confidence, rf


# ─── 9. Public entry point ────────────────────────────────────────────────────
def classify_file(filepath, n_trees=200, n_per_class=2000, log_fn=None):
    def _log(m):
        if log_fn: log_fn(m)

    _log("       Reading image…")
    raw, profile, nodata_mask = read_image(filepath)

    _log("       Scaling bands…")
    data = scale_bands(raw, nodata_mask, log_fn=log_fn)

    classification, confidence, rf = classify(
        data, nodata_mask, n_trees=n_trees,
        n_per_class=n_per_class, log_fn=log_fn)

    return classification, confidence, profile, nodata_mask
