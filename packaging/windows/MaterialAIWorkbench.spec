import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata


ROOT = Path(SPECPATH).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

datas = []
binaries = []
hiddenimports = []

streamlit_data, streamlit_binaries, streamlit_hidden = collect_all("streamlit")
datas += streamlit_data
binaries += streamlit_binaries
hiddenimports += [
    module
    for module in streamlit_hidden
    if not module.startswith(("streamlit.testing", "streamlit.hello"))
]

datas += collect_data_files("webview")
hiddenimports += [
    "material_ai_workbench.streamlit_app",
    "pylabfea",
    "pylabfea.basic",
    "pylabfea.data",
    "pylabfea.material",
    "pylabfea.model",
    "pylabfea.training",
    "webview",
    "webview.platforms.edgechromium",
    "webview.platforms.mshtml",
    "webview.platforms.win32",
    "webview.platforms.winforms",
]
datas += [(str(ROOT / "material_ai_workbench" / "streamlit_app.py"), "material_ai_workbench")]
datas += collect_data_files(
    "material_ai_workbench",
    includes=["library/*.json", "resources/*.png", "resources/umat/*"],
)
datas += collect_data_files("pylabfea")

for distribution in (
    "materialai-workbench",
    "streamlit",
    "pywebview",
    "plotly",
    "pandas",
    "numpy",
    "scipy",
    "scikit-learn",
    "matplotlib",
    "pillow",
    "openpyxl",
):
    try:
        datas += copy_metadata(distribution)
    except Exception:
        pass


a = Analysis(
    [str(ROOT / "packaging" / "windows" / "materialai_desktop.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "IPython",
        "PySide6",
        "black",
        "dask",
        "ipykernel",
        "jupyter",
        "notebook",
        "pylabfea.gui",
        "pytest",
        "streamlit.hello",
        "streamlit.testing",
        "tensorflow",
        "tkinter",
        "torch",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MaterialAIWorkbench",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=str(ROOT / "packaging" / "windows" / "materialai.ico"),
    codesign_identity=None,
    entitlements_file=None,
    version=str(ROOT / "packaging" / "windows" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MaterialAIWorkbench",
)
