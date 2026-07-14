"""PyInstaller bootstrap that configures writable paths before package import."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _bootstrap_environment() -> None:
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    root = base / "MaterialAIWorkbench"
    os.environ.setdefault("MATERIALAI_WORKSPACE_ROOT", str(root / "workspace"))
    os.environ.setdefault("MATERIALAI_ENV_FILE", str(root / "config" / ".env"))
    os.environ.setdefault("MATERIALAI_DESKTOP_LOG_DIR", str(root / "logs"))
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")


_bootstrap_environment()

from material_ai_workbench.desktop_launcher import main


if __name__ == "__main__":
    sys.exit(main())
