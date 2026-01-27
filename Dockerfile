FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENV=/app/.venv

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh -s -- --install-dir /usr/local/bin

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --python 3.11

COPY scripts/setup_pytorch_connectomics.sh ./scripts/setup_pytorch_connectomics.sh
RUN chmod +x scripts/setup_pytorch_connectomics.sh && \
    ./scripts/setup_pytorch_connectomics.sh --force && \
    uv pip install --directory /app --editable /app/pytorch_connectomics && \
    rm -rf /app/pytorch_connectomics/.git

COPY server_api ./server_api
COPY server_pytc ./server_pytc
COPY scripts/docker-entrypoint.sh ./scripts/docker-entrypoint.sh

RUN chmod +x scripts/docker-entrypoint.sh

EXPOSE 4242 4243 4244 6006

CMD ["./scripts/docker-entrypoint.sh"]
