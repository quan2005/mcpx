# MCPX Dockerfile
# 多阶段构建，使用 uv 进行依赖管理

FROM python:3.12-slim AS builder

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 设置工作目录
WORKDIR /app

# 复制项目文件（README.md 被 pyproject.toml 引用）
COPY pyproject.toml uv.lock README.md ./
COPY src/mcpx ./src/mcpx

# 安装依赖（使用 --frozen 确保可复现构建）
RUN uv sync --frozen --no-dev

# 运行阶段
FROM python:3.12-slim

# 安装运行时依赖（npx 用于 Node.js MCP 服务器）
RUN apt-get update && \
    apt-get install -y --no-install-recommends nodejs npm && \
    rm -rf /var/lib/apt/lists/*

# 从 uv 镜像复制 uv 工具
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 设置工作目录
WORKDIR /app

# 从构建阶段复制虚拟环境和源码
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY pyproject.toml ./

# 确保 Python 能找到虚拟环境
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# 默认入口点（HTTP/SSE 模式）
ENTRYPOINT ["mcpx-sse"]

# 暴露 HTTP/SSE 端口
EXPOSE 8000

# 默认参数（使用示例配置）
CMD ["config.json"]
