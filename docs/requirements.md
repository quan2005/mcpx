# MCPX 需求文档

## 1. 项目概述

MCPX 是一个 MCP（Model Context Protocol）代理服务器，通过 `inspect` 和 `exec` 两个工具实现按需加载 MCP 工具，大幅减少初始上下文。

## 2. 核心需求

### 2.1 上下文优化
- **问题**：直接连接多个 MCP 服务器会暴露所有工具，导致初始上下文过大
- **解决方案**：代理仅暴露两个工具（`inspect` 和 `exec`），AI 按需查询工具详情和执行

### 2.2 架构设计
- **启动时**：连接所有 MCP 服务器并保持长连接，获取工具列表和完整 Schema 后缓存
- **AI 收到**：仅两个工具的描述，`inspect` 的工具描述中包含所有可用工具的列表及简介
- **`inspect`**：从缓存返回工具的完整 Schema
- **`exec`**：通过长连接池执行工具

## 3. 功能需求

### 3.1 工具注册表 (Registry)
- 启动时连接所有配置的 MCP 服务器
- 保持长连接，不主动断开
- 获取并缓存工具列表、完整 Schema 和服务器信息
- 单个服务器连接失败不影响其他服务器
- 提供工具查询接口

### 3.2 长连接执行器 (Executor)
- 维护与所有 MCP 服务器的长连接池
- 根据 server_name 和 tool_name 路由到对应服务器
- 执行前进行参数校验
- 执行后连接保持活跃，可复用
- 返回清晰的执行结果或错误信息

### 3.3 MCP 代理服务器
- 实现 MCP 协议
- 仅暴露两个工具：`inspect` 和 `exec`
- `inspect` 描述在初始化时动态生成，包含所有可用工具列表及简介
- 支持按服务器名称、工具名称查询工具

### 3.4 传输方式
- **stdio**：默认传输方式，兼容 Claude Desktop
- **HTTP**：基于 FastMCP 内置的 HTTP 传输方式
- 两种方式功能完全一致

### 3.5 配置管理
- 通过 `config.json` 配置 MCP 服务器列表
- 配置更改需重启生效（不支持热加载）
- 配置加载失败有清晰错误提示
- 支持环境变量配置

## 4. 工具接口规范

### 4.1 inspect
查询可用工具及其 Schema。

**参数**：
- `server_name`（必填）：服务器名称
- `tool_name`（可选）：工具名称，返回该工具的完整 Schema

**返回**：`ToolResult` 对象
- `content`：TOON 压缩后的数据（用于 AI 阅读，节省 token）
- `structuredContent`：原始未压缩的 JSON 数据（用于程序解析）

**数据内容**：
- 仅指定 `server_name`：返回该服务器的所有工具 Schema
- 指定 `server_name` + `tool_name`：返回单个工具的完整 Schema

**工具描述**：
`inspect` 工具的描述在初始化时动态生成，包含所有可用工具列表：
```
Inspect available MCP tools and their schemas.

Available tools:
  Server: filesystem - File operations for reading and writing files
    - read_file: Read the complete contents of a file...
    - write_file: Create a new file or overwrite...
  Server: brave-search - Web search powered by Brave Search API
    - search: Search the web using Brave Search API...
```

**说明**：
- 每个 Server 行可包含该 MCP 服务器的 instructions（引导说明），帮助 AI 理解服务器的用途
- 引导说明来自 MCP 服务器的 `server_info.instructions` 字段
- 若引导说明超过 300 字符，截断并添加 `...`

### 4.3 Schema 压缩
为减少 token 消耗，`input_schema` 字段默认转换为 TypeScript 类型格式。

**压缩规则**：
- 启用配置：`schema_compression_enabled: true`（默认）
- 压缩效果：约减少 60-70% token
- 格式示例：
  - JSON Schema: `{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}`
  - TypeScript: `{path: string}`

**实现**：
- `src/mcpx/schema_ts.py`：JSON Schema 到 TypeScript 转换器
- 支持基本类型、数组、对象、联合类型、枚举、$ref 解析
- 可配置保留描述（`max_description_len`）

### 4.2 exec
执行 MCP 工具。

**参数**：
- `server_name`（必填）：服务器名称
- `tool_name`（必填）：工具名称
- `arguments`（可选）：工具参数，执行前进行 Schema 校验

**返回**：`ToolResult` 对象
- `content`：TOON 压缩后的数据（用于 AI 阅读，节省 token）
- `structuredContent`：原始未压缩的 JSON 数据（用于程序解析）

**特殊情况**（多模态内容直接透传）：
- `TextContent`：文本内容
- `ImageContent`：图片内容（base64 编码）
- `EmbeddedResource`：资源引用

**错误响应**：
- `error`：错误信息

## 5. 错误处理

### 5.1 连接错误
- 单个服务器连接失败不影响其他服务器
- 记录清晰的错误日志
- 可用的工具正常工作

### 5.2 执行错误
- 服务器不存在时返回清晰的错误信息
- 工具不存在时返回清晰的错误信息
- 参数校验失败返回准确的错误提示
- 执行异常返回原始错误信息

### 5.3 配置错误
- 配置文件不存在时退出并提示
- JSON 格式错误时退出并提示
- 配置结构错误时退出并提示

## 8. 项目结构

```
src/mcpx/
├── __init__.py       # 模块导出
├── __main__.py       # 入口、inspect/exec 工具定义
├── config.py         # 配置模型（McpServerConfig、ProxyConfig）
├── registry.py       # Registry 类：连接管理、工具缓存
├── executor.py       # Executor 类：工具执行
├── compression.py    # TOON 压缩实现
├── content.py        # 多模态内容检测
├── health.py         # 连接健康检查
└── schema_ts.py      # JSON Schema → TypeScript 转换器
```

### 核心类说明

#### Registry (`registry.py`)
- `_sessions`: 服务器长连接
- `_tools`: 工具 Schema 缓存
- `_server_infos`: 服务器信息缓存
- `get_tool(server_name, tool_name)`: 获取工具
- `list_tools(server_name)`: 列出服务器工具
- `get_server_info(server_name)`: 获取服务器信息

#### Executor (`executor.py`)
- 复用 Registry 的连接
- `execute(server_name, tool_name, arguments)`: 执行工具
- 返回 `ExecutionResult`（包含压缩数据和原始数据）

#### SchemaConverter (`schema_ts.py`)
- `convert(schema)`: 将 JSON Schema 转换为 TypeScript 类型
- 支持基本类型、数组、对象、联合类型、枚举、$ref 解析

## 6. 非功能需求

### 6.1 可靠性
- 长连接断线后能检测并报告错误
- 支持并发工具执行

### 6.2 可维护性
- 代码结构清晰，模块化设计
- 遵循 Python 最佳实践
- 类型注解完整

## 7. 不做的事项

- 不包含连接健康检查和心跳机制
- 不包含连接池的动态扩缩容
- 不包含工具执行的结果缓存
- 不包含生产环境部署相关（Docker、监控、日志聚合等）
- 不包含性能优化（连接复用策略、并发限制等）
- 不包含 Web UI 或管理界面
- 不包含配置热加载
