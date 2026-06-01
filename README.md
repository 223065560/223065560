# GeoSight — Automated Land Cover Change Detection

**Module:** GIS Programming  
**Author:** Justine Shimpiku · 223065560  
**Institution:** Namibia University of Science and Technology  
**Study Area:** Rundu, Kavango East, Namibia  

---

## What is GeoSight?

GeoSight is a desktop application that automates multi-temporal land cover classification and change detection using Landsat satellite imagery. It replaces manual GIS workflows — including field-based ground-truth collection — with a Random Forest machine learning pipeline that runs in a few clicks.

**Supported inputs:** Landsat 5 TM · Landsat 7 ETM+ · Landsat 8/9 OLI (GEE Collection 2 exports)  
**Output classes:** Vegetation · Built-up · Water · Bare Land  

---

## Features

| Feature | Details |
|---|---|
| 🌍 Multi-temporal classification | Compare any two years side-by-side |
| 🤖 Random Forest classifier | 200 trees, adaptive training samples, confidence refinement |
| 📊 Accuracy assessment | Overall Accuracy, Cohen's Kappa, PA/UA/F1 per class, confusion matrix |
| 📍 GCP validation | Upload a CSV of field-collected ground control points for true independent validation |
| ⚙ Preprocessing | Auto-scales raw GEE exports to reflectance and computes NDVI/NDBI |
| 🗺 Map exports | Classification maps, change map, side-by-side comparison, confidence maps, area chart |
| 📁 CSV statistics | Land cover areas (km²) and inter-epoch transition table |

---

## ⬇️ Download

> **The compiled Windows executable is too large for GitHub (>100 MB) and is hosted on Google Drive.**

### [👉 Click here to download LandCoverTool.exe](https://drive.google.com/file/d/1iQE5W1Tju2-D18wFwSnZgji8jeL1yM-O/view?usp=sharing)

No Python installation required — just download and run.

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- pip

### Install dependencies

```bash
cd LandCoverTool
pip install -r requirements.txt
```

### Run the application

```bash
python main.py
```

### Build the Windows executable

```bash
python build.py
```

The `.exe` will appear in the `dist/` folder.  
> **Note:** The compiled executable is not included in this repository (it exceeds GitHub's 25 MB file limit). Build it locally using the command above.

---

## Preparing Your Satellite Images

Images must be exported from **Google Earth Engine** as GeoTIFFs with the following band order:

```
SR_B2 (Blue) · SR_B3 (Green) · SR_B4 (Red)
SR_B5 (NIR)  · SR_B6 (SWIR1) · SR_B7 (SWIR2)
NDVI · NDBI
```

All bands must be **Float32**. Cast before export in GEE:

```javascript
var image = yourImage
  .select(['SR_B2','SR_B3','SR_B4','SR_B5','SR_B6','SR_B7'])
  .addBands(ndvi).addBands(ndbi)
  .toFloat();
```

If you have raw exports, enable **⚙ Preprocess images** in the application and it will handle scaling and band arrangement automatically.

---

## GCP CSV Format

To run a proper independent accuracy assessment, provide a CSV file with field-collected reference points:

```csv
longitude,latitude,class_id
17.923,-17.941,2
17.910,-17.935,1
17.931,-17.952,4
```

| class_id | Class |
|---|---|
| 1 | Vegetation |
| 2 | Built-up |
| 3 | Water |
| 4 | Bare Land |

---

## Project Structure

```
LandCoverTool/
├── main.py          # GUI application (Tkinter)
├── classify.py      # Random Forest classifier + training sample generation
├── change.py        # Change detection + temporal consistency constraints
├── accuracy.py      # Accuracy assessment (self-consistency + GCP-based)
├── preprocess.py    # Raw image scaling and band harmonisation
├── export.py        # Map and chart generation (Matplotlib)
├── areas.py         # Land cover area statistics
├── build.py         # PyInstaller build script
└── requirements.txt # Python dependencies
```

---

## Requirements

```
numpy
rasterio
scikit-learn
matplotlib
pandas
pyproj
```

---

## License

This project was developed as an academic submission for the GIS Programming module at NUST. 
