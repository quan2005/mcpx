# MCPX 核心功能需求文档

**版本**: v0.1.0
**日期**: 2026-01-24
**状态**: ✅ 已完成

## 1. 概述

MCPX 是一个 MCP（Model Context Protocol）代理服务器，将多个 MCP 服务器的工具收敛为 `inspect` 和 `exec` 两个入口，AI 按需查询和执行，大幅减少初始上下文 token 消耗。

## 2. 核心需求

### 2.1 工具收敛

**需求描述**: 将多个 MCP 服务器的工具聚合为两个工具暴露给 AI

| 工具 | 用途 |
|------|------|
| `inspect` | 查询可用工具及其 Schema |
| `exec` | 执行任意 MCP 工具 |

### 2.2 连接管理 (Registry)

**需求描述**: 启动时连接所有配置的 MCP 服务器，维护长连接

**功能要求**:
- 支持多服务器并发连接
- 单个服务器连接失败不影响其他服务器
- 连接复用，避免重复建立

### 2.3 工具缓存

**需求描述**: 缓存服务器工具列表和 Schema，避免重复查询

**缓存内容**:
- 工具列表 (`list_tools()`)
- 工具完整 Schema (`input_schema`)
- 服务器信息 (`server_info`)

### 2.4 工具执行 (Executor)

**需求描述**: 通过长连接执行 MCP 工具

**功能要求**:
- 根据 `server_name` 和 `tool_name` 路由到对应服务器
- 参数校验（必填字段、未知参数）
- 执行结果返回

### 2.5 配置驱动

**需求描述**: 通过配置文件管理 MCP 服务器列表

**配置格式** (`config.json`):
```json
{
  "mcp_servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    }
  ]
}
```

### 2.6 传输方式

**需求描述**: 支持多种传输方式

| 传输方式 | 用途 | 状态 |
|---------|------|------|
| stdio | Claude Desktop 默认 | ✅ 必需 |
| HTTP/SSE | 远程调用 | ✅ 必需 |

## 3. 工具接口规范

### 3.1 inspect

**参数**:
- `server_name` (必填): 服务器名称
- `tool_name` (可选): 工具名称

**返回**:
- 仅 `server_name`: 返回该服务器所有工具的 Schema
- `server_name` + `tool_name`: 返回单个工具的完整 Schema

### 3.2 exec

**参数**:
- `server_name` (必填): 服务器名称
- `tool_name` (必填): 工具名称
- `arguments` (可选): 工具参数

**返回**:
- 成功: 工具执行结果
- 失败: 错误信息

## 4. 模块结构

```
src/mcpx/
├── __main__.py   # 入口、inspect/exec 工具定义
├── registry.py   # Registry 类：连接管理、工具缓存
└── executor.py   # Executor 类：工具执行
```

## 5. 验收标准

- [ ] 连接至少 2 个 MCP 服务器
- [ ] `inspect` 能正确列出所有工具
- [ ] `exec` 能正确执行工具
- [ ] 单个服务器连接失败不影响其他服务器
- [ ] 支持 stdio 和 HTTP/SSE 两种传输方式
- [ ] 测试覆盖率 ≥ 70%

## 6. 不包含功能

- TOON 压缩（后续版本）
- Schema 压缩（后续版本）
- 健康检查（后续版本）
- 多模态内容透传（后续版本）
- Docker 支持（后续版本）
