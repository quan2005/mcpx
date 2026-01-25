# Docker 支持验证文档

**版本**: v0.2.0
**日期**: 2026-01-24
**对应需求**: [docker_requirements.md](./2026-01-24_docker_requirements.md)

## 1. 测试概述

本文档定义 Docker 支持的验证测试用例。

## 2. 构建测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_docker_build` | Docker 镜像构建 | `docker build -t mcpx .` | 构建成功，无错误 |
| `test_image_size` | 镜像体积检查 | `docker images mcpx` | < 500 MB |
| `test_layers` | 镜像层数检查 | `docker history mcpx` | 合理的层数 |

## 3. 运行测试

### 3.1 基础运行

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_container_start` | 容器启动 | `docker run mcpx` | 容器正常启动 |
| `test_port_binding` | 端口绑定 | `-p 8000:8000` | 端口正确监听 |
| `test_config_mount` | 配置挂载 | `-v config.json:/app/config.json` | 配置正确加载 |

### 3.2 HTTP/SSE 测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_http_endpoint` | HTTP 端点访问 | `curl http://localhost:8000/mcp/` | 返回 MCP 响应 |
| `test_sse_connection` | SSE 连接 | curl SSE 端点 | 连接成功 |
| `test_cors` | CORS 支持 | 带 Origin 头请求 | 返回正确 CORS 头 |

## 4. Docker Compose 测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_compose_up` | 启动服务 | `docker compose up -d` | 服务成功启动 |
| `test_compose_ps` | 服务状态 | `docker compose ps` | 状态为 Up |
| `test_compose_down` | 停止服务 | `docker compose down` | 服务成功停止 |

## 5. 配置测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_config_override` | 配置覆盖 | 挂载不同配置 | 使用挂载的配置 |
| `test_env_vars` | 环境变量 | 设置 PORT 环境变量 | 使用指定端口 |

## 6. 集成测试

### 6.1 MCP 工具调用

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_inspect_tool` | inspect 工具 | HTTP 调用 inspect | 返回工具列表 |
| `test_exec_tool` | exec 工具 | HTTP 调用 exec | 返回执行结果 |

## 7. 故障恢复测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_invalid_config` | 无效配置 | 挂载无效 JSON | 容器报错并退出 |
| `test_missing_config` | 缺失配置 | 不挂载配置 | 容器报错并退出 |
| `test_port_conflict` | 端口冲突 | 端口已被占用 | 容器启动失败 |

## 8. 验收标准

所有测试用例通过，且：
- Dockerfile 优化合理（多阶段构建）
- 镜像体积 < 500 MB
- 文档完整（README + Docker Compose 示例）
