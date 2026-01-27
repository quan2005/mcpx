# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 核心目标

MCP 代理服务器，将多个 MCP 服务器聚合为 `describe`、`call` 和 `resources` 三个工具，AI 按需查询工具/资源、执行工具和读取资源，减少初始上下文。

## 常用命令

```bash
# 运行测试
uv run pytest tests/ -v --cov=src/mcpx

# 运行单个测试
uv run pytest tests/test_mcpx.py -v

# 代码检查
uv run ruff check src/mcpx tests/

# 类型检查
uv run mypy src/mcpx

# HTTP/SSE 模式运行（默认端口 8000）
uv run mcpx-toolkit config.json

# 指定端口和主机
uv run mcpx-toolkit --port 3000 --host 127.0.0.1 config.json
```

## 开发流程

本项目使用 **skills** 规范 AI 开发流程（位于 `.claude/skills/`）。

### 开始开发前的第一步

**告诉 AI：加载 mcpx-getting-started skill**

这会加载项目的所有开发流程规范。

### 完整开发流程

```
1. TDD 开发 (mcpx-tdd-workflow)
   ├─ RED:   先写失败的测试
   ├─ GREEN: 写最小代码使测试通过
   └─ REFACTOR: 优化代码结构

2. 代码检查 (mcpx-code-quality)
   ├─ uv run ruff format src/mcpx tests/
   ├─ uv run ruff check src/mcpx tests/
   ├─ uv run mypy src/mcpx
   └─ uv run pytest tests/ -v --cov=src/mcpx (覆盖率 ≥ 70%)

3. 文档更新 (mcpx-documentation)
   ├─ CLAUDE.md (AI 开发指南)
   ├─ README.md (用户文档)
   └─ docs/roadmap.md (功能状态)

4. 提交代码
   └─ git commit -m "<type>: <中文描述>"
```

### Skills 快速参考

| Skill | 用途 | 触发时机 |
|-------|------|----------|
| `mcpx-getting-started` | 入口，加载所有 skills | 开始任何工作前 |
| `mcpx-tdd-workflow` | TDD 开发（RED-GREEN-REFACTOR） | 实现功能或 bug 修复 |
| `mcpx-code-quality` | 代码质量检查（lint/types/test） | 提交代码前 |
| `mcpx-documentation` | 文档更新规范 | 代码变更影响功能时 |
| `mcpx-release` | 版本发布流程 | 准备发布版本时 |

### 提交规范

```
<type>: <中文描述>

类型：feat, fix, docs, style, refactor, perf, test, chore
```

## 技术栈

- **FastMCP 3.0** - MCP 服务器框架（`@mcp.tool` 装饰器注册工具）
- **Pydantic v2** - 数据模型和校验
- **uv** - 依赖管理和运行
- **toons** - TOON 压缩格式

## 项目结构

```
src/mcpx/
├── __main__.py    # 入口、describe/call/resources 工具定义
├── config.py      # ProxyConfig、McpServerConfig 配置模型
├── registry.py    # Registry 类：连接管理、工具/资源缓存、健康检查
├── executor.py    # Executor 类：工具执行、TOON 压缩
├── compression.py # ToonCompressor：TOON 压缩实现
├── schema_ts.py   # json_schema_to_typescript：Schema 压缩
├── content.py     # 多模态内容处理（TextContent/ImageContent/EmbeddedResource）
├── health.py      # HealthChecker：健康检查和重连
└── port_utils.py  # find_available_port：端口可用性检测和自动切换
```

## 核心架构

### 设计模式

MCPX 将多个 MCP 服务器的工具和资源收敛为三个入口点：
- **describe**: 查询工具列表和 Schema（按需获取详情），使用 method 参数（如 "server" 或 "server.tool"）
- **call**: 执行工具（使用 method 参数，格式为 "server.tool"），使用 client_factory 每次创建新会话
- **resources**: 列出或读取 MCP 服务器的资源（支持文本和二进制内容）

### 三大核心类

**Registry（注册表）**
- 启动时连接所有 MCP 服务器（stdio 或 HTTP/SSE）获取工具/资源 Schema
- 使用 FastMCP 的 **client_factory 模式**（Session Isolation）
- 维护 client factory `_client_factories: dict[str, Callable[[], McpClient]]`
- 缓存工具 Schema `_tools: dict[str, ToolInfo]`
- 缓存资源信息 `_resources: dict[str, ResourceInfo]`
- 缓存服务器信息 `_server_infos: dict[str, ServerInfo]`
- 集成健康检查 `HealthChecker`（使用临时会话）

**Executor（执行器）**
- 每次请求通过 `client_factory()` 创建新会话
- 使用 `async with client:` 自动管理会话生命周期
- TOON 压缩响应数据
- 多模态内容透传（图片/资源）

**ToonCompressor（压缩器）**
- 将 JSON 数据压缩为 TOON 格式
- 返回 `content`（压缩后）和 `structured_content`（原始）
- 可配置最小压缩阈值

### 数据流

```
AI → describe(method="server.tool") → Registry._tools (缓存) → 压缩的 Schema
AI → call(method="server.tool", arguments={...}) → Executor → client_factory() → 临时会话 → MCP Server → TOON 压缩结果
AI → resources → Registry._resources (缓存) / read_resource() → 资源列表或内容
```

### Session Isolation 模式

使用 FastMCP 的 client_factory 模式实现会话隔离：

```python
# Registry 初始化时创建 factory
for server_name, server_config in self._config.mcpServers.items():
    factory = self._create_client_factory(server_config)
    self._client_factories[server_name] = factory

# Executor 每次请求创建新会话
factory = self._registry.get_client_factory(server_name)
client = factory()
async with client:
    result = await client.call_tool(tool_name, arguments)
# 会话自动关闭
```

## 关键实现细节

### 1. describe/call method 参数格式

使用 `method` 参数指定目标工具，格式为 `server.tool` 或仅 `server`：

```python
# 查询服务器所有工具
describe(method="filesystem")          # 列出 filesystem 服务器的所有工具

# 查询特定工具的 schema
describe(method="filesystem.read_file")  # 获取 read_file 工具的详细 schema

# 执行工具
call(method="filesystem.read_file", arguments={"path": "/tmp/file.txt"})
```

### 2. 双返回格式

`describe` 和 `call` 都返回 `ToolResult`，包含：
- `content`: TOON 压缩后的字符串（供 AI 阅读）
- `structured_content`: 原始 JSON（供程序解析）

### 3. 多模态内容透传

`call` 返回类型支持多种内容：
- `ToolResult`: 普通数据（压缩 + 原始）
- `TextContent | ImageContent | EmbeddedResource`: 单项多模态内容
- `list[TextContent | ImageContent | EmbeddedResource]`: 多项多模态内容

透传逻辑在 `Executor._extract_result_data()`。

### 4. HTTP/SSE 模式的事件循环

`main()` 需要特殊处理：
- 在临时 asyncio.run() 中预连接获取工具描述
- 在 uvicorn lifespan 中重新初始化 Registry
- 避免跨事件循环的连接问题

### 5. 参数校验

`call` 执行前校验：
- 必填字段（`required`）
- 未知参数（不在 `properties` 中）

### 6. 健康检查

`HealthChecker` 在后台定期探测服务器健康状态：
- 使用临时会话（通过 `client_factory()` 创建）
- 使用 `async with client:` 自动管理会话生命周期
- 检查完成后自动关闭临时会话
- 失败阈值达到后标记服务器不健康
- 提供 `get_server_health()` 查询状态

### 7. 端口自动切换

`main()` 启动前自动检测端口可用性：
- 使用 `find_available_port(port, host)` 检测端口是否被占用
- 如果端口被占用，自动尝试下一个可用端口（最多 100 次）
- 启动日志会显示实际使用的端口
- 实现位于 `port_utils.py` 模块

## 配置

MCPX 使用 Claude Code 兼容的配置格式：

```json
{
  "mcpServers": {
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    },
    "http-server": {
      "type": "http",
      "url": "http://localhost:3000/mcp",
      "headers": {"Authorization": "Bearer xxx"}
    }
  },
  "schema_compression_enabled": true,
  "toon_compression_enabled": true,
  "toon_compression_min_size": 3,
  "health_check_enabled": true,
  "health_check_interval": 30
}
```

### 配置说明

- `mcpServers`: 服务器配置字典（key 为服务器名称）
  - `type`: 传输类型，`"stdio"` 或 `"http"`（默认 `"stdio"`）
    - `"http"` 类型会自动检测：URL 包含 `/sse` 使用 `SSETransport`，否则使用 `StreamableHttpTransport`
  - `command`: stdio 类型的命令
  - `args`: 命令参数数组
  - `env`: 环境变量字典（可选）
  - `url`: http 类型的 URL（支持 SSE 和 Streamable HTTP）
  - `headers`: HTTP 请求头（可选）

## 测试要求

- 覆盖率 ≥ 70%
- 使用 pytest-asyncio 运行异步测试
- E2E 测试覆盖核心流程

## 当前分支

分支名与当前任务相关，PR 合并目标为 `main`。
