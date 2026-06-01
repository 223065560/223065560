import numpy as np
from classify import CLASS_NAMES, apply_temporal_constraint


def detect_change(class1, class2, nodata_mask1, nodata_mask2, log_fn=None):
    """
    Apply temporal constraint then detect pixel-wise changes.
    Returns corrected class2 and change map.
    """
    # Enforce temporal consistency (built-up can't shrink)
    class2_corrected = apply_temporal_constraint(
        class1, class2, nodata_mask1, nodata_mask2, log_fn=log_fn
    )

    nodata = (class1 == 0) | (class2_corrected == 0)
    changed = (~nodata) & (class1 != class2_corrected)

    change_map = np.full(class1.shape, 255, dtype=np.uint8)  # 255 = no change
    change_map[changed] = class2_corrected[changed]
    change_map[nodata]  = 0

    return class2_corrected, change_map


def change_summary(class1, class2, pixel_area_m2=900):
    valid   = (class1 != 0) & (class2 != 0)
    changed = valid & (class1 != class2)

    transitions = {}
    for from_cls in range(1, 5):
        for to_cls in range(1, 5):
            if from_cls == to_cls:
                continue
            mask  = changed & (class1 == from_cls) & (class2 == to_cls)
            count = int(np.sum(mask))
            if count > 0:
                area_km2 = round((count * pixel_area_m2) / 1e6, 4)
                key = f"{CLASS_NAMES[from_cls]} → {CLASS_NAMES[to_cls]}"
                transitions[key] = area_km2
    return transitions
