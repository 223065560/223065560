import numpy as np
import pandas as pd
from classify import CLASS_NAMES


def calculate_areas(class1, class2, pixel_area_m2=900):
    rows = []
    for cls, name in CLASS_NAMES.items():
        a1 = round(np.sum(class1 == cls) * pixel_area_m2 / 1e6, 4)
        a2 = round(np.sum(class2 == cls) * pixel_area_m2 / 1e6, 4)
        change = round(a2 - a1, 4)
        pct    = round((change / a1 * 100) if a1 > 0 else 0.0, 2)
        rows.append({
            "Class":          name,
            "Year1_Area_km2": a1,
            "Year2_Area_km2": a2,
            "Change_km2":     change,
            "Change_%":       pct,
        })
    return pd.DataFrame(rows)


def save_csv(df, path):
    df.to_csv(path, index=False)
