# ProxyProvider 连接稳定性重构实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> **执行方式**: 使用 /ralph-wiggum:ralph-loop 循环执行每个任务

**Goal:** 使用 FastMCP ProxyProvider 的 Session Isolation 机制重构 MCPX 连接管理，简化代码并提升连接稳定性

**Architecture:** 将"长连接 + 手动重连"架构改为"client_factory + 会话隔离"架构，每次请求创建新会话，自动管理连接生命周期

**Tech Stack:** FastMCP 3.0, Pydantic v2, uv, pytest

**兼容性保证:**
- ✅ inspect/exec/resources 接口不变
- ✅ config.json 格式不变
- ✅ TOON 压缩功能不受影响
- ✅ Schema 压缩功能不受影响
- ✅ 多模态内容透传不受影响
- ✅ 资源缓存功能不受影响

---

## 前置检查：验证现有功能

### Task 0: 验证现有测试全部通过

**目的:** 在重构前确认所有现有功能正常，建立基线

**Files:**
- Test: `tests/test_mcpx.py`
- Test: `tests/test_e2e.py`

**Step 1: 运行现有测试**

```bash
cd /Users/yanwu/conductor/workspaces/mcpx/milan
uv run pytest tests/ -v --cov=src/mcpx
```

**Step 2: 确认覆盖率基线**

记录当前覆盖率，确保重构后不低于此值。

**Step 3: 创建重构分支（如未创建）**

```bash
git branch --show-current | grep proxyprovider-refactor || git checkout -b proxyprovider-refactor
```

**Step 4: 记录基线结果**

将测试结果保存到 `.context/baseline-test-results.txt`

---

## Phase 1: Registry 重构

### Task 1: 添加 _client_factories 属性

**Files:**
- Modify: `src/mcpx/registry.py:117-128`

**Step 1: 修改 __init__ 方法**

在 `Registry.__init__` 中添加 `_client_factories` 字典，暂时保留 `_sessions` 以确保兼容：

```python
def __init__(self, config: ProxyConfig) -> None:
    """Initialize registry with configuration.

    Args:
        config: Proxy configuration with MCP server list
    """
    self._config = config
    self._sessions: dict[str, McpClient] = {}  # 待移除
    self._client_factories: dict[str, Callable[[], McpClient]] = {}  # 新增
    self._tools: dict[str, ToolInfo] = {}
    self._resources: dict[str, ResourceInfo] = {}
    self._server_infos: dict[str, ServerInfo] = {}
    self._initialized = False
```

**Step 2: 运行测试**

```bash
uv run pytest tests/test_mcpx.py -v -k "test_registry"
```

**Step 3: 提交**

```bash
git add src/mcpx/registry.py
git commit -m "refactor: add _client_factories attribute to Registry"
```

---

### Task 2: 创建 _create_client_factory 方法

**Files:**
- Modify: `src/mcpx/registry.py`
- Add: 新方法在 `Registry` 类中

**Step 1: 添加导入**

在文件顶部添加必要的类型：

```python
from collections.abc import Callable
from typing import Awaitable
```

**Step 2: 实现 _create_client_factory 方法**

在 `Registry` 类中添加此方法，放在 `__init__` 之后：

```python
def _create_client_factory(
    self, server_config: McpServerConfig
) -> Callable[[], McpClient]:
    """Create a client factory for a server.

    The factory returns a new client instance on each call.
    This enables session isolation - each request gets a fresh connection.

    Args:
        server_config: Server configuration

    Returns:
        A callable that returns a new Client instance
    """
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport, StreamableHttpTransport

    # Create transport based on type
    if server_config.type == "http":
        transport: StdioTransport | StreamableHttpTransport = StreamableHttpTransport(
            url=server_config.url,  # type: ignore[arg-type]
            headers=server_config.headers or {},
        )
    else:
        # Default to stdio
        transport = StdioTransport(
            command=server_config.command,  # type: ignore[arg-type]
            args=server_config.args,
            env=server_config.env or {},
        )

    # Create base client (disconnected)
    base_client: McpClient = Client(transport, auto_initialize=True)

    # Factory function: returns new client each time
    def factory() -> McpClient:
        return base_client.new()

    return factory
```

**Step 3: 运行测试**

```bash
uv run pytest tests/test_mcpx.py -v -k "test_registry"
```

**Step 4: 提交**

```bash
git add src/mcpx/registry.py
git commit -m "refactor: implement _create_client_factory method"
```

---

### Task 3: 修改 initialize 使用 client_factory 获取 Schema

**Files:**
- Modify: `src/mcpx/registry.py:144-166`

**Step 1: 重写 initialize 方法**

保持 Schema 获取逻辑，但使用临时会话而非长连接：

```python
async def initialize(self) -> None:
    """Initialize connections to all MCP servers.

    Fetches and caches tool schemas using temporary sessions.
    Failed connections don't prevent other servers from loading.
    """
    if self._initialized:
        return

    for server_config in self._config.mcp_servers:
        try:
            # Create client factory
            factory = self._create_client_factory(server_config)
            self._client_factories[server_config.name] = factory

            # Use temporary session to fetch schemas
            async with factory() as client:
                # Cache server information
                init_result = client.initialize_result
                if init_result and init_result.serverInfo:
                    self._server_infos[server_config.name] = ServerInfo(
                        name=server_config.name,
                        server_name=init_result.serverInfo.name or server_config.name,
                        version=init_result.serverInfo.version or "unknown",
                        instructions=init_result.instructions,
                    )
                else:
                    self._server_infos[server_config.name] = ServerInfo(
                        name=server_config.name,
                        server_name=server_config.name,
                        version="unknown",
                        instructions=None,
                    )

                # Fetch and cache tools
                tools = await client.list_tools()
                logger.info(f"Server '{server_config.name}' has {len(tools)} tool(s)")

                for tool in tools:
                    tool_key = f"{server_config.name}:{tool.name}"
                    self._tools[tool_key] = ToolInfo(
                        server_name=server_config.name,
                        name=tool.name,
                        description=tool.description or "",
                        input_schema=tool.inputSchema or {},
                    )

                # Fetch and cache resources
                try:
                    resources = await client.list_resources()
                    logger.info(f"Server '{server_config.name}' has {len(resources)} resource(s)")

                    for resource in resources:
                        resource_key = f"{server_config.name}:{resource.uri}"

                        # Generate description for text resources
                        description = resource.description
                        if not description and _is_text_mime_type(resource.mimeType):
                            try:
                                contents = await client.read_resource(str(resource.uri))
                                if contents and len(contents) > 0:
                                    first_content = contents[0]
                                    if hasattr(first_content, "text"):
                                        text_content = first_content.text
                                        description = text_content[:100]
                                        if len(text_content) > 100:
                                            description += "..."
                            except Exception as e:
                                logger.debug(f"Failed to read resource for description: {e}")

                        self._resources[resource_key] = ResourceInfo(
                            server_name=server_config.name,
                            uri=str(resource.uri),
                            name=resource.name,
                            description=description,
                            mime_type=resource.mimeType,
                            size=resource.size,
                        )
                except Exception as e:
                    logger.warning(f"Failed to list resources from '{server_config.name}': {e}")

                # Temporarily keep session for compatibility (will be removed)
                self._sessions[server_config.name] = client

        except Exception as e:
            logger.error(f"Failed to connect to server '{server_config.name}': {e}")

    self._initialized = True

    # Start health checker if enabled
    if self._config.health_check_enabled and self._client_factories:
        server_names = list(self._client_factories.keys())
        await self._health_checker.start(server_names)
        logger.info(f"Health checker started for {len(server_names)} server(s)")
```

**Step 2: 注意事项**

这里有个问题：`async with factory() as client` 退出后会关闭连接，但我们需要保持会话用于 `HealthChecker`。暂时保留 `_sessions` 并在下一个任务处理。

**Step 3: 运行测试**

```bash
uv run pytest tests/test_mcpx.py -v -k "test_init"
```

**Step 4: 提交**

```bash
git add src/mcpx/registry.py
git commit -m "refactor: initialize uses client_factory for schema fetching"
```

---

### Task 4: 添加 get_client_factory 方法

**Files:**
- Modify: `src/mcpx/registry.py`

**Step 1: 添加 get_client_factory 方法**

放在 `get_session` 方法之后：

```python
def get_client_factory(self, server_name: str) -> Callable[[], McpClient] | None:
    """Get client factory for a server.

    Args:
        server_name: Name of the server

    Returns:
        Client factory if exists, None otherwise
    """
    return self._client_factories.get(server_name)
```

**Step 2: 运行测试**

```bash
uv run pytest tests/test_mcpx.py -v -k "test_registry"
```

**Step 3: 提交**

```bash
git add src/mcpx/registry.py
git commit -m "refactor: add get_client_factory method"
```

---

### Task 5: 移除 _connect_server 方法（不再需要）

**Files:**
- Modify: `src/mcpx/registry.py:168-270`

**Step 1: 删除 _connect_server 方法**

这个方法不再需要，因为我们在 `initialize` 中直接使用临时会话。

**Step 2: 运行测试**

```bash
uv run pytest tests/test_mcpx.py -v
```

**Step 3: 修复测试中可能使用的 _connect_server**

如果有测试直接调用 `_connect_server`，改为使用 `initialize`。

**Step 4: 提交**

```bash
git add src/mcpx/registry.py tests/
git commit -m "refactor: remove _connect_server method"
```

---

### Task 6: 移除 reconnect_server 方法

**Files:**
- Modify: `src/mcpx/registry.py:425-470`

**Step 1: 删除 reconnect_server 方法及其调用**

会话隔离意味着每次请求都是新连接，无需手动重连。

**Step 2: 运行测试**

```bash
uv run pytest tests/test_mcpx.py -v
```

**Step 3: 提交**

```bash
git add src/mcpx/registry.py tests/
git commit -m "refactor: remove reconnect_server method"
```

---

## Phase 2: Executor 改造

### Task 7: 修改 Executor.execute 使用 client_factory

**Files:**
- Modify: `src/mcpx/executor.py:83-174`

**Step 1: 重写 execute 方法**

使用 `client_factory` + `async with` 替代长连接 + 手动重连：

```python
async def execute(
    self, server_name: str, tool_name: str, arguments: dict[str, Any]
) -> ExecutionResult:
    """Execute a tool using a fresh session for each request.

    Args:
        server_name: Name of the server
        tool_name: Name of the tool
        arguments: Tool arguments

    Returns:
        ExecutionResult with success status and data or error
    """
    # Get client factory
    factory = self._registry.get_client_factory(server_name)
    if factory is None:
        return ExecutionResult(
            server_name=server_name,
            tool_name=tool_name,
            success=False,
            data=None,
            error=f"No client factory for server '{server_name}'",
        )

    # Create fresh client for this request
    client = factory()
    try:
        async with client:
            result = await client.call_tool(tool_name, arguments=arguments)

        # Extract data from result
        data = self._extract_result_data(result)

        # Apply TOON compression if enabled and beneficial
        compressed_data, was_compressed = self._compressor.compress(data)

        return ExecutionResult(
            server_name=server_name,
            tool_name=tool_name,
            success=True,
            data=compressed_data,
            raw_data=data,
            compressed=was_compressed,
            format="toon" if was_compressed else "json",
        )

    except Exception as e:
        logger.error(f"Error executing tool '{server_name}:{tool_name}': {e}")
        return ExecutionResult(
            server_name=server_name,
            tool_name=tool_name,
            success=False,
            data=None,
            error=str(e),
        )
```

**Step 2: 移除不再需要的 _is_connection_error 方法**

Session isolation 意味着连接错误会自然恢复，无需特殊处理。

**Step 3: 运行测试**

```bash
uv run pytest tests/test_mcpx.py -v -k "test_exec"
```

**Step 4: 提交**

```bash
git add src/mcpx/executor.py tests/
git commit -m "refactor: executor uses client_factory with session isolation"
```

---

### Task 8: 修改 Registry.read_resource 使用 client_factory

**Files:**
- Modify: `src/mcpx/registry.py:361-383`

**Step 1: 重写 read_resource 方法**

```python
async def read_resource(
    self, server_name: str, uri: str
) -> Any | None:
    """Read resource content using a fresh session.

    Args:
        server_name: Name of the server
        uri: Resource URI to read

    Returns:
        List of content items, or None if factory not found/read fails
    """
    factory = self._client_factories.get(server_name)
    if factory is None:
        return None

    try:
        async with factory() as client:
            contents = await client.read_resource(uri)
            return contents
    except Exception as e:
        logger.error(f"Error reading resource '{uri}' from '{server_name}': {e}")
        return None
```

**Step 2: 运行测试**

```bash
uv run pytest tests/test_mcpx.py -v -k "test_resource"
```

**Step 3: 提交**

```bash
git add src/mcpx/registry.py
git commit -m "refactor: read_resource uses client_factory"
```

---

## Phase 3: 清理和验证

### Task 9: 移除 _sessions 字典

**Files:**
- Modify: `src/mcpx/registry.py`
- Modify: `src/mcpx/__main__.py`

**Step 1: 从 Registry 中移除 _sessions**

删除 `__init__` 中的 `_sessions` 定义和相关使用。

**Step 2: 更新 list_servers 方法**

```python
def list_servers(self) -> list[str]:
    """List all connected server names.

    Returns:
        List of server names
    """
    return list(self._client_factories.keys())
```

**Step 3: 更新 get_tool_list_text 方法**

```python
def get_tool_list_text(self) -> str:
    """Generate plain text list of available tools grouped by server.

    This is used for the inspect tool description.

    Returns:
        Plain text listing all available tools grouped by server
    """
    if not self._tools:
        return "No tools available."

    lines = ["Available tools (use inspect with server_name to get details):"]
    for server_name in sorted(self._client_factories.keys()):
        lines.append(f"  Server: {server_name}")
        for tool in self.list_tools(server_name):
            desc = tool.description[:60] + "..." if len(tool.description) > 60 else tool.description
            lines.append(f"    - {tool.name}: {desc}")
    return "\n".join(lines)
```

**Step 4: 运行测试**

```bash
uv run pytest tests/test_mcpx.py -v
```

**Step 5: 提交**

```bash
git add src/mcpx/registry.py src/mcpx/__main__.py
git commit -m "refactor: remove _sessions dictionary completely"
```

---

### Task 10: 移除 get_session 和 sessions 属性

**Files:**
- Modify: `src/mcpx/registry.py:404-418`

**Step 1: 删除 get_session 方法**

不再需要获取持久会话。

**Step 2: 删除 sessions 属性**

不再需要暴露所有会话。

**Step 3: 运行测试**

```bash
uv run pytest tests/test_mcpx.py -v
```

**Step 4: 提交**

```bash
git add src/mcpx/registry.py tests/
git commit -m "refactor: remove get_session and sessions property"
```

---

### Task 11: 更新 close 方法

**Files:**
- Modify: `src/mcpx/registry.py:472-493`

**Step 1: 重写 close 方法**

不再需要关闭长连接，只需停止健康检查：

```python
async def close(self) -> None:
    """Stop health checker and clear caches."""
    # Stop health checker
    await self._health_checker.stop()

    # Clear caches
    self._client_factories.clear()
    self._tools.clear()
    self._resources.clear()
    self._initialized = False
```

**Step 2: 运行测试**

```bash
uv run pytest tests/test_mcpx.py -v
```

**Step 3: 提交**

```bash
git add src/mcpx/registry.py
git commit -m "refactor: simplify close method"
```

---

## Phase 4: HealthChecker 适配

### Task 12: 修改 HealthChecker 使用 client_factory

**Files:**
- Modify: `src/mcpx/health.py`
- Modify: `src/mcpx/registry.py:495-505`

**Step 1: 更新 Registry 的健康检查回调**

```python
async def _get_session_for_health_check(self, server_name: str) -> McpClient | None:
    """Get a fresh session for health checking.

    Args:
        server_name: Name of the server

    Returns:
        New client session if factory exists, None otherwise
    """
    factory = self._client_factories.get(server_name)
    if factory is None:
        return None

    # Return a new client for health check
    return factory()
```

**Step 2: 更新 HealthChecker 确保关闭临时会话**

在 `health.py` 中确保健康检查后关闭会话：

```python
async def check_server(self, server_name: str) -> bool:
    """Check health of a single server.

    Args:
        server_name: Name of the server to check

    Returns:
        True if server is healthy, False otherwise
    """
    if self._get_session_callback is None:
        logger.warning("Session callback not set, skipping health check")
        return False

    try:
        session = await self._get_session_callback(server_name)
        if session is None:
            self._status.update_server(server_name, False, "No active session")
            return False

        # Use temporary session and close it
        async with session:
            # Try to ping the server
            if hasattr(session, "ping"):
                await asyncio.wait_for(session.ping(), timeout=self._check_timeout)
            else:
                # Fallback: try to list tools
                await asyncio.wait_for(
                    session.list_tools(), timeout=self._check_timeout
                )

        self._status.update_server(server_name, True)
        logger.debug(f"Health check passed for '{server_name}'")
        return True

    except asyncio.TimeoutError:
        self._status.update_server(server_name, False, f"Timeout after {self._check_timeout}s")
        logger.warning(f"Health check timeout for '{server_name}'")
        return False
    except Exception as e:
        self._status.update_server(server_name, False, str(e))
        logger.warning(f"Health check failed for '{server_name}': {e}")
        return False
```

**Step 3: 运行测试**

```bash
uv run pytest tests/test_mcpx.py -v -k "test_health"
```

**Step 4: 提交**

```bash
git add src/mcpx/registry.py src/mcpx/health.py
git commit -m "refactor: health checker uses client_factory"
```

---

## Phase 5: 完整验证

### Task 13: 运行所有测试并验证覆盖率

**Files:**
- Test: `tests/`

**Step 1: 运行完整测试套件**

```bash
uv run pytest tests/ -v --cov=src/mcpx --cov-report=term-missing
```

**Step 2: 验证覆盖率不低于基线**

确保覆盖率 ≥ 70%。

**Step 3: 运行类型检查**

```bash
uv run mypy src/mcpx
```

**Step 4: 运行代码检查**

```bash
uv run ruff check src/mcpx tests/
```

**Step 5: 如果测试失败，逐个修复**

不要跳过任何失败的测试。

**Step 6: 提交（如有修复）**

```bash
git add src/mcpx tests/
git commit -m "test: fix failing tests after refactor"
```

---

### Task 14: E2E 测试验证核心功能

**Files:**
- Test: `tests/test_e2e.py`

**Step 1: 创建临时 E2E 测试配置**

```bash
cat > /tmp/e2e-config.json << 'EOF'
{
  "mcp_servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "type": "stdio"
    }
  ]
}
EOF
```

**Step 2: 运行 E2E 测试**

```bash
uv run pytest tests/test_e2e.py -v
```

**Step 3: 验证功能清单**

- [ ] inspect 返回工具列表
- [ ] exec 执行工具成功
- [ ] resources 读取资源成功
- [ ] TOON 压缩正常工作
- [ ] Schema 压缩正常工作

**Step 4: 提交（如有修复）**

```bash
git add tests/
git commit -m "test: fix E2E tests"
```

---

### Task 15: 创建连接恢复测试

**Files:**
- Create: `tests/test_connection_recovery.py`

**Step 1: 编写连接恢复测试**

```python
"""Test connection recovery with session isolation."""

import asyncio
import pytest

from mcpx.config import McpServerConfig, ProxyConfig
from mcpx.registry import Registry
from mcpx.executor import Executor


async def test_connection_auto_recovery():
    """Verify that each request uses a fresh session.

    This test verifies the session isolation mechanism - each request
    gets a new connection, so connection failures don't persist.
    """
    config = ProxyConfig(
        mcp_servers=[
            McpServerConfig(
                name="test-server",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                type="stdio",
            )
        ]
    )

    registry = Registry(config)
    await registry.initialize()

    executor = Executor(registry)

    # First request should succeed
    result1 = await executor.execute("test-server", "read_file", {"path": "/tmp"})
    assert result1.success

    # Second request should also succeed (using fresh session)
    result2 = await executor.execute("test-server", "read_file", {"path": "/tmp"})
    assert result2.success

    await registry.close()


async def test_factory_returns_new_clients():
    """Verify that factory creates new client instances."""
    config = ProxyConfig(
        mcp_servers=[
            McpServerConfig(
                name="test-server",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                type="stdio",
            )
        ]
    )

    registry = Registry(config)
    await registry.initialize()

    factory = registry.get_client_factory("test-server")
    assert factory is not None

    # Multiple calls should return different instances
    client1 = factory()
    client2 = factory()

    # They should be different objects
    assert client1 is not client2

    # They should have different session states
    assert client1._session_state is not client2._session_state

    await registry.close()
```

**Step 2: 运行连接恢复测试**

```bash
uv run pytest tests/test_connection_recovery.py -v
```

**Step 3: 提交**

```bash
git add tests/test_connection_recovery.py
git commit -m "test: add connection recovery tests"
```

---

### Task 16: 更新文档

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Create: `docs/requirements/2026-01-25_proxyprovider_refactor_requirements.md`
- Create: `docs/requirements/2026-01-25_proxyprovider_refactor_verification.md`

**Step 1: 移动设计文档到 docs/requirements**

```bash
cp /Users/yanwu/conductor/workspaces/mcpx/milan/.context/proxyprovider-refactor-requirement.md \
   /Users/yanwu/conductor/workspaces/mcpx/milan/docs/requirements/2026-01-25_proxyprovider_refactor_requirements.md

cp /Users/yanwu/conductor/workspaces/mcpx/milan/.context/proxyprovider-refactor-verification.md \
   /Users/yanwu/conductor/workspaces/mcpx/milan/docs/requirements/2026-01-25_proxyprovider_refactor_verification.md
```

**Step 2: 更新 CLAUDE.md**

在核心架构部分更新连接管理描述：

```markdown
## 核心架构

### 设计模式

MCPX 使用 FastMCP Client 的 **Session Isolation** 模式：
- 每次请求通过 `client_factory` 创建新会话
- `async with client:` 自动管理连接生命周期
- 连接断开后下次请求自动恢复，无需手动重连
```

**Step 3: 更新 README.md**

添加关于连接稳定性的说明。

**Step 4: 更新需求状态**

将所有需求文档中的状态更新为最新。

**Step 5: 运行文档链接检查**

```bash
# 确保所有文档链接有效
grep -r "](./" docs/requirements/ | grep -v "\.md:" || true
```

**Step 6: 提交**

```bash
git add CLAUDE.md README.md docs/requirements/
git commit -m "docs: update documentation for proxyprovider refactor"
```

---

## Phase 6: 最终验证

### Task 17: 完整功能回归测试

**Files:**
- Test: `tests/`

**Step 1: 逐个验证所有现有需求**

**核心功能 (2026-01-24_core_features):**
```bash
# 工具收敛测试
uv run pytest tests/ -v -k "test_inspect or test_exec"
```

**MCP Resource (2026-01-25_mcp_resource):**
```bash
# 资源功能测试
uv run pytest tests/ -v -k "test_resource"
```

**Schema 压缩 (2026-01-25_schema_compression):**
```bash
# Schema 压缩测试
uv run pytest tests/ -v -k "test_schema"
```

**TOON 压缩 (2026-01-25_toon_multimodal):**
```bash
# TOON 压缩测试
uv run pytest tests/ -v -k "test_toon or test_compress"
```

**Step 2: 验收清单**

| 需求 | 状态 | 验证命令 |
|------|------|----------|
| 核心功能 | ✅ | `pytest tests/ -k "test_inspect or test_exec"` |
| MCP Resource | ✅ | `pytest tests/ -k "test_resource"` |
| Schema 压缩 | ✅ | `pytest tests/ -k "test_schema"` |
| TOON 压缩 | ✅ | `pytest tests/ -k "test_toon"` |
| 连接恢复 | ✅ | `pytest tests/test_connection_recovery.py` |

**Step 3: 最终覆盖率检查**

```bash
uv run pytest tests/ --cov=src/mcpx --cov-report=term
```

**Step 4: 记录最终结果**

保存测试结果到 `.context/final-test-results.txt`

**Step 5: 提交**

```bash
git add .context/
git commit -m "test: record final test results"
```

---

## Task 18: 创建 PR 准备清单

**Step 1: 生成 PR 描述**

```bash
cat > /Users/yanwu/conductor/workspaces/mcpx/milan/.context/pr-description.md << 'EOF'
# ProxyProvider 连接稳定性重构

## 概述

使用 FastMCP Client 的 Session Isolation 机制重构连接管理，简化代码并提升连接稳定性。

## 主要变更

### 架构变化
- **之前**: 长连接 + 手动重连
- **之后**: client_factory + 会话隔离

### 删除的代码
- `_sessions` 字典管理
- `reconnect_server()` 方法
- `_connect_server()` 方法
- 手动连接错误检测逻辑

### 新增的代码
- `_client_factories` 字典
- `_create_client_factory()` 方法
- `get_client_factory()` 方法

## 兼容性

- ✅ inspect/exec/resources 接口不变
- ✅ config.json 格式不变
- ✅ TOON 压缩功能不受影响
- ✅ Schema 压缩功能不受影响
- ✅ 多模态内容透传不受影响
- ✅ 资源缓存功能不受影响

## 测试

- 所有现有测试通过
- 新增连接恢复测试
- 覆盖率 ≥ 70%

## 相关文档

- Requirement: docs/requirements/2026-01-25_proxyprovider_refactor_requirements.md
- Verification: docs/requirements/2026-01-25_proxyprovider_refactor_verification.md
EOF
```

**Step 2: 检查分支状态**

```bash
git status
git log --oneline -10
```

**Step 3: 确保 PR 准备就绪**

```bash
# 确保所有更改已提交
git status

# 运行最终测试
uv run pytest tests/ --cov=src/mcpx

# 类型检查
uv run mypy src/mcpx

# 代码检查
uv run ruff check src/mcpx tests/
```

---

## 执行说明

### 使用 /ralph-wiggum:ralph-loop 执行

1. 启动循环：
   ```
   /ralph-wiggum:ralph-loop
   ```

2. 循环将逐个执行上述 18 个任务

3. 每个任务完成后检查：
   - 测试是否通过
   - 是否需要调整

### 检查点

在每个 Phase 结束后检查：
- Phase 1 (Task 1-6): Registry 重构完成
- Phase 2 (Task 7-8): Executor 改造完成
- Phase 3 (Task 9-11): 清理完成
- Phase 4 (Task 12): HealthChecker 适配完成
- Phase 5 (Task 13-16): 验证和文档完成
- Phase 6 (Task 17-18): 最终验证和 PR 准备

### 回滚条件

如果出现以下情况，停止并评估：
- 任何现有需求测试失败
- 覆盖率下降超过 5%
- 接口返回格式发生变化
EOF
