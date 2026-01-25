# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 核心目标

MCP 代理服务器，将多个 MCP 服务器聚合为 `inspect`、`exec` 和 `resources` 三个工具，AI 按需查询工具/资源、执行工具和读取资源，减少初始上下文。

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

# stdio 模式运行
uv run mcpx config.json

# HTTP/SSE 模式运行
uv run mcpx-sse config.json
```

## 技术栈

- **FastMCP 3.0** - MCP 服务器框架（`@mcp.tool` 装饰器注册工具）
- **Pydantic v2** - 数据模型和校验
- **uv** - 依赖管理和运行
- **toons** - TOON 压缩格式

## 项目结构

```
src/mcpx/
├── __main__.py    # 入口、inspect/exec/resources 工具定义
├── config.py      # ProxyConfig、McpServerConfig 配置模型
├── registry.py    # Registry 类：连接管理、工具/资源缓存、健康检查
├── executor.py    # Executor 类：工具执行、TOON 压缩
├── compression.py # ToonCompressor：TOON 压缩实现
├── schema_ts.py   # json_schema_to_typescript：Schema 压缩
├── content.py     # 多模态内容处理（TextContent/ImageContent/EmbeddedResource）
└── health.py      # HealthChecker：健康检查和重连
```

## 核心架构

### 设计模式

MCPX 将多个 MCP 服务器的工具和资源收敛为三个入口点：
- **inspect**: 查询工具列表和 Schema（按需获取详情）
- **exec**: 执行工具（使用 client_factory 每次创建新会话）
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
AI → inspect → Registry._tools (缓存) → 压缩的 Schema
AI → exec → Executor → client_factory() → 临时会话 → MCP Server → TOON 压缩结果
AI → resources → Registry._resources (缓存) / read_resource() → 资源列表或内容
```

### Session Isolation 模式

使用 FastMCP 的 client_factory 模式实现会话隔离：

```python
# Registry 初始化时创建 factory
factory = self._create_client_factory(server_config)
self._client_factories[server_config.name] = factory

# Executor 每次请求创建新会话
factory = self._registry.get_client_factory(server_name)
client = factory()
async with client:
    result = await client.call_tool(tool_name, arguments)
# 会话自动关闭
```

## 关键实现细节

### 1. inspect 描述动态生成

FastMCP 工具描述必须在装饰器中指定，不能用 f-string docstring：

```python
@mcp.tool(description=full_desc)  # ✅ 正确
async def inspect(...):
    """..."""  # ❌ f-string 在这里无效
```

### 2. 双返回格式

`inspect` 和 `exec` 都返回 `ToolResult`，包含：
- `content`: TOON 压缩后的字符串（供 AI 阅读）
- `structured_content`: 原始 JSON（供程序解析）

### 3. 多模态内容透传

`exec` 返回类型支持多种内容：
- `ToolResult`: 普通数据（压缩 + 原始）
- `TextContent | ImageContent | EmbeddedResource`: 单项多模态内容
- `list[TextContent | ImageContent | EmbeddedResource]`: 多项多模态内容

透传逻辑在 `Executor._extract_result_data()`。

### 4. HTTP/SSE 模式的事件循环

`main_http()` 需要特殊处理：
- 在临时 asyncio.run() 中预连接获取工具描述
- 在 uvicorn lifespan 中重新初始化 Registry
- 避免跨事件循环的连接问题

### 5. 参数校验

`exec` 执行前校验：
- 必填字段（`required`）
- 未知参数（不在 `properties` 中）

### 6. 健康检查

`HealthChecker` 在后台定期探测服务器健康状态：
- 使用临时会话（通过 `client_factory()` 创建）
- 使用 `async with client:` 自动管理会话生命周期
- 检查完成后自动关闭临时会话
- 失败阈值达到后标记服务器不健康
- 提供 `get_server_health()` 查询状态

## 配置

```json
{
  "mcp_servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "type": "stdio"
    },
    {
      "name": "http-server",
      "url": "http://localhost:3000/mcp",
      "type": "http",
      "headers": {"Authorization": "Bearer xxx"}
    }
  ],
  "schema_compression_enabled": true,
  "toon_compression_enabled": true,
  "toon_compression_min_size": 3,
  "health_check_enabled": true,
  "health_check_interval": 30
}
```

## 测试要求

- 覆盖率 ≥ 70%
- 使用 pytest-asyncio 运行异步测试
- E2E 测试覆盖核心流程

## 当前分支

分支名与当前任务相关，PR 合并目标为 `main`。
