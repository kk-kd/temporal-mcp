FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN uv pip install --system .

ENV TEMPORAL_ADDRESS=localhost:7233
ENV TEMPORAL_NAMESPACE=default

ENTRYPOINT ["temporal-mcp"]
