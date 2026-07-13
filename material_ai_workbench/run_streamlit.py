"""Console script entry point for launching the MaterialAI Workbench Streamlit app.

Usage:
  materialai-streamlit                # default port 8501
  materialai-streamlit --port 8502    # custom port
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    """Launch the Streamlit app from the installed package."""
    from streamlit.web import cli as stcli

    app_path = Path(__file__).resolve().parent / "streamlit_app.py"
    args = ["streamlit", "run", str(app_path)]

    # Pass through any extra CLI arguments
    args.extend(sys.argv[1:])
    if not any(a.startswith("--server.port") for a in sys.argv[1:]):
        args.append("--server.port=8501")

    sys.argv = args
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
