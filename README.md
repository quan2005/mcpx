# MCPX

MCP 代理服务器，通过 `inspect` 和 `exec` 两个工具实现按需加载 MCP 工具。

## 快速开始

```bash
# 安装依赖
uv sync

# 创建配置文件
cp config.example.json config.json

# 运行服务器
uv run mcpx config.json
```

## 配置

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

## 可用工具

### inspect
查询可用工具及其 Schema。

```python
# 列出服务器的所有工具
inspect(server_name="filesystem")

# 获取特定工具的完整 Schema
inspect(server_name="filesystem", tool_name="read_file")
```

### exec
执行 MCP 工具。

```python
exec(
    server_name="filesystem",
    tool_name="read_file",
    arguments={"path": "/tmp/file.txt"}
)
```

## Docker 使用

### 构建镜像

```bash
docker build -t mcpx:latest .
```

### 运行容器

```bash
# 准备配置文件
cp config.example.json config.json
# 编辑 config.json 添加你的 MCP 服务器

# 运行（HTTP/SSE 模式，默认端口 8000）
docker run -p 8000:8000 -v $(pwd)/config.json:/app/config.json mcpx:latest
```

### Claude Desktop 集成（Docker）

```json
{
  "mcpServers": {
    "mcpx": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-p", "8000:8000",
        "-v", "/path/to/config.json:/app/config.json",
        "mcpx:latest"
      ],
      "env": {
        "MCP_SSE_URL": "http://localhost:8000/mcp/"
      }
    }
  }
}
```

### 使用 Docker Compose（推荐）

创建 `docker-compose.yml`：

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

运行：

```bash
docker compose up -d
```

## 传输方式

### stdio（默认）
```bash
uv run mcpx config.json
```

### HTTP/SSE
```bash
uv run mcpx-sse config.json
```

## Claude Desktop 集成

```json
{
  "mcpServers": {
    "mcpx": {
      "command": "uv",
      "args": ["run", "mcpx", "/path/to/config.json"],
      "cwd": "/path/to/mumbai"
    }
  }
}
```

## 开发

```bash
# 运行测试
uv run pytest tests/ -v

# 代码检查
uv run ruff check src/mcpx tests/

# 类型检查
uv run mypy src/mcpx
```

## 许可证

MIT
