"""Central configuration for MaterialAI Workbench.

Environment variables are optional overrides.  Explicit function arguments still
take precedence over these defaults.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


_DEFAULT_ABAQUS_ROOT = Path(
    _env("MATERIALAI_ABAQUS_ROOT", str(Path("D:/") / "ABAQUS" / "2023"))
)
ABAQUS_BAT = Path(
    _env(
        "MATERIALAI_ABAQUS_BAT",
        _env("ABAQUS_BAT", str(_DEFAULT_ABAQUS_ROOT / "Commands" / "abaqus.bat")),
    )
)
ABAQUS_SMAPYTHON = Path(
    _env(
        "MATERIALAI_ABAQUS_SMAPYTHON",
        _env(
            "ABAQUS_SMAPYTHON",
            str(
                _DEFAULT_ABAQUS_ROOT
                / "EstProducts"
                / "win_b64"
                / "code"
                / "bin"
                / "SMAPython.exe"
            ),
        ),
    )
)

ABAQUS_MCP_HOST = _env("MATERIALAI_ABAQUS_MCP_HOST", "127.0.0.1")
ABAQUS_MCP_PORT = int(_env("MATERIALAI_ABAQUS_MCP_PORT", "48152"))
ABAQUS_MCP_TIMEOUT = float(_env("MATERIALAI_ABAQUS_MCP_TIMEOUT", "10"))

_DEFAULT_WORKSPACE = (
    REPO_ROOT / "workspace"
    if (REPO_ROOT / "pyproject.toml").exists()
    else Path.home() / "MaterialAIWorkbench"
)
WORKSPACE_ROOT = Path(
    _env("MATERIALAI_WORKSPACE_ROOT", str(_DEFAULT_WORKSPACE))
).expanduser()
RUNS_ROOT = Path(_env("MATERIALAI_RUNS_ROOT", str(WORKSPACE_ROOT / "runs")))
CASES_ROOT = Path(_env("MATERIALAI_CASES_ROOT", str(WORKSPACE_ROOT / "cases")))
BATCHES_ROOT = Path(_env("MATERIALAI_BATCHES_ROOT", str(WORKSPACE_ROOT / "batches")))
COMPOSITE_ROOT = Path(
    _env("MATERIALAI_COMPOSITE_ROOT", str(WORKSPACE_ROOT / "composite_runs"))
)
COMPOSITE_BATCH_ROOT = Path(
    _env("MATERIALAI_COMPOSITE_BATCH_ROOT", str(WORKSPACE_ROOT / "composite_batches"))
)
COMPOSITE_SURROGATE_ROOT = Path(
    _env(
        "MATERIALAI_COMPOSITE_SURROGATE_ROOT",
        str(WORKSPACE_ROOT / "composite_surrogates"),
    )
)
SURROGATES_ROOT = Path(
    _env("MATERIALAI_SURROGATES_ROOT", str(WORKSPACE_ROOT / "surrogates"))
)
IMPORTS_ROOT = Path(_env("MATERIALAI_IMPORTS_ROOT", str(WORKSPACE_ROOT / "imports")))
DATASETS_ROOT = Path(_env("MATERIALAI_DATASETS_ROOT", str(WORKSPACE_ROOT / "datasets")))
EXPERIMENTS_ROOT = Path(
    _env("MATERIALAI_EXPERIMENTS_ROOT", str(WORKSPACE_ROOT / "experiments"))
)
CLOSED_LOOP_ROOT = Path(
    _env("MATERIALAI_CLOSED_LOOP_ROOT", str(WORKSPACE_ROOT / "closed_loop_reports"))
)
MCP_SESSIONS_ROOT = Path(
    _env("MATERIALAI_MCP_SESSIONS_ROOT", str(WORKSPACE_ROOT / "mcp_sessions"))
)
DIAGNOSTICS_ROOT = Path(
    _env("MATERIALAI_DIAGNOSTICS_ROOT", str(WORKSPACE_ROOT / "diagnostics"))
)
ACCEPTANCE_ROOT = Path(
    _env("MATERIALAI_ACCEPTANCE_ROOT", str(WORKSPACE_ROOT / "acceptance_runs"))
)

LLM_BASE_URL = _env("MATERIALAI_LLM_BASE_URL", "")
LLM_MODEL = _env("MATERIALAI_LLM_MODEL", "")
LLM_API_KEY_ENV = _env("MATERIALAI_LLM_API_KEY_ENV", "MATERIALAI_LLM_API_KEY")
