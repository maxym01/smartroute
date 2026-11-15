# syntax=docker/dockerfile:1

# SmartRoute backend (FastAPI + Uvicorn).
#   runtime (default) - production image, application code only, non-root user
#   test              - runtime dependencies + dev tools + tests:  docker build --target test backend
#
# No .env and no SQLite database is copied into the image (see .dockerignore):
# configuration and secrets come from environment variables at run time,
# the databases live in the /data volume.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first (better layer caching); versions pinned by requirements-lock.txt.
COPY pyproject.toml requirements-lock.txt ./
COPY app ./app
RUN pip install . -c requirements-lock.txt


FROM base AS test
RUN pip install ".[dev]" -c requirements-lock.txt
COPY tests ./tests
CMD ["python", "-m", "pytest"]


FROM base AS runtime

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin smartroute \
    && mkdir -p /data \
    && chown smartroute:smartroute /data

# Absolute paths inside the data volume; override with environment variables if needed.
ENV DATABASE_URL=sqlite:////data/smartroute.db \
    GTFS_DATABASE_URL=sqlite:////data/gtfs.db

USER smartroute
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import json, sys, urllib.request; r = urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4); sys.exit(0 if json.load(r).get('status') == 'ok' else 1)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
