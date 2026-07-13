from __future__ import annotations

import py_compile
from pathlib import Path


def test_streamlit_app_is_python_syntax_valid() -> None:
    app_path = Path("material_ai_workbench/streamlit_app.py")
    py_compile.compile(str(app_path), doraise=True)
