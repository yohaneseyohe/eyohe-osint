FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# WeasyPrint runtime libs + chromium for screenshots/PDF fallback
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi8 libcairo2 libgdk-pixbuf-2.0-0 \
    shared-mime-info fonts-dejavu-core chromium ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/README.md ./
RUN uv sync --frozen --no-dev --all-extras --no-install-project
COPY apps/api/ ./
RUN uv sync --frozen --no-dev --all-extras
ENV CHROMIUM_PATH=/usr/bin/chromium
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "eyohe.main:app", "--host", "0.0.0.0", "--port", "8000"]
