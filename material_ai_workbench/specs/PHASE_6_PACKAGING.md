# Phase 6: Packaging and DevOps

## Objective
Make the project installable as a proper Python package, containerized for deployment, and protected by CI.

## Prerequisites
- Phase 0 complete (git, config, tests, dependencies)
- Phases 1-5 functional (the package should contain working code)

---

## Task 6.1: Python Package with `pyproject.toml`

### Context
The project is structured as a Python package (`material_ai_workbench/__init__.py` exists) but has no build system. Developers must manually clone and set up. Convert to an installable package.

### New file: `pyproject.toml` at project root (D:\githubproject\pyLabFEA)

Note: this goes in the PARENT directory because the project imports `pylabfea` from the parent level. The package is `material_ai_workbench` inside the `pyLabFEA` repo.

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "material-ai-workbench"
version = "0.1.0"
description = "Closed-loop material AI system: ML yield models → Abaqus UMAT → surrogate predictions"
readme = "material_ai_workbench/README_CN.md"
license = {text = "MIT"}
requires-python = ">=3.10"
dependencies = [
    "numpy>=1.26",
    "scipy>=1.12",
    "matplotlib>=3.8",
    "scikit-learn>=1.4",
    "pandas>=2.2",
    "pylabfea",
]

[project.optional-dependencies]
web = ["streamlit>=1.32"]
dev = ["pytest>=8", "pytest-cov"]

[project.scripts]
material-ai-workbench = "material_ai_workbench.run_workbench:main"
material-ai-composite = "material_ai_workbench.run_composite_workflow:main"
material-ai-streamlit = "material_ai_workbench.streamlit_app:main"

[tool.setuptools]
packages = ["material_ai_workbench"]

[tool.setuptools.package-data]
material_ai_workbench = ["library/*.json"]

[tool.pytest.ini_options]
testpaths = ["material_ai_workbench/tests"]
pythonpath = ["."]

[tool.coverage.run]
source = ["material_ai_workbench"]
omit = ["material_ai_workbench/tests/*", "material_ai_workbench/specs/*"]
```

#### b) Ensure `streamlit_app.py` has a `main()` entry point

If `streamlit_app.py` does not have `def main():` at the bottom (it currently runs the app at module level), wrap the app launch:

```python
# At the bottom of streamlit_app.py, replace any direct execution with:
def main():
    """Entry point for `material-ai-streamlit` console script."""
    import sys
    from streamlit.web import cli as stcli
    from pathlib import Path

    app_path = Path(__file__).resolve()
    sys.argv = ["streamlit", "run", str(app_path)]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
```

### Acceptance Criteria
- `pip install -e .` from the parent directory installs the package
- `material-ai-workbench --material j2 --name test_pkg` runs successfully
- `python -c "from material_ai_workbench import run_material_workbench; print('OK')"` works
- `pip install -e ".[dev]"` installs pytest

---

## Task 6.2: Docker Image

### Context
The project depends on:
- A specific conda environment (`pylabfea`)
- Abaqus (for full functionality, but the container can't include Abaqus)
- pyLabFEA library

Create a Docker image for the non-Abaqus parts (training, visualization, data management). The image should work for demo and development without Abaqus.

### New file: `Dockerfile` at project root (D:\githubproject\pyLabFEA)

```dockerfile
FROM python:3.12-slim

LABEL org.opencontainers.image.title="MaterialAI Workbench"
LABEL org.opencontainers.image.description="Closed-loop material AI system for pyLabFEA"

# Install system dependencies for matplotlib and scipy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy package files
COPY pyproject.toml .
COPY material_ai_workbench/ material_ai_workbench/
COPY setup.py . 2>/dev/null || true

# Install
RUN pip install --no-cache-dir -e ".[web]"

# Create volume for output data
RUN mkdir -p /app/material_ai_workbench/runs \
    /app/material_ai_workbench/batches \
    /app/material_ai_workbench/cases

VOLUME ["/app/material_ai_workbench/runs", "/app/material_ai_workbench/library"]

EXPOSE 8501

# Default: start Streamlit
CMD ["streamlit", "run", "material_ai_workbench/streamlit_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
```

### New file: `docker-compose.yml` at project root (D:\githubproject\pyLabFEA)

```yaml
version: "3.8"

services:
  workbench:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./material_ai_workbench/runs:/app/material_ai_workbench/runs
      - ./material_ai_workbench/library:/app/material_ai_workbench/library
      - ./material_ai_workbench/cases:/app/material_ai_workbench/cases
    environment:
      - MATERIALAI_LLM_BASE_URL=${MATERIALAI_LLM_BASE_URL:-}
      - MATERIALAI_LLM_MODEL=${MATERIALAI_LLM_MODEL:-}
      - MATERIALAI_LLM_API_KEY=${MATERIALAI_LLM_API_KEY:-}
    restart: unless-stopped
```

### Acceptance Criteria
- `docker build -t material-ai-workbench .` succeeds
- `docker run -p 8501:8501 material-ai-workbench` starts Streamlit
- `curl http://localhost:8501` returns HTTP 200
- Training a J2 material works inside the container (no Abaqus needed)
- Volume mount preserves runs between container restarts

---

## Task 6.3: GitHub Actions CI Pipeline

### Context
Once the project is in a GitHub repository, CI should run tests, linting, and verify packaging on every PR.

### New file: `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run tests
        run: pytest material_ai_workbench/tests/ -v --tb=short --cov=material_ai_workbench

      - name: Check imports
        run: python -c "from material_ai_workbench import run_material_workbench, WorkbenchConfig, WorkbenchResult; print('Imports OK')"

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install ruff
        run: pip install ruff

      - name: Lint
        run: ruff check material_ai_workbench/ --ignore=E501,E722
        # E501: line too long (fine for our style)
        # E722: bare except (intentional in some scripts)

  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Verify package builds
        run: |
          pip install build
          python -m build --sdist --wheel
          ls -la dist/
```

### Acceptance Criteria
- Push a commit to a PR branch → CI runs
- `test` job runs pytest and passes
- `lint` job runs ruff and passes (with allowed ignores)
- `build` job produces `.whl` and `.tar.gz` in dist/
- CI completes in under 5 minutes

---

## Task 6.4: Streamlit UI Polish (Quick Wins)

### Context
The Streamlit UI (1990 lines) works but is utilitarian. Small improvements can dramatically improve the experience without a full rewrite.

### Changes to `streamlit_app.py`

#### a) Add page config at the very top
```python
st.set_page_config(
    page_title="MaterialAI Workbench",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)
```

#### b) Add a sidebar with navigation
Replace the 11-tab layout with a sidebar radio for cleaner navigation:
```python
with st.sidebar:
    st.title("MaterialAI Workbench")
    st.caption("Closed-loop material AI")

    page = st.radio(
        "Navigate",
        ["AI Tasks", "Material Training", "Data Import",
         "Case Library", "Abaqus MCP", "Abaqus Verification",
         "Composite RVE", "Batch Simulation", "Results Browser",
         "Surrogate Model", "Model Management"],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption(f"pyLabFEA v{FE.__version__}")
```

Then replace the current tab-based routing with an if-elif chain based on `page`.

#### c) Add progress indicators for long operations
Wrap `run_material_workbench()` calls with:
```python
with st.spinner("Training material model..."):
    result = run_material_workbench(config)
st.success(f"Training complete! Support vectors: {result.support_vectors}")
```

Apply similar `st.spinner()` / `st.progress()` patterns to:
- Data import
- Abaqus verification
- Batch execution
- Surrogate training

#### d) Consistent card layout for results
Create a reusable `_metric_card()` helper:
```python
def _metric_card(title: str, value: str | float, delta: str | None = None,
                 border: bool = True) -> None:
    """Render a metric in a card-like container."""
    with st.container(border=border):
        st.metric(label=title, value=value, delta=delta)
```

Use it in Results Browser and Model Management.

### Acceptance Criteria
- Sidebar navigation works and pages switch correctly
- `st.spinner()` visible during training (takes >1 second for user to see)
- Metric cards render with borders in Results Browser
- Page is "wide" by default (uses full screen width)
