# MCPX 验证标准文档

## 1. 条款验证概览

| 条款 | 状态 | 验证方式 |
|------|------|----------|
| 条款 1：FastMCP 框架架构 | ✅ | 检查依赖、代码结构 |
| 条款 2：工具注册表与缓存 | ✅ | 检查 Registry 实现 |
| 条款 3：长连接执行器 | ✅ | 检查 Executor 实现 |
| 条款 4：MCP 代理服务器 | ✅ | 检查工具数量、接口实现 |
| 条款 5：双传输方式支持 | ✅ | 检查命令入口、功能测试 |
| 条款 6：配置驱动 | ✅ | 检查配置文件、错误处理 |
| 条款 7：错误处理与降级 | ✅ | 检查异常处理逻辑 |
| 条款 8：E2E 测试覆盖 | ✅ | 运行测试套件 |

## 2. 详细验证标准

### 条款 1：FastMCP 框架架构

**目标**：项目使用 FastMCP 框架构建，遵循最佳实践。

**验证方式**：
```bash
# 检查依赖
grep "fastmcp" pyproject.toml

# 检查代码使用 FastMCP 装饰器模式
grep -r "@mcp.tool" src/

# 检查项目结构
ls -la src/mcpx/
```

**通过标准**：
- `pyproject.toml` 包含 `fastmcp>=3.0.0b1` 依赖
- 代码使用 `@mcp.tool()` 装饰器注册工具
- 项目结构符合 FastMCP 推荐模式（`src/` 布局）

### 条款 2：工具注册表与缓存

**目标**：Registry 在启动时连接所有服务器，保持长连接，缓存工具和 Schema。

**验证方式**：
```python
# 检查 Registry 实现
# src/mcpx/registry.py

# 验证属性
- Registry._sessions: dict[str, Client]  # 维护活跃连接
- Registry._tools: dict[str, ToolInfo]   # 缓存工具和 Schema
- Registry.get_tool(server_name, tool_name): ToolInfo  # 从缓存获取工具
- Registry.list_tools(server_name): list[ToolInfo]    # 列出指定服务器的缓存工具
```

**通过标准**：
- `_sessions` 在启动后维护所有服务器的活跃连接
- `_tools` 缓存包含所有服务器的工具和 Schema
- `inspect` 通过 `server_name` 和 `tool_name` 从缓存返回指定工具的完整 Schema
- `server_name` 为必填参数，不支持查询所有服务器的工具

### 条款 3：长连接执行器

**目标**：Executor 维护长连接池，执行后连接保持活跃。

**验证方式**：
```python
# 检查 Executor 实现
# src/mcpx/executor.py

# 验证执行流程
1. 接收 server_name 和 tool_name 参数
2. 从缓存获取工具信息
3. 执行参数校验（在请求前校验 arguments 是否匹配 Schema）
4. 获取对应服务器的 session
5. 执行工具
6. 连接保持活跃（不关闭）
```

**通过标准**：
- `Executor._sessions` 维护所有服务器的活跃连接
- `execute()` 接收 `server_name` 和 `tool_name` 参数，正确路由到对应服务器并执行
- 执行前进行参数校验，校验失败返回准确的错误提示
- 执行后连接保持活跃（不关闭）
- 多个工具执行能复用同一连接

### 条款 4：MCP 代理服务器

**目标**：代理仅暴露 `inspect` 和 `exec` 两个工具。

**验证方式**：
```bash
# 运行测试验证工具数量
uv run pytest tests/test_e2e.py::TestMCPXClientE2E::test_client_list_tools_only_two -v
```

**通过标准**：
- MCP 服务器初始化时仅注册两个工具
- `inspect` 工具：
  - 参数：`server_name`（必填）、`tool_name`（可选）
  - `server_name` 必须提供，不支持两个参数同时为空
  - 能返回指定服务器的工具列表或单个工具的完整 Schema
- `exec` 工具：
  - 参数：`server_name`（必填）、`tool_name`（必填）、`arguments`（可选）
  - 执行前进行参数校验，校验失败返回准确的错误提示
  - 能通过 Executor 执行工具并返回结果
- 初始响应的工具列表仅包含两个工具

### 条款 5：双传输方式支持

**目标**：支持 stdio 和 SSE/HTTP 两种传输方式。

**验证方式**：
```bash
# 检查命令定义
grep "scripts" pyproject.toml

# 验证 stdio 方式
uv run mcpx config.json

# 验证 HTTP/SSE 方式
uv run mcpx-sse config.json
```

**通过标准**：
- `pyproject.toml` 定义 `mcpx`（stdio）和 `mcpx-sse`（HTTP）两个命令
- stdio 方式能正常启动并与 Claude Desktop 通信
- HTTP/SSE 方式能正常启动并接受连接
- 两种方式功能一致（工具注册、执行、错误处理）

### 条款 6：配置驱动

**目标**：通过 `config.json` 配置 MCP 服务器列表，配置更改需重启生效。

**验证方式**：
```json
// config.json 格式
{
  "mcp_servers": [
    {
      "name": "server_name",
      "command": "command",
      "args": ["arg1", "arg2"],
      "env": {"KEY": "value"}
    }
  ]
}
```

**通过标准**：
- `config.json` 包含 `mcp_servers` 数组
- 每个服务器有 `name`、`command`、`args` 字段
- 修改配置后需重启服务才能加载新服务器（不支持热加载）
- 配置格式错误时有清晰的错误提示
- 服务器连接失败不影响其他服务器加载

### 条款 7：错误处理与降级

**目标**：单个服务器失败不影响整体服务。

**验证方式**：
```bash
# 运行错误处理测试
uv run pytest tests/test_e2e.py::TestMCPXErrorHandling -v
```

**通过标准**：
- 启动时某个服务器连接失败，其他服务器仍正常工作
- 执行不存在的工具时返回清晰的错误信息
- 执行失败时返回原始错误而非崩溃
- 连接断开后能报告错误

### 条款 8：E2E 测试覆盖

**目标**：使用 fastmcp client 编写完整的端到端测试。

**验证方式**：
```bash
# 运行所有 E2E 测试
uv run pytest tests/test_e2e.py -v

# 检查覆盖率
uv run pytest tests/ --cov=src/mcpx --cov-report=term
```

**测试覆盖清单**：
- ✅ stdio 连接方式测试
- ✅ HTTP/SSE 连接方式测试
- ✅ `inspect` 调用测试：
  - 指定 `server_name` 返回该服务器所有工具
  - 指定 `server_name` + `tool_name` 返回单个工具的完整 Schema
  - 缺少 `server_name` 时返回错误提示
- ✅ `exec` 调用测试：
  - 指定 `server_name` + `tool_name` + `arguments` 执行工具
  - 执行前参数校验（arguments 不匹配 Schema 时返回准确的错误提示）
  - 缺少必填参数时返回错误提示
- ✅ 错误场景测试（不存在的工具、不存在的服务器、服务器连接失败）
- ✅ 并发客户端测试
- ✅ 配置文件测试

**通过标准**：
- 所有测试运行通过
- 覆盖率 ≥ 70%

## 3. 代码质量验证

### 3.1 代码风格
```bash
# 运行 ruff 检查
uv run ruff check src/mcpx tests/
```

### 3.2 类型检查
```bash
# 运行 mypy 检查
uv run mypy src/mcpx --strict
```

### 3.3 测试通过
```bash
# 运行所有测试
uv run pytest tests/ -v
```

## 4. 验证命令

### 4.1 完整验证
```bash
# 代码质量检查
uv run ruff check src/mcpx tests/
uv run mypy src/mcpx

# 运行测试
uv run pytest tests/ -v --cov=src/mcpx --cov-report=term
```

### 4.2 快速验证
```bash
# 仅运行测试
uv run pytest tests/ -v
```

## 5. 验证输出示例

```
✅ 条款 1：FastMCP 框架架构 - 通过
✅ 条款 2：工具注册表与缓存 - 通过
✅ 条款 3：长连接执行器 - 通过
✅ 条款 4：MCP 代理服务器 - 通过
✅ 条款 5：双传输方式支持 - 通过
✅ 条款 6：配置驱动 - 通过
✅ 条款 7：错误处理与降级 - 通过
✅ 条款 8：E2E 测试覆盖 - 通过

代码质量：✅ ruff 通过，✅ mypy 通过
测试结果：34 passed, coverage 74%

验证通过
```
