# syntax=docker/dockerfile:1

# ---- 构建阶段：用 uv 安装依赖并产出虚拟环境 ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS builder
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

COPY . .
RUN uv sync --no-dev

# ---- 运行阶段：精简镜像、非 root 用户、健康检查 ----
FROM python:3.13-slim-bookworm AS runtime
RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app /app

RUN chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=4).status == 200 else 1)"

# 启动前先跑迁移，再起服务；多 worker 下迁移幂等可重复执行
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
