# MCPX 开发指南

## 核心目标

MCP 代理服务器，将多个 MCP 服务器聚合为 `inspect` 和 `exec` 两个工具，AI 按需查询和执行，减少初始上下文。

## 技术栈

- **FastMCP 3.0** - MCP 服务器框架（`@mcp.tool` 装饰器注册工具）
- **Pydantic** - 数据模型和校验
- **uv** - 依赖管理和运行

## 项目结构

```
src/mcpx/
├── __main__.py   # 入口、inspect/exec 工具定义
├── registry.py   # Registry 类：连接管理、工具缓存
└── executor.py   # Executor 类：工具执行
```

## 核心类

### Registry
- `_sessions`: 服务器长连接
- `_tools`: 工具 Schema 缓存
- `_server_infos`: 服务器信息缓存
- `get_tool(server_name, tool_name)`: 获取工具
- `list_tools(server_name)`: 列出服务器工具

### Executor
- 复用 Registry 的连接
- `execute(server_name, tool_name, arguments)`: 执行工具

## 关键实现

### inspect 描述动态生成
`@mcp.tool(description=full_desc)` - 必须用 description 参数，f-string docstring 无效。

### 参数校验
`exec` 执行前校验 required 字段和 unknown 参数。

## 测试

```bash
uv run pytest tests/ -v --cov=src/mcpx
```

覆盖率要求 ≥ 70%。
