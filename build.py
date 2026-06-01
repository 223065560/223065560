"""
build.py  —  GeoSight Build Script
Strips unused library data to keep the exe under 100 MB.
"""
import subprocess
import sys
import os

def run(args):
    print(f"\n>>> {' '.join(args)}\n")
    result = subprocess.run(args)
    if result.returncode != 0:
        print(f"[ERROR] Command failed: {' '.join(args)}")
        sys.exit(1)

print("=" * 55)
print("  GeoSight  —  Build Script")
print("=" * 55)

print("\n[1/2] Installing dependencies...")
run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

print("\n[2/2] Building executable...")
run([
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--onefile", "--windowed",
    "--name", "LandCoverTool",

    # ── Collect geo/ML packages fully (Cython extensions) ──────────────
    "--collect-all", "rasterio",
    "--collect-all", "fiona",
    "--collect-all", "shapely",
    "--collect-all", "pyproj",
    "--collect-all", "sklearn",

    # ── Exclude heavy unused modules ────────────────────────────────────
    # Test suites
    "--exclude-module", "sklearn.tests",
    "--exclude-module", "numpy.testing",
    "--exclude-module", "numpy.tests",
    "--exclude-module", "pandas.tests",
    "--exclude-module", "matplotlib.tests",
    "--exclude-module", "rasterio.tests",

    # IPython / Jupyter (not needed in a desktop app)
    "--exclude-module", "IPython",
    "--exclude-module", "ipykernel",
    "--exclude-module", "ipywidgets",
    "--exclude-module", "jupyter",
    "--exclude-module", "notebook",

    # Unused stdlib / heavy modules
    "--exclude-module", "tkinter.test",
    "--exclude-module", "unittest",
    "--exclude-module", "pydoc",
    "--exclude-module", "doctest",
    "--exclude-module", "lib2to3",
    "--exclude-module", "distutils",
    "--exclude-module", "setuptools",
    "--exclude-module", "pkg_resources",
    "--exclude-module", "pip",

    # Unused scipy (if pulled in transitively)
    "--exclude-module", "scipy.fft",
    "--exclude-module", "scipy.signal",
    "--exclude-module", "scipy.linalg",
    "--exclude-module", "scipy.optimize",
    "--exclude-module", "scipy.interpolate",
    "--exclude-module", "scipy.stats",
    "--exclude-module", "scipy.spatial",
    "--exclude-module", "scipy.ndimage",
    "--exclude-module", "scipy.io",

    # Unused matplotlib backends
    "--exclude-module", "matplotlib.backends.backend_gtk3",
    "--exclude-module", "matplotlib.backends.backend_gtk3agg",
    "--exclude-module", "matplotlib.backends.backend_gtk3cairo",
    "--exclude-module", "matplotlib.backends.backend_qt5",
    "--exclude-module", "matplotlib.backends.backend_qt5agg",
    "--exclude-module", "matplotlib.backends.backend_wxagg",
    "--exclude-module", "matplotlib.backends.backend_wx",
    "--exclude-module", "matplotlib.backends._backend_tk",

    # Cryptography / network (not used)
    "--exclude-module", "cryptography",
    "--exclude-module", "ssl",
    "--exclude-module", "http",
    "--exclude-module", "urllib",
    "--exclude-module", "email",
    "--exclude-module", "xmlrpc",
    "--exclude-module", "ftplib",
    "--exclude-module", "imaplib",
    "--exclude-module", "smtplib",
    "--exclude-module", "poplib",

    # Source files
    "--add-data", f"classify.py{os.pathsep}.",
    "--add-data", f"change.py{os.pathsep}.",
    "--add-data", f"areas.py{os.pathsep}.",
    "--add-data", f"export.py{os.pathsep}.",
    "--add-data", f"preprocess.py{os.pathsep}.",
    "--add-data", f"accuracy.py{os.pathsep}.",

    "main.py",
])

print("\n" + "=" * 55)
print("  ✅  Done!  Check the /dist folder for LandCoverTool.exe")
print("  Tip: if still >100MB, upload to Google Drive and link")
print("       in README — GitHub Releases cap is 100MB.")
print("=" * 55)
