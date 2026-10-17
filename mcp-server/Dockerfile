FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY mcp_server ./mcp_server

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "mcp_server.main:app", "--host", "0.0.0.0", "--port", "8080"]
