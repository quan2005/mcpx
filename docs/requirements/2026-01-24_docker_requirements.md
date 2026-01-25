# Docker 支持需求文档

**版本**: v0.2.0
**日期**: 2026-01-24
**状态**: ✅ 已完成

## 1. 概述

为 MCPX 添加 Docker 容器化支持，便于部署和运行。

## 2. 核心需求

### 2.1 容器化构建

**需求描述**: 支持 Docker 多阶段构建

**功能要求**:
- 使用 Python 3.12-slim 基础镜像
- 多阶段构建减小镜像体积
- uv 作为依赖管理工具
- 包含运行时依赖 (Node.js/npm 用于 MCP 服务器)

### 2.2 HTTP/SSE 传输增强

**需求描述**: 完善 HTTP/SSE 传输方式

**功能要求**:
- 支持 CORS 跨域
- 支持自定义端口和主机
- 正确的生命周期管理

### 2.3 配置挂载

**需求描述**: 支持通过卷挂载配置文件

**功能要求**:
- 配置文件路径可配置
- 支持热更新（重启容器）

## 3. 交付物

### 3.1 文件

| 文件 | 说明 |
|------|------|
| `Dockerfile` | 多阶段构建配置 |
| `.dockerignore` | 排除不必要的文件 |
| `README.md` | Docker 部署文档 |
| `docs/roadmap.md` | 更新路线图 |

### 3.2 Dockerfile 规格

```dockerfile
# 构建阶段
FROM python:3.12-slim AS builder
# 安装 uv
# 复制项目文件
# 安装依赖

# 运行阶段
FROM python:3.12-slim
# 安装 Node.js 运行时
# 复制构建产物
# 暴露端口 8000
# 入口点: mcpx-sse
```

## 4. 部署方式

### 4.1 直接运行

```bash
docker build -t mcpx:latest .
docker run -p 8000:8000 -v $(pwd)/config.json:/app/config.json mcpx:latest
```

### 4.2 Docker Compose

```yaml
services:
  mcpx:
    image: mcpx:latest
    ports:
      - "8000:8000"
    volumes:
      - ./config.json:/app/config.json
    restart: unless-stopped
```

## 5. 验收标准

- [ ] Docker 镜像成功构建
- [ ] 容器成功启动并监听端口 8000
- [ ] 可以通过 HTTP/SSE 访问 MCP 服务
- [ ] 配置文件挂载正常工作
- [ ] Docker Compose 部署成功

## 6. 配置选项

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `PORT` | HTTP 端口 | 8000 |
| `HOST` | 绑定地址 | 0.0.0.0 |
| `PYTHONUNBUFFERED` | Python 输出非缓冲 | 1 |
