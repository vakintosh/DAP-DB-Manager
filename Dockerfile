FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv"

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN uv pip install --no-cache .

FROM python:3.11-slim

RUN apt-get purge -y --allow-remove-essential --auto-remove apt && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/*

RUN useradd --create-home --shell /bin/bash --uid 1000 ddm

RUN mkdir -p /input /output /tmp /home/ddm/.cache && \
    chown -R ddm:ddm /input /output /tmp /home/ddm

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

USER ddm

VOLUME ["/input", "/output", "/tmp"]

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=1 \
    CMD ["ddm", "--version"]

LABEL security.readonly_root="true" \
      security.capabilities_drop="ALL" \
      security.run_as_user="1000"

ENTRYPOINT ["ddm"]
CMD ["--help"]
