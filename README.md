# MCPX

> 把 100 个 MCP 工具变成 3 个 —— 让 AI 专注于真正重要的事情

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
| `describe` | 查询可用工具及其 Schema |
| `call` | 执行任意 MCP 工具 |
| `resources` | 列出或读取 MCP 服务器资源 |

AI 收到的是一份简洁的"工具目录"，按需查询详情。

### 效果

- **初始上下文减少 60-70%**
- **Schema 压缩为 TypeScript 类型**
- **TOON 压缩响应数据**

---

## 安装

### 给人类用户

将以下提示复制给你的 LLM Agent（Claude Code、Cursor、Windsurf 等）：

```
帮我安装和配置 mcpx-toolkit，让所有 MCP 工具通过 mcpx-toolkit 统一管理。

注意：我的 ~/.claude.json 文件很大，请用 jq 命令精准提取 mcpServers 配置，
不要读取整个文件。具体步骤请参考：
https://raw.githubusercontent.com/quan2005/mcpx/main/README.md
```

### 给 LLM Agent

> ⚠️ **重要提示**：`~/.claude.json` 文件可能非常大（数千行）。
> **务必使用 `jq` 命令精准提取 `mcpServers` 配置**，不要直接读取整个文件。

安装 `mcpx-toolkit`：

```bash
# 使用 uv 安装（推荐）
uv tool install mcpx-toolkit

# 或使用 pip
pip install mcpx-toolkit
```

---

## LLM 配置指南

> 将此指南发给 LLM Agent，让它帮你完成配置

### 第一步：提取现有 MCP 配置

> ⚠️ **Claude Code 配置文件可能非常大**，包含大量历史对话和其他设置。
> **请务必使用 `jq` 精准提取 `mcpServers` 字段**，避免读取整个文件导致上下文溢出。

查找 Claude Code 配置文件：

| 系统 | 路径 |
|------|------|
| macOS | `~/.claude.json` |
| Windows | `~/.claude.json` |
| Linux | `~/.claude.json` |

使用 `jq` 精准提取 `mcpServers` 到推荐目录：

```bash
# 创建 mcpx-toolkit 配置目录
mkdir -p ~/.config/mcpx-toolkit

# 提取 mcpServers 配置
jq '.mcpServers' ~/.claude.json > ~/.config/mcpx-toolkit/mcpx.json

# Windows (PowerShell)
New-Item -ItemType Directory -Force -Path ~/.config/mcpx-toolkit
Get-Content ~/.claude.json | \
  ConvertFrom-Json | Select-Object -ExpandProperty mcpServers | \
  ConvertTo-Json -Depth 10 | Out-File ~/.config/mcpx-toolkit/mcpx.json
```

验证提取结果（应该只包含 MCP 服务器配置）：

```bash
cat ~/.config/mcpx-toolkit/mcpx.json | jq 'keys'
```

### 第二步：启动 mcpx-toolkit

```bash
# 使用提取的配置启动
mcpx-toolkit ~/.config/mcpx-toolkit/mcpx.json
```

MCPX 会：
1. 连接所有配置的 MCP 服务器
2. 启动 HTTP/SSE 模式，等待连接（默认 `http://localhost:8000`）

### 第三步：修改 Claude Code 配置

备份原配置：

```bash
cp ~/.claude.json ~/.claude.json.backup
```

将 `~/.claude.json` 的 `mcpServers` 修改为只保留 `mcpx`：

```json
{
  "mcpServers": {
    "mcpx": {
      "command": "mcpx-toolkit",
      "args": ["~/.config/mcpx-toolkit/mcpx.json"]
    }
  }
}
```

### 第四步：重启 Claude Code

重启后，所有 MCP 工具将通过 MCPX 统一管理。

---

## 使用方式

### 查询工具

```python
# 列出指定服务器的所有工具
describe(method="filesystem")

# 查看工具的详细 Schema
describe(method="filesystem.read_file")
```

### 执行工具

```python
call(
    method="filesystem.read_file",
    arguments={"path": "/tmp/file.txt"}
)
```

### 列出/读取资源

```python
# 列出服务器的所有资源
resources(server_name="filesystem")

# 读取指定资源
resources(server_name="filesystem", uri="file:///tmp/file.txt")
```

---

## 配置文件说明

推荐配置文件路径：`~/.config/mcpx-toolkit/mcpx.json`

格式说明：

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
      "headers": {
        "Authorization": "Bearer xxx"
      }
    },
    "sse-server": {
      "type": "http",
      "url": "https://example.com/sse"
    }
  },
  "schema_compression_enabled": true,
  "toon_compression_enabled": true,
  "toon_compression_min_size": 1,
  "health_check_enabled": true,
  "health_check_interval": 30
}
```

**注意**：HTTP 类型会自动检测传输方式——URL 包含 `/sse` 使用 SSE 传输，否则使用 Streamable HTTP。

| 配置项 | 说明 | 默认值 |
|-------|------|--------|
| `schema_compression_enabled` | Schema 压缩为 TypeScript 类型 | `true` |
| `toon_compression_enabled` | TOON 压缩响应数据 | `true` |
| `toon_compression_min_size` | TOON 压缩最小阈值（数组长度/对象键数） | `1` |
| `health_check_enabled` | 启用健康检查 | `true` |
| `health_check_interval` | 健康检查间隔（秒） | `30` |

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **按需加载** | 仅暴露 `describe`、`call`、`resources` 三个工具 |
| **多传输** | stdio / Streamable HTTP / SSE（自动检测） |
| **Schema 压缩** | JSON Schema → TypeScript 类型，节省 token |
| **TOON 压缩** | 响应数据双格式：`content`（压缩）/ `structured_content`（原始） |
| **会话隔离** | 每次请求创建新会话，避免状态污染 |
| **健康检查** | 后台定期探测服务器状态 |
| **多模态** | 透传图片、资源等非文本内容 |

### Schema 压缩示例

```typescript
// 原始 JSON Schema (~200 tokens)
{"type":"object","properties":{"path":{"type":"string","description":"文件路径"}},"required":["path"]}

// 压缩后 (~50 tokens)
{path: string}  // 文件路径
```

---

## HTTP/SSE 模式

适用于需要通过 HTTP 访问的场景（如 Web 应用）：

```bash
mcpx-toolkit-sse ~/.config/mcpx-toolkit/mcpx.json
```

服务启动在 `http://localhost:8000`，兼容 MCP HTTP/SSE 协议。

---

## 开发

```bash
# 克隆仓库
git clone https://github.com/quan2005/mcpx.git
cd mcpx

# 安装依赖
uv sync

# 运行测试
uv run pytest tests/ -v --cov=src/mcpx

# 代码检查
uv run ruff check src/mcpx tests/

# 类型检查
uv run mypy src/mcpx
```

## AI 开发流程

本项目使用 **skills** 规范 AI Agent 的开发流程。这些 skills 是项目的一部分，位于 `.claude/skills/` 目录：

```bash
.claude/skills/
├── mcpx-getting-started/    # 入口，加载其他 skills
├── mcpx-tdd-workflow/       # TDD 开发（RED-GREEN-REFACTOR）
├── mcpx-code-quality/       # 代码质量检查（lint/types/test）
├── mcpx-documentation/      # 文档更新规范
└── mcpx-release/            # 版本发布流程
```

### 使用方式

这些是**项目专属 skills**，克隆项目后即可使用。开始开发前，告诉 AI：

> 加载 mcpx-getting-started skill

AI 会自动加载并遵循项目的开发流程规范。

---

## 架构

```
Claude Desktop
       ↓
   MCPX (mcpx-toolkit)
   ├── describe (查询工具)
   ├── call (执行工具)
   └── resources (读取资源)
       ↓
   Schema 缓存 + 连接池 + 健康检查
       ↓
   Server 1 · Server 2 · Server N
```

### 核心组件

| 组件 | 职责 |
|------|------|
| **Registry** | 连接管理、工具/资源缓存、健康检查 |
| **Executor** | 工具执行、TOON 压缩、会话隔离 |
| **ToonCompressor** | TOON 压缩实现 |
| **HealthChecker** | 后台健康检查和重连 |

---

## 路线图

### ✅ 已完成
- FastMCP 框架、工具缓存、长连接执行器
- HTTP/SSE 传输支持
- Schema/TOON 压缩、健康检查
- 多模态内容透传、Docker 支持
- MCP Resource 动态加载
- client_factory 模式重构（会话隔离）
- E2E 测试 74% 覆盖率
- GitHub Actions 自动发布到 PyPI

### 📋 待办（P1 高优先级）
- （暂无高优先级待办）

---

## 许可证

MIT License
