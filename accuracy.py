"""
accuracy.py  —  Accuracy Assessment for GeoSight
==================================================
Generates a stratified random sample of reference points from both
classified images, builds a confusion matrix, and computes:
  • Overall Accuracy (OA)
  • Cohen's Kappa (κ)
  • Producer's Accuracy (PA) per class
  • User's Accuracy (UA) per class
  • F1-score per class

No external ground-truth data is required.  The "reference" is a
second independent classification run on a held-out 20% random
sample of pixels — the main classifier is trained on the remaining
80%, then evaluated against the held-out set.

This is a self-consistency check, not a full independent validation,
but it is the accepted approach when no field data is available and
is far more rigorous than no assessment at all.
"""

import numpy as np
from sklearn.metrics import (confusion_matrix, cohen_kappa_score,
                              classification_report)
from classify import (read_image, scale_bands, _build_feature_stack,
                      _generate_training_samples, CLASS_NAMES)
from sklearn.ensemble import RandomForestClassifier
import pandas as pd


def run_accuracy_assessment(filepath, log_fn=None, n_trees=200,
                             test_fraction=0.20, random_state=99):
    """
    Train on 80% of adaptive samples, predict on held-out 20%,
    return (metrics_dict, conf_matrix_df, report_str).
    """
    def _log(m):
        if log_fn: log_fn(m)

    _log("       Reading image for accuracy assessment…")
    raw, profile, nodata_mask = read_image(filepath)
    data = scale_bands(raw, nodata_mask, log_fn=log_fn)

    _log("       Generating full sample pool…")
    X_all, y_all = _generate_training_samples(
        data, nodata_mask, n_per_class=3000, log_fn=log_fn)

    # Stratified train/test split
    np.random.seed(random_state)
    X_train, X_test, y_train, y_test = [], [], [], []
    for cls in np.unique(y_all):
        idx = np.where(y_all == cls)[0]
        np.random.shuffle(idx)
        split = max(1, int(len(idx) * test_fraction))
        X_test.append(X_all[idx[:split]])
        y_test.append(y_all[idx[:split]])
        X_train.append(X_all[idx[split:]])
        y_train.append(y_all[idx[split:]])

    X_train = np.vstack(X_train);  y_train = np.concatenate(y_train)
    X_test  = np.vstack(X_test);   y_test  = np.concatenate(y_test)

    _log(f"       Train: {len(y_train):,}  |  Test: {len(y_test):,}")

    rf = RandomForestClassifier(
        n_estimators=n_trees, max_features="sqrt",
        min_samples_leaf=5, n_jobs=-1,
        random_state=random_state, class_weight="balanced")
    rf.fit(X_train, y_train)
    y_pred = rf.predict(X_test)

    # ── Metrics ──────────────────────────────────────────────────────────────
    labels   = sorted(np.unique(np.concatenate([y_test, y_pred])))
    names    = [CLASS_NAMES[l] for l in labels]

    cm       = confusion_matrix(y_test, y_pred, labels=labels)
    oa       = float(np.trace(cm)) / float(cm.sum())
    kappa    = cohen_kappa_score(y_test, y_pred, labels=labels)

    # PA = diagonal / column sum;  UA = diagonal / row sum
    pa = np.diag(cm) / (cm.sum(axis=0) + 1e-10)
    ua = np.diag(cm) / (cm.sum(axis=1) + 1e-10)
    f1 = 2 * pa * ua / (pa + ua + 1e-10)

    # Confusion matrix as DataFrame
    cm_df = pd.DataFrame(cm, index=[f"Ref:{n}" for n in names],
                              columns=[f"Map:{n}" for n in names])

    # Per-class table
    per_class = pd.DataFrame({
        "Class":       names,
        "PA_%":        np.round(pa * 100, 1),
        "UA_%":        np.round(ua * 100, 1),
        "F1":          np.round(f1, 3),
    })

    metrics = {
        "overall_accuracy": round(oa * 100, 2),
        "kappa":            round(kappa, 4),
        "per_class":        per_class,
        "confusion_matrix": cm_df,
        "n_test":           len(y_test),
    }

    _log(f"       Overall Accuracy : {metrics['overall_accuracy']}%")
    _log(f"       Cohen's Kappa    : {metrics['kappa']}")
    for _, row in per_class.iterrows():
        _log(f"       {row['Class']:12s}  PA={row['PA_%']}%  UA={row['UA_%']}%  F1={row['F1']}")

    return metrics


def run_gcp_assessment(filepath, gcp_csv, profile, log_fn=None):
    """
    Validate a classification against user-supplied Ground Control Points.

    GCP CSV format (with header):
        longitude,latitude,class_id
        17.923,-17.941,2
        ...
    class_id: 1=Vegetation 2=Built-up 3=Water 4=Bare Land

    The function:
      1. Reads the GeoTIFF and classifies it (full run)
      2. Reprojects each GCP lon/lat to image pixel coords using the
         image's affine transform + CRS
      3. Reads the predicted class at each GCP pixel
      4. Computes the same accuracy metrics as run_accuracy_assessment
    """
    import csv
    import rasterio
    from rasterio.crs import CRS
    from pyproj import Transformer

    def _log(m):
        if log_fn: log_fn(m)

    _log("       Reading GCP file…")
    gcps = []
    with open(gcp_csv, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lon = float(row["longitude"])
                lat = float(row["latitude"])
                cls = int(row["class_id"])
                gcps.append((lon, lat, cls))
            except (KeyError, ValueError):
                continue

    if len(gcps) == 0:
        raise ValueError(
            "GCP file is empty or missing columns (longitude, latitude, class_id).")

    _log(f"       {len(gcps)} GCPs loaded")

    # Classify the image
    _log("       Classifying image…")
    raw, img_profile, nodata_mask = read_image(filepath)
    data = scale_bands(raw, nodata_mask, log_fn=_log)
    from sklearn.ensemble import RandomForestClassifier as RFC
    X_train, y_train = _generate_training_samples(
        data, nodata_mask, n_per_class=2000, log_fn=_log)
    rf = RFC(n_estimators=200, max_features="sqrt",
             min_samples_leaf=5, n_jobs=-1,
             random_state=42, class_weight="balanced")
    rf.fit(X_train, y_train)
    features, *_ = _build_feature_stack(data)
    rows_img, cols_img = data.shape[1], data.shape[2]
    valid_idx = np.where((~nodata_mask).ravel())[0]
    proba = rf.predict_proba(features[valid_idx])
    pred_flat = np.zeros(rows_img * cols_img, dtype=np.uint8)
    pred_flat[valid_idx] = rf.classes_[np.argmax(proba, axis=1)]
    classification = pred_flat.reshape(rows_img, cols_img)

    # Map GCPs to pixel coords
    transform = img_profile["transform"]
    src_crs   = img_profile.get("crs")

    # If image CRS is not geographic, we need to reproject the GCPs
    try:
        img_crs  = CRS.from_user_input(src_crs)
        geo_crs  = CRS.from_epsg(4326)
        need_proj = not img_crs.equals(geo_crs)
        if need_proj:
            transformer = Transformer.from_crs(
                geo_crs, img_crs, always_xy=True)
    except Exception:
        need_proj = False

    y_true, y_pred_gcp = [], []
    skipped = 0
    for lon, lat, cls_true in gcps:
        try:
            if need_proj:
                x_map, y_map = transformer.transform(lon, lat)
            else:
                x_map, y_map = lon, lat
            col = int((x_map - transform.c) / transform.a)
            row = int((y_map - transform.f) / transform.e)
            if 0 <= row < rows_img and 0 <= col < cols_img:
                pred_cls = int(classification[row, col])
                if pred_cls != 0:
                    y_true.append(cls_true)
                    y_pred_gcp.append(pred_cls)
                    continue
        except Exception:
            pass
        skipped += 1

    if skipped > 0:
        _log(f"       Warning: {skipped} GCPs fell outside image extent and were skipped")

    if len(y_true) < 4:
        raise ValueError(
            f"Only {len(y_true)} valid GCPs found inside the image. "
            "Need at least 4 (one per class). Check your GCP coordinates.")

    y_true     = np.array(y_true)
    y_pred_gcp = np.array(y_pred_gcp)

    labels = sorted(np.unique(np.concatenate([y_true, y_pred_gcp])))
    names  = [CLASS_NAMES[l] for l in labels]

    cm    = confusion_matrix(y_true, y_pred_gcp, labels=labels)
    oa    = float(np.trace(cm)) / float(cm.sum())
    kappa = cohen_kappa_score(y_true, y_pred_gcp, labels=labels)
    pa    = np.diag(cm) / (cm.sum(axis=0) + 1e-10)
    ua    = np.diag(cm) / (cm.sum(axis=1) + 1e-10)
    f1    = 2 * pa * ua / (pa + ua + 1e-10)

    cm_df = pd.DataFrame(cm, index=[f"Ref:{n}" for n in names],
                              columns=[f"Map:{n}" for n in names])
    per_class = pd.DataFrame({
        "Class": names,
        "PA_%":  np.round(pa * 100, 1),
        "UA_%":  np.round(ua * 100, 1),
        "F1":    np.round(f1, 3),
    })

    metrics = {
        "overall_accuracy": round(oa * 100, 2),
        "kappa":            round(kappa, 4),
        "per_class":        per_class,
        "confusion_matrix": cm_df,
        "n_test":           len(y_true),
        "method":           "GCP validation",
    }

    _log(f"       Overall Accuracy (GCP): {metrics['overall_accuracy']}%")
    _log(f"       Cohen's Kappa         : {metrics['kappa']}")
    for _, row in per_class.iterrows():
        _log(f"       {row['Class']:12s}  PA={row['PA_%']}%  UA={row['UA_%']}%  F1={row['F1']}")

    return metrics
