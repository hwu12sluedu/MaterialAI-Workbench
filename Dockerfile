FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MPLBACKEND=Agg

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE NOTICE.md CHANGELOG.md THIRD_PARTY_LICENSES requirements.txt ./
COPY src ./src
COPY material_ai_workbench ./material_ai_workbench
COPY examples ./examples
COPY docs ./docs
COPY configs ./configs
COPY schemas ./schemas
COPY .streamlit ./.streamlit
COPY MANIFEST.in ./

RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir -e ".[app]"

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)"

CMD ["streamlit", "run", "material_ai_workbench/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
