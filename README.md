# MCPX

> 把 100 个 MCP 工具变成 2 个 —— 让 AI 专注于真正重要的事情

---

## 为什么需要 MCPX？

### 问题

直接连接多个 MCP 服务器时，所有工具的完整 Schema 会一次性发送给 AI：

```
连接 10 个服务器 × 每个服务器 5 个工具 × 每个 Schema 200 tokens
= 约 10,000 tokens 的"工具介绍"
```

这些冗余信息挤占了真正有价值的上下文空间。

### 解决方案

MCPX 只暴露三个工具：

| 工具 | 用途 |
|------|------|
| `inspect` | 查询可用工具及其 Schema |
| `exec` | 执行任意 MCP 工具 |
| `resources` | 列出或读取 MCP 服务器资源 |

AI 收到的是一份简洁的"工具目录"，按需查询详情。

### 效果

- **初始上下文减少 60-70%**
- **Schema 压缩为 TypeScript 类型**
- **TOON 压缩响应数据**

---

## 快速开始

```bash
# 安装
uv sync

# 配置 config.json
# 运行
uv run mcpx config.json
```

**config.json**
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

---

## 使用方式

```python
# 查询工具
inspect(server_name="filesystem")
inspect(server_name="filesystem", tool_name="read_file")

# 执行工具
exec(server_name="filesystem", tool_name="read_file", arguments={"path": "/tmp/file.txt"})

# 列出/读取资源
resources(server_name="filesystem")
resources(server_name="filesystem", uri="file:///tmp/file.txt")
```

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **按需加载** | 仅暴露 `inspect`、`exec`、`resources` 三个工具，AI 按需查询详情 |
| **双传输** | stdio（Claude Desktop）+ HTTP/SSE |
| **Schema 压缩** | JSON Schema → TypeScript 类型，节省 token |
| **TOON 压缩** | 响应数据双格式：`content`（压缩）/ `structured_content`（原始） |
| **长连接** | 启动时连接所有服务器，复用连接池 |
| **多模态** | 透传图片、资源等非文本内容 |

### Schema 压缩示例

```typescript
// 原始 JSON Schema (~200 tokens)
{"type":"object","properties":{"path":{"type":"string","description":"文件路径"}},"required":["path"]}

// 压缩后 (~50 tokens)
{path: string}  // 文件路径
```

配置项：

```json
{
  "schema_compression_enabled": true,
  "max_description_len": 50
}
```

---

## 路线图

### ✅ 已完成
- FastMCP 框架、工具缓存、长连接执行器
- stdio + HTTP/SSE 双传输
- Schema/TOON 压缩、健康检查
- 多模态内容透传、Docker 支持
- MCP Resource 动态加载
- client_factory 模式重构（会话隔离）
- E2E 测试 74% 覆盖率

### 📋 待办（P1 高优先级）
- （暂无高优先级待办）

---

## Claude Desktop 集成

```json
{
  "mcpServers": {
    "mcpx": {
      "command": "uv",
      "args": ["run", "mcpx", "/absolute/path/to/config.json"],
      "cwd": "/absolute/path/to/mcpx"
    }
  }
}
```

---

## 开发

```bash
# 测试
uv run pytest tests/ -v --cov=src/mcpx

# Lint
uv run ruff check src/mcpx tests/

# 类型检查
uv run mypy src/mcpx
```

---

## 架构

```
AI → inspect (查询) / exec (执行)
          ↓
    MCPX Proxy
          ↓
    Schema 缓存 + 连接池
          ↓
   Server 1 · Server 2 · Server N
```

---

MIT License
