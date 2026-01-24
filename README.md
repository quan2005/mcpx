# MCPX

> 把 100 个 MCP 工具变成 2 个 —— 让 AI 专注于真正重要的事情

当你的 AI 需要处理数十个 MCP 服务器时，初始上下文可能膨胀到数万 token。MCPX 通过**按需加载**模式，把所有工具收敛为 `inspect` 和 `exec` 两个入口，AI 只在需要时才获取工具详情。

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

MCPX 只暴露两个工具：

| 工具 | 用途 |
|------|------|
| `inspect` | 查询可用工具及其 Schema |
| `exec` | 执行任意 MCP 工具 |

AI 收到的是一份简洁的"工具目录"，按需查询详情。

### 效果

- **初始上下文减少 60-70%**
- **Schema 压缩为 TypeScript 类型**（可选）
- **TOON 压缩响应数据**（节省 token）

---

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/your-org/mcpx.git
cd mcpx

# 安装依赖
uv sync
```

### 配置

创建 `config.json`：

```json
{
  "mcp_servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    },
    {
      "name": "brave-search",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"]
    }
  ]
}
```

### 运行

```bash
# stdio 模式（Claude Desktop 默认）
uv run mcpx config.json

# HTTP/SSE 模式
uv run mcpx-sse config.json
```

---

## 使用方式

### inspect —— 查询工具

```python
# 列出某个服务器的所有工具
inspect(server_name="filesystem")

# 获取特定工具的完整 Schema
inspect(server_name="filesystem", tool_name="read_file")
```

### exec —— 执行工具

```python
exec(
    server_name="filesystem",
    tool_name="read_file",
    arguments={"path": "/tmp/file.txt"}
)
```

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

## 高级特性

### Schema 压缩

默认启用，将 JSON Schema 转换为 TypeScript 类型：

```json
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

### TOON 压缩

响应数据自动应用 TOON 压缩，返回两种格式：

- `content`：压缩后，供 AI 阅读节省 token
- `structuredContent`：原始 JSON，供程序解析

---

## Docker 部署

### 构建

```bash
docker build -t mcpx:latest .
```

### 运行

```bash
# 准备配置文件
cp config.example.json config.json

# 运行容器
docker run -p 8000:8000 -v $(pwd)/config.json:/app/config.json mcpx:latest
```

### Docker Compose（推荐）

```yaml
services:
  mcpx:
    image: mcpx:latest
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./config.json:/app/config.json
    restart: unless-stopped
```

```bash
docker compose up -d
```

---

## 开发

```bash
# 运行测试
uv run pytest tests/ -v --cov=src/mcpx

# 代码检查
uv run ruff check src/mcpx tests/

# 类型检查
uv run mypy src/mcpx
```

---

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                         AI                              │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    MCPX Proxy                           │
│  ┌─────────────────┐      ┌─────────────────────────┐  │
│  │   inspect       │      │          exec            │  │
│  │  (工具目录)      │      │      (工具执行)           │  │
│  └─────────────────┘      └─────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
          │                            │
          ▼                            ▼
┌──────────────────┐        ┌──────────────────┐
│   Schema 缓存     │        │   连接池管理       │
└──────────────────┘        └──────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
   ┌──────────┐      ┌──────────┐      ┌──────────┐
   │ Server 1 │      │ Server 2 │      │ Server N │
   └──────────┘      └──────────┘      └──────────┘
```

---

## 许可证

MIT
