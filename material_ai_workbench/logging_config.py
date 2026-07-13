"""Logging helpers for MaterialAI Workbench."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from material_ai_workbench.config import WORKSPACE_ROOT

LOG_DIR = Path(os.environ.get("MATERIALAI_LOG_DIR", str(WORKSPACE_ROOT / "logs"))).expanduser()
LOG_FILE = LOG_DIR / "material_ai_workbench.log"
_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    """Configure console and rotating-file logging once per process."""

    global _CONFIGURED
    if _CONFIGURED:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root = logging.getLogger("material_ai_workbench")
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
