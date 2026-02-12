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

MCPX 只暴露两个工具：

| 工具 | 用途 |
|------|------|
| `invoke` | 执行任意 MCP 工具（出错时返回可用服务器/工具/schema） |
| `read` | 读取 MCP 服务器资源 |

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

> ⚠️ **重要提示**：
> 1. `~/.claude.json` 文件可能非常大（数千行），**务必使用 `jq` 命令精准提取 `mcpServers` 配置**
> 2. `mcpx-toolkit` 应配置为**后台服务并开机自启**，不要直接运行

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

### 第二步：配置后台服务（推荐）

> ⚠️ **重要**：不要直接运行 `mcpx-toolkit`，应该配置为后台服务并开机自启。

#### macOS（使用 launchd）

创建服务配置文件：

```bash
# 创建 launchd 配置
cat > ~/Library/LaunchAgents/com.mcpx-toolkit.service.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mcpx-toolkit.service</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/mcpx-toolkit</string>
        <string>/Users/YOUR_USERNAME/.config/mcpx-toolkit/mcpx.json</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/mcpx-toolkit.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/mcpx-toolkit.stderr.log</string>
</dict>
</plist>
EOF

# 替换 YOUR_USERNAME 为你的用户名
sed -i '' "s|YOUR_USERNAME|$USER|" ~/Library/LaunchAgents/com.mcpx-toolkit.service.plist

# 加载并启动服务
launchctl load ~/Library/LaunchAgents/com.mcpx-toolkit.service.plist

# 检查服务状态
launchctl list | grep mcpx
```

#### Linux（使用 systemd）

创建服务配置文件：

```bash
# 创建 systemd 服务文件
cat > ~/.config/systemd/user/mcpx-toolkit.service << 'EOF'
[Unit]
Description=MCPX Toolkit - MCP Proxy Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/mcpx-toolkit /home/YOUR_USERNAME/.config/mcpx-toolkit/mcpx.json
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

# 替换 YOUR_USERNAME 为你的用户名
sed -i "s|YOUR_USERNAME|$USER|" ~/.config/systemd/user/mcpx-toolkit.service

# 重载并启用服务
systemctl --user daemon-reload
systemctl --user enable mcpx-toolkit.service
systemctl --user start mcpx-toolkit.service

# 检查服务状态
systemctl --user status mcpx-toolkit.service
```

#### 临时测试（仅用于调试）

如果需要临时测试服务（不推荐用于生产环境）：

```bash
# 后台运行
nohup mcpx-toolkit ~/.config/mcpx-toolkit/mcpx.json > /tmp/mcpx-toolkit.log 2>&1 &

# 查看日志
tail -f /tmp/mcpx-toolkit.log

# 停止服务
pkill -f mcpx-toolkit
```

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
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

> **注意**：`mcpx-toolkit` 服务已经在后台运行。如果 8000 端口被占用，服务会自动切换到可用端口（如 8001、8002...），可通过日志查看实际端口。

### 第四步：重启 Claude Code

重启后，所有 MCP 工具将通过 MCPX 统一管理。

### 服务管理命令

**macOS（launchd）**：
```bash
# 停止服务
launchctl unload ~/Library/LaunchAgents/com.mcpx-toolkit.service.plist

# 启动服务
launchctl load ~/Library/LaunchAgents/com.mcpx-toolkit.service.plist

# 重启服务
launchctl unload ~/Library/LaunchAgents/com.mcpx-toolkit.service.plist
launchctl load ~/Library/LaunchAgents/com.mcpx-toolkit.service.plist

# 查看日志
tail -f /tmp/mcpx-toolkit.stdout.log
```

**Linux（systemd）**：
```bash
# 停止服务
systemctl --user stop mcpx-toolkit.service

# 启动服务
systemctl --user start mcpx-toolkit.service

# 重启服务
systemctl --user restart mcpx-toolkit.service

# 查看日志
journalctl --user -u mcpx-toolkit.service -f
```

---

## 使用方式

### 执行工具

```python
invoke(
    method="filesystem.read_file",
    arguments={"path": "/tmp/file.txt"}
)
```

**错误处理**：当调用失败时，`invoke` 会返回有用的信息：
- 服务器不存在：返回 `error` + `available_servers` 列表
- 工具不存在：返回 `error` + `available_tools` 列表
- 参数无效：返回 `error` + `tool_schema`

### 读取资源

```python
read(server_name="filesystem", uri="file:///tmp/file.txt")
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

## Web Dashboard

MCPX 提供 Web Dashboard 用于直观管理 MCP 服务器、工具和资源。

### 启动 Dashboard

```bash
# Dashboard 模式（启用 Web 界面）
mcpx-toolkit --gui --open config.json

# Desktop 模式（原生窗口，需要 pywebview）
mcpx-toolkit --gui --desktop config.json
```

### Dashboard 功能

| 页面 | 功能 |
|------|------|
| **Dashboard** | 总览所有服务器状态、工具和资源数量 |
| **Servers** | 查看服务器详情，添加/编辑/删除服务器，启用/禁用服务器 |
| **Tools** | 浏览和搜索工具，查看工具 Schema，测试工具执行，启用/禁用单个工具 |
| **Resources** | 浏览资源，点击预览内容 |
| **Health** | 查看健康状态，手动触发健康检查 |
| **Settings** | 修改配置并热重载 |

**新增功能（v0.6.0）**：
- 工具详情模态框：查看工具 Schema、测试工具执行
- 服务器配置编辑器：添加/编辑/删除服务器
- Toast 通知：操作反馈
- 确认对话框：删除操作确认

### CLI 参数

| 参数 | 说明 |
|------|------|
| `--gui` | 启用 Web Dashboard |
| `--open` | 启动后自动打开浏览器 |
| `--desktop` | 使用 pywebview 创建原生窗口（需要安装 `pywebview`） |

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **极简 API** | 仅暴露 `invoke`、`read` 两个工具 |
| **多传输** | stdio / Streamable HTTP / SSE（自动检测） |
| **Schema 压缩** | JSON Schema → TypeScript 类型，节省 token |
| **TOON 压缩** | 响应数据双格式：`content`（压缩）/ `structured_content`（原始） |
| **连接池** | 连接复用提升性能，自动管理连接生命周期 |
| **健康检查** | 后台定期探测服务器状态 |
| **多模态** | 透传图片、资源等非文本内容 |
| **Web Dashboard** | 浏览器管理服务器、工具和资源（增量启停） |

### Schema 压缩示例

```typescript
// 原始 JSON Schema (~200 tokens)
{"type":"object","properties":{"path":{"type":"string","description":"文件路径"}},"required":["path"]}

// 压缩后 (~50 tokens)
{path: string}  // 文件路径
```

---

## HTTP/SSE 模式

`mcpx-toolkit` 默认以 HTTP/SSE 模式运行，服务启动在 `http://localhost:8000/mcp`，兼容 MCP HTTP/SSE 协议。

**端口自动切换**：如果指定端口被占用，服务会自动尝试后续端口（8001、8002...），并在日志中显示实际监听的端口。

### 修改端口

编辑服务配置文件，在启动命令中添加 `--port` 参数：

**macOS（launchd）**：
```xml
<key>ProgramArguments</key>
<array>
    <string>/usr/local/bin/mcpx-toolkit</string>
    <string>--port</string>
    <string>3000</string>
    <string>/Users/YOUR_USERNAME/.config/mcpx-toolkit/mcpx.json</string>
</array>
```

**Linux（systemd）**：
```ini
ExecStart=/usr/local/bin/mcpx-toolkit --port 3000 /home/YOUR_USERNAME/.config/mcpx-toolkit/mcpx.json
```

修改后重新加载服务即可。

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
   ├── invoke (执行工具，出错时返回 schema)
   └── read (读取资源)
       ↓
   连接池 + Schema 缓存 + 健康检查
       ↓
   Server 1 · Server 2 · Server N
```

### 核心组件

| 组件 | 职责 |
|------|------|
| **ServerManager** | 连接池管理、工具/资源缓存、健康检查、工具执行 |
| **ConnectionPool** | MCP 连接池，连接复用提升性能 |
| **ToonCompressor** | TOON 压缩实现 |
| **HealthChecker** | 后台健康检查和重连 |

---

## 路线图

### ✅ 已完成
- FastMCP 框架、工具缓存、连接池执行器
- HTTP/SSE 传输支持
- Schema/TOON 压缩、健康检查
- 多模态内容透传、Docker 支持
- MCP Resource 动态加载
- 连接池模式重构（替代 Session Isolation）
- E2E 测试 70%+ 覆盖率
- GitHub Actions 自动发布到 PyPI
- **v0.4.0**: ServerManager 合并 Registry + Executor，连接池提升性能
- **v0.5.0**: Web Dashboard 基础版本 - 浏览器管理服务器、工具和资源
- **v0.6.0**: Dashboard 增强版本 - 工具详情+测试、服务器配置编辑器、Toast通知

### 📋 待办（P1 高优先级）
- （暂无高优先级待办）

---

## 许可证

MIT License
