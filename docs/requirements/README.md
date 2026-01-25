# MCPX 需求与验证

本目录包含 MCPX 各特性的需求文档和验证文档。

## 文档索引

| 日期 | 特性 | 需求文档 | 验证文档 |
|------|------|----------|----------|
| 2026-01-24 | 核心功能 | [core_features_requirements.md](./2026-01-24_core_features_requirements.md) | [core_features_verification.md](./2026-01-24_core_features_verification.md) |
| 2026-01-24 | Docker 支持 | [docker_requirements.md](./2026-01-24_docker_requirements.md) | [docker_verification.md](./2026-01-24_docker_verification.md) |
| 2026-01-25 | TOON 压缩 + 多模态 + 健康检查 | [toon_multimodal_requirements.md](./2026-01-25_toon_multimodal_requirements.md) | [toon_multimodal_verification.md](./2026-01-25_toon_multimodal_verification.md) |
| 2026-01-25 | Schema 压缩 | [schema_compression_requirements.md](./2026-01-25_schema_compression_requirements.md) | [schema_compression_verification.md](./2026-01-25_schema_compression_verification.md) |
| 2026-01-25 | MCP Resource 支持 | [mcp_resource_requirements.md](./2026-01-25_mcp_resource_requirements.md) | [mcp_resource_verification.md](./2026-01-25_mcp_resource_verification.md) |
| 2026-01-25 | Session Isolation 重构 | [proxyprovider_refactor_requirements.md](./2026-01-25_proxyprovider_refactor_requirements.md) | [proxyprovider_refactor_verification.md](./2026-01-25_proxyprovider_refactor_verification.md) |

---

## 项目概述

MCPX 是一个 MCP（Model Context Protocol）代理服务器，通过 `inspect`、`exec` 和 `resources` 三个工具实现按需加载 MCP 工具和资源，大幅减少初始上下文。

## 核心架构

```
AI → inspect (查询工具) / exec (执行工具) / resources (读取资源)
          ↓
    MCPX Proxy
          ↓
    Schema/Resource 缓存 + client_factory
          ↓
   Server 1 · Server 2 · Server N
   (Session Isolation: 每次请求独立会话)
```

## 核心类

| 类 | 文件 | 职责 |
|----|------|------|
| `Registry` | registry.py | client_factory 管理、工具/资源缓存、健康检查 |
| `Executor` | executor.py | 使用 client_factory 执行工具、TOON 压缩 |
| `ResourceInfo` | registry.py | 资源信息数据模型 |
| `ToonCompressor` | compression.py | TOON 压缩实现 |
| `HealthChecker` | health.py | 健康检查（使用临时会话） |
| `SchemaConverter` | schema_ts.py | JSON Schema → TypeScript 转换 |

## 工具接口

### inspect
查询可用工具及其 Schema

**参数**:
- `server_name` (必填): 服务器名称
- `tool_name` (可选): 工具名称

**返回**: `ToolResult` - 压缩后的 Schema + 原始数据

### exec
执行 MCP 工具

**参数**:
- `server_name` (必填): 服务器名称
- `tool_name` (必填): 工具名称
- `arguments` (可选): 工具参数

**返回**: `ToolResult` - 压缩后的结果 + 原始数据 / 多模态内容

### resources
读取 MCP 服务器资源

**参数**:
- `server_name` (必填): 服务器名称
- `uri` (必填): 资源 URI

**返回**:
- 文本资源: 字符串内容
- 二进制资源: 包含 uri、mime_type、blob (base64) 的字典
- 多项内容: 内容项列表

## 验证标准

### 8 大条款

| 条款 | 状态 | 验证方式 |
|------|------|----------|
| FastMCP 框架架构 | ✅ | 检查依赖、代码结构 |
| 工具注册表与缓存 | ✅ | 检查 Registry 实现 |
| 长连接执行器 | ✅ | 检查 Executor 实现 |
| MCP 代理服务器 | ✅ | 检查工具数量、接口实现 |
| 双传输方式支持 | ✅ | stdio + HTTP/SSE 功能测试 |
| 配置驱动 | ✅ | 配置文件、错误处理 |
| 错误处理与降级 | ✅ | 异常处理逻辑 |
| E2E 测试覆盖 | ✅ | 测试套件 |

### 验证命令

```bash
# 代码质量
uv run ruff check src/mcpx tests/
uv run mypy src/mcpx

# 测试
uv run pytest tests/ -v --cov=src/mcpx --cov-report=term
```

### 通过标准

- 覆盖率 ≥ 70%
- ruff 检查通过
- mypy --strict 通过
- E2E 测试全部通过
