import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib_scalebar.scalebar import ScaleBar
import os

# ─── Colours ──────────────────────────────────────────────────────────────────
CLASS_RGBA = {
    0:   (0.00, 0.00, 0.00, 0.00),   # NoData  — transparent
    1:   (0.13, 0.55, 0.13, 1.00),   # Vegetation
    2:   (0.86, 0.20, 0.20, 1.00),   # Built-up
    3:   (0.12, 0.39, 0.78, 1.00),   # Water
    4:   (0.71, 0.55, 0.31, 1.00),   # Bare Land
}

CHANGE_RGBA = {
    0:   (0.00, 0.00, 0.00, 0.00),   # NoData
    1:   (0.13, 0.55, 0.13, 1.00),   # → Vegetation
    2:   (0.86, 0.20, 0.20, 1.00),   # → Built-up
    3:   (0.12, 0.39, 0.78, 1.00),   # → Water
    4:   (0.71, 0.55, 0.31, 1.00),   # → Bare Land
    255: (0.92, 0.92, 0.92, 1.00),   # No change
}

CLASS_NAMES = {1: "Vegetation", 2: "Built-up", 3: "Water", 4: "Bare Land"}

PANEL_BG = "#f8fafc"
MAP_BG   = "#ffffff"
TEXT_COL = "#1e293b"
ACC_COL  = "#0891b2"


def _array_to_rgba(arr, lut):
    h, w = arr.shape
    rgba = np.zeros((h, w, 4), dtype=np.float32)
    for val, color in lut.items():
        rgba[arr == val] = color
    return rgba


def _add_north_arrow(ax):
    ax.annotate("", xy=(0.96, 0.94), xytext=(0.96, 0.86),
                xycoords="axes fraction", textcoords="axes fraction",
                arrowprops=dict(arrowstyle="-|>", color=TEXT_COL, lw=1.8))
    ax.text(0.96, 0.96, "N", transform=ax.transAxes,
            ha="center", va="bottom", color=TEXT_COL,
            fontsize=10, fontweight="bold", fontfamily="monospace")


def _add_legend(ax, entries, title="Land Cover"):
    patches = [mpatches.Patch(facecolor=c, edgecolor="white",
                               linewidth=0.5, label=lbl)
               for lbl, c in entries]
    leg = ax.legend(handles=patches, title=title, loc="lower left",
                    fontsize=8.5, title_fontsize=9.5,
                    facecolor=PANEL_BG, edgecolor=ACC_COL,
                    labelcolor=TEXT_COL, framealpha=0.95)
    leg.get_title().set_color(ACC_COL)
    leg.get_title().set_fontfamily("monospace")


def _style_ax(ax, title, transform=None, crs_str=""):
    ax.set_facecolor(MAP_BG)
    ax.set_title(title, color=TEXT_COL, fontsize=11,
                 fontweight="bold", fontfamily="monospace", pad=10)
    ax.tick_params(colors=TEXT_COL, labelsize=7)
    for sp in ax.spines.values():
        sp.set_edgecolor(ACC_COL)
        sp.set_linewidth(0.8)
    if crs_str:
        ax.text(0.01, 0.01, str(crs_str)[:40],
                transform=ax.transAxes,
                fontsize=6, color=ACC_COL, fontfamily="monospace",
                va="bottom", ha="left")
    if transform is not None:
        try:
            sb = ScaleBar(abs(transform.a), units="m",
                          location="lower right",
                          color=TEXT_COL, box_color=PANEL_BG,
                          box_alpha=0.7,
                          font_properties={"size": 7.5},
                          border_pad=0.5, sep=3)
            ax.add_artist(sb)
        except Exception:
            pass


def _footer(fig, source="Source: Landsat via Google Earth Engine",
            tool="GeoSight  —  Land Cover Analysis Platform"):
    fig.text(0.01, 0.004, source, fontsize=7, color=ACC_COL,
             fontfamily="monospace", va="bottom")
    fig.text(0.99, 0.004, tool, fontsize=7, color=ACC_COL,
             fontfamily="monospace", va="bottom", ha="right")


# ─── Public functions ─────────────────────────────────────────────────────────

def save_classification_map(classification, output_path, title,
                             transform=None, crs=None):
    rgba = _array_to_rgba(classification, CLASS_RGBA)
    fig, ax = plt.subplots(figsize=(9, 8), facecolor=PANEL_BG)
    ax.imshow(rgba, interpolation="nearest")
    _style_ax(ax, title, transform, str(crs) if crs else "")
    _add_north_arrow(ax)
    _add_legend(ax, [(CLASS_NAMES[i], CLASS_RGBA[i][:3]) for i in range(1,5)])
    _footer(fig)
    plt.tight_layout(rect=[0, 0.02, 1, 1])
    plt.savefig(output_path, dpi=200, bbox_inches="tight",
                facecolor=PANEL_BG)
    plt.close()


def save_change_map(change_map, output_path,
                    year1="Year 1", year2="Year 2",
                    transform=None, crs=None):
    rgba = _array_to_rgba(change_map, CHANGE_RGBA)
    fig, ax = plt.subplots(figsize=(9, 8), facecolor=PANEL_BG)
    ax.imshow(rgba, interpolation="nearest")
    _style_ax(ax, f"Change Detection  ·  {year1} → {year2}",
              transform, str(crs) if crs else "")
    _add_north_arrow(ax)
    entries = [("No Change", CHANGE_RGBA[255][:3])] + \
              [(f"→ {CLASS_NAMES[i]}", CHANGE_RGBA[i][:3]) for i in range(1,5)]
    _add_legend(ax, entries, title="Change")
    _footer(fig)
    plt.tight_layout(rect=[0, 0.02, 1, 1])
    plt.savefig(output_path, dpi=200, bbox_inches="tight",
                facecolor=PANEL_BG)
    plt.close()


def save_side_by_side(class1, class2, output_path,
                       year1="Year 1", year2="Year 2",
                       transform=None, crs=None):
    rgba1 = _array_to_rgba(class1, CLASS_RGBA)
    rgba2 = _array_to_rgba(class2, CLASS_RGBA)
    crs_s = str(crs) if crs else ""

    fig, axes = plt.subplots(1, 2, figsize=(16, 7.5), facecolor=PANEL_BG)
    fig.subplots_adjust(wspace=0.05)
    for ax, rgba, yr in zip(axes, [rgba1, rgba2], [year1, year2]):
        ax.imshow(rgba, interpolation="nearest")
        _style_ax(ax, yr, transform, crs_s)
        _add_north_arrow(ax)

    patches = [mpatches.Patch(facecolor=CLASS_RGBA[i][:3],
                               edgecolor="white", linewidth=0.4,
                               label=CLASS_NAMES[i]) for i in range(1,5)]
    fig.legend(handles=patches, loc="lower center", ncol=4,
               fontsize=9, facecolor=PANEL_BG, edgecolor=ACC_COL,
               labelcolor=TEXT_COL, framealpha=0.92,
               bbox_to_anchor=(0.5, 0.0))
    _footer(fig)
    plt.savefig(output_path, dpi=200, bbox_inches="tight",
                facecolor=PANEL_BG)
    plt.close()


def save_area_chart(df, output_path, year1="Year 1", year2="Year 2"):
    classes = df["Class"].tolist()
    x = np.arange(len(classes))
    w = 0.35
    colors = [CLASS_RGBA[i][:3] for i in range(1, 5)]

    fig, ax = plt.subplots(figsize=(9, 5), facecolor=PANEL_BG)
    ax.set_facecolor(MAP_BG)
    ax.bar(x - w/2, df["Year1_Area_km2"], w, label=year1,
           color=colors, alpha=0.70, edgecolor="white", linewidth=0.4)
    ax.bar(x + w/2, df["Year2_Area_km2"], w, label=year2,
           color=colors, alpha=1.0,  edgecolor="white", linewidth=0.4)

    ax.set_xticks(x)
    ax.set_xticklabels(classes, color=TEXT_COL, fontsize=10,
                        fontfamily="monospace")
    ax.set_ylabel("Area (km²)", color=TEXT_COL, fontsize=10,
                   fontfamily="monospace")
    ax.set_title("Land Cover Area Comparison",
                  color=TEXT_COL, fontsize=12, fontweight="bold",
                  fontfamily="monospace")
    ax.tick_params(colors=TEXT_COL)
    for sp in ["top","right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["bottom","left"]:
        ax.spines[sp].set_color(ACC_COL)
    ax.legend(facecolor=PANEL_BG, edgecolor=ACC_COL,
              labelcolor=TEXT_COL, fontsize=9)
    ax.yaxis.grid(True, color=ACC_COL, alpha=0.2, linewidth=0.5)
    _footer(fig)
    plt.tight_layout(rect=[0, 0.02, 1, 1])
    plt.savefig(output_path, dpi=200, bbox_inches="tight",
                facecolor=PANEL_BG)
    plt.close()


def save_confidence_map(confidence, nodata_mask, output_path,
                         title="Classification Confidence"):
    display = confidence.copy().astype(np.float32)
    display[nodata_mask] = np.nan

    fig, ax = plt.subplots(figsize=(9, 8), facecolor=PANEL_BG)
    im = ax.imshow(display, cmap="RdYlGn", vmin=0.4, vmax=1.0,
                   interpolation="nearest")
    cbar = fig.colorbar(im, ax=ax, fraction=0.036, pad=0.04)
    cbar.set_label("Confidence Score", color=TEXT_COL,
                    fontsize=9, fontfamily="monospace")
    cbar.ax.yaxis.set_tick_params(color=TEXT_COL, labelsize=7.5)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=TEXT_COL)

    ax.set_facecolor(MAP_BG)
    ax.set_title(title, color=TEXT_COL, fontsize=11,
                  fontweight="bold", fontfamily="monospace", pad=10)
    ax.tick_params(colors=TEXT_COL, labelsize=7)
    for sp in ax.spines.values():
        sp.set_edgecolor(ACC_COL)
        sp.set_linewidth(0.8)
    _add_north_arrow(ax)
    _footer(fig)
    plt.tight_layout(rect=[0, 0.02, 1, 1])
    plt.savefig(output_path, dpi=200, bbox_inches="tight",
                facecolor=PANEL_BG)
    plt.close()


def save_accuracy_report(metrics, output_path, year_label=""):
    """
    Render a clean accuracy report image:
      - Overall Accuracy + Kappa banner
      - Per-class PA / UA / F1 table
      - Confusion matrix heatmap
    """
    import matplotlib.gridspec as gridspec
    import matplotlib.ticker as ticker

    per   = metrics["per_class"]
    cm_df = metrics["confusion_matrix"]
    oa    = metrics["overall_accuracy"]
    kappa = metrics["kappa"]
    n     = metrics["n_test"]

    fig = plt.figure(figsize=(11, 7), facecolor=PANEL_BG)
    gs  = gridspec.GridSpec(2, 2, figure=fig,
                            left=0.07, right=0.97,
                            top=0.88,  bottom=0.06,
                            hspace=0.42, wspace=0.38)

    title_str = f"Accuracy Assessment  —  {year_label}  (n={n:,} test pixels)"
    fig.suptitle(title_str, color=TEXT_COL, fontsize=12,
                 fontweight="bold", fontfamily="monospace", y=0.96)

    # ── Banner: OA and Kappa ──────────────────────────────────────────────
    ax_banner = fig.add_subplot(gs[0, 0])
    ax_banner.set_facecolor(PANEL_BG)
    for sp in ax_banner.spines.values():
        sp.set_visible(False)
    ax_banner.set_xticks([]); ax_banner.set_yticks([])

    # Colour-code OA
    oa_col = "#16a34a" if oa >= 80 else ("#d97706" if oa >= 65 else "#dc2626")
    kappa_col = "#16a34a" if kappa >= 0.6 else ("#d97706" if kappa >= 0.4 else "#dc2626")

    ax_banner.text(0.5, 0.72, f"{oa}%",
                   ha="center", va="center", fontsize=38, fontweight="bold",
                   color=oa_col, transform=ax_banner.transAxes)
    ax_banner.text(0.5, 0.44, "Overall Accuracy",
                   ha="center", va="center", fontsize=10,
                   color=TEXT_COL, transform=ax_banner.transAxes,
                   fontfamily="monospace")
    ax_banner.text(0.5, 0.18, f"Cohen's κ = {kappa}",
                   ha="center", va="center", fontsize=10,
                   color=kappa_col, transform=ax_banner.transAxes,
                   fontfamily="monospace")

    # ── Per-class table ───────────────────────────────────────────────────
    ax_tbl = fig.add_subplot(gs[0, 1])
    ax_tbl.set_facecolor(PANEL_BG)
    for sp in ax_tbl.spines.values():
        sp.set_visible(False)
    ax_tbl.set_xticks([]); ax_tbl.set_yticks([])
    ax_tbl.set_title("Per-Class Metrics", color=ACC_COL,
                      fontsize=9, fontfamily="monospace", pad=4)

    col_labels = ["Class", "PA %", "UA %", "F1"]
    cell_text  = [[row["Class"], f"{row['PA_%']}", f"{row['UA_%']}", f"{row['F1']}"]
                  for _, row in per.iterrows()]

    tbl = ax_tbl.table(cellText=cell_text, colLabels=col_labels,
                       cellLoc="center", loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.5)

    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor(PANEL_BG)
        if r == 0:
            cell.set_facecolor(ACC_COL)
            cell.set_text_props(color="white", fontweight="bold",
                                fontfamily="monospace")
        else:
            cell.set_facecolor("#f0f9ff" if r % 2 == 0 else "#ffffff")
            cell.set_text_props(color=TEXT_COL)

    # ── Confusion matrix heatmap ──────────────────────────────────────────
    ax_cm = fig.add_subplot(gs[1, :])
    ax_cm.set_facecolor(PANEL_BG)
    ax_cm.set_title("Confusion Matrix", color=ACC_COL,
                     fontsize=9, fontfamily="monospace", pad=4)

    cm_arr = cm_df.values.astype(float)
    # Normalise by row (reference) for display
    row_sums = cm_arr.sum(axis=1, keepdims=True)
    cm_norm  = np.divide(cm_arr, row_sums,
                          out=np.zeros_like(cm_arr), where=row_sums != 0)

    im = ax_cm.imshow(cm_norm, cmap="Blues", vmin=0, vmax=1,
                       aspect="auto", interpolation="nearest")
    fig.colorbar(im, ax=ax_cm, fraction=0.025, pad=0.02,
                 label="Proportion")

    classes_short = [c.replace("Map:", "") for c in cm_df.columns]
    ax_cm.set_xticks(range(len(classes_short)))
    ax_cm.set_yticks(range(len(classes_short)))
    ax_cm.set_xticklabels(classes_short, color=TEXT_COL, fontsize=8,
                           fontfamily="monospace")
    ax_cm.set_yticklabels([c.replace("Ref:", "") for c in cm_df.index],
                           color=TEXT_COL, fontsize=8, fontfamily="monospace")
    ax_cm.set_xlabel("Predicted Class", color=TEXT_COL,
                      fontsize=9, fontfamily="monospace")
    ax_cm.set_ylabel("Reference Class", color=TEXT_COL,
                      fontsize=9, fontfamily="monospace")
    ax_cm.tick_params(colors=TEXT_COL)

    # Annotate cells with raw counts
    for i in range(len(classes_short)):
        for j in range(len(classes_short)):
            val  = int(cm_arr[i, j])
            norm = cm_norm[i, j]
            txt_col = "white" if norm > 0.5 else TEXT_COL
            ax_cm.text(j, i, str(val), ha="center", va="center",
                       color=txt_col, fontsize=8, fontfamily="monospace")

    _footer(fig)
    plt.savefig(output_path, dpi=180, bbox_inches="tight",
                facecolor=PANEL_BG)
    plt.close()
