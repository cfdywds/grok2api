# ── Stage 1: 安装依赖 ──────────────────────────────────────────
FROM python:3.13-slim AS builder

ENV UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

# ── Stage 2: 运行镜像（不含 uv 工具链）──────────────────────────
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

ENV PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 仅复制已安装的依赖，不引入 uv、pyproject.toml、uv.lock
COPY --from=builder /opt/venv /opt/venv

COPY config.defaults.toml ./
COPY app ./app
COPY main.py ./
COPY scripts ./scripts

RUN mkdir -p /app/data /app/data/tmp /app/logs \
    && chmod +x /app/scripts/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/scripts/entrypoint.sh"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
