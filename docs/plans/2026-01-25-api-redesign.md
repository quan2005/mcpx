# API 语义化重构实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> **执行方式**: 使用 /superpowers:subagent-driven-development 逐任务执行

**Goal:** 重构 MCPX API，使命名和格式更接近传统编程语言，提升开发者体验

**Architecture:** 将 `inspect/exec` 重命名为 `describe/call`，参数从 `(server_name, tool_name)` 合并为 `method`，描述格式改为 `server.tool(params): desc` 的紧凑风格

**Tech Stack:** FastMCP 3.0, Pydantic v2, uv, pytest

**兼容性保证:**
- ✅ 配置格式不变
- ✅ TOON 压缩功能不受影响
- ✅ Schema 压缩功能不受影响
- ✅ 多模态内容透传不受影响
- ✅ 资源功能不受影响
- ⚠️ API 签名变化（需要客户端更新）

---

## Phase 1: 前置验证

### Task 0: 验证基线

**目的:** 在重构前确认所有现有功能正常，建立基线

**Files:**
- Test: `tests/`

**Step 1: 运行现有测试**

```bash
cd /Users/yanwu/conductor/workspaces/mcpx/san-jose
uv run pytest tests/ -v --cov=src/mcpx
```

**Step 2: 确认覆盖率基线**

记录当前覆盖率，确保重构后不低于此值。

**Step 3: 创建重构分支（如未创建）**

```bash
git branch --show-current | grep api-redesign || git checkout -b api-redesign
```

**Step 4: 记录基线结果**

将测试结果保存到 `.context/baseline-test-results.txt`

---

## Phase 2: 工具重命名

### Task 1: inspect → describe

**Files:**
- Modify: `src/mcpx/__main__.py:218-310`

**Step 1: 重命名工具函数**

将 `inspect` 函数重命名为 `describe`，更新函数签名和文档：

```python
@mcp.tool(description=full_desc)
async def describe(
    method: str,
) -> ToolResult | str:
    """Query tool information from MCP servers.

    Args:
        method: Method identifier in "server" or "server.tool" format
            - "server": List all tools from this server
            - "server.tool": Get detailed schema for this tool

    Returns:
        ToolResult with:
        - content: TOON 压缩后的数据（用于 AI 阅读）
        - structured_content: 原始未压缩的 JSON 数据（用于程序解析）

    Examples:
        # List all tools from a server
        describe(method="filesystem")

        # Get details for a specific tool
        describe(method="filesystem.read_file")
    """
```

**Step 2: 更新 method 解析逻辑**

```python
# Parse method string
parts = method.split(".", 1)
server_name = parts[0]
tool_name = parts[1] if len(parts) > 1 else None
```

**Step 3: 运行测试**

```bash
uv run pytest tests/ -v -k "describe or inspect"
```

**Step 4: 提交**

```bash
git add src/mcpx/__main__.py
git commit -m "refactor: rename inspect to describe, use method parameter"
```

---

### Task 2: exec → call

**Files:**
- Modify: `src/mcpx/__main__.py:343-430`

**Step 1: 重命名工具函数**

将 `exec` 函数重命名为 `call`，更新函数签名和文档：

```python
@mcp.tool
async def call(
    method: str,
    arguments: dict[str, object] | None = None,
) -> ToolResult | str | TextContent | ImageContent | EmbeddedResource | list[TextContent | ImageContent | EmbeddedResource]:
    """Execute an MCP tool.

    Args:
        method: Method identifier in "server.tool" format
        arguments: Tool arguments (use describe to get schema)

    Example:
        call(method="filesystem.read_file", arguments={"path": "/tmp/file.txt"})
    """
```

**Step 2: 更新 method 解析逻辑**

```python
# Parse method string
parts = method.split(".", 1)
if len(parts) != 2:
    error_data = {"error": f"Invalid method format: '{method}'. Expected 'server.tool'"}
    return json.dumps(error_data, ensure_ascii=False)

server_name, tool_name = parts
```

**Step 3: 运行测试**

```bash
uv run pytest tests/ -v -k "call or exec"
```

**Step 4: 提交**

```bash
git add src/mcpx/__main__.py
git commit -m "refactor: rename exec to call, use method parameter"
```

---

## Phase 3: 描述格式重构

### Task 3: 重写 generate_tools_description

**Files:**
- Modify: `src/mcpx/__main__.py:56-99`

**Step 1: 重写函数**

实现紧凑的 `server.tool(params): desc` 格式：

```python
def generate_tools_description(registry: "Registry") -> str:
    """Generate a compact description of all available tools.

    Format: server.tool(param, param?): description

    Args:
        registry: Initialized registry with cached tools

    Returns:
        Formatted string with all tools in compact format
    """
    tools_desc_lines = ["Available tools:"]

    for server_name in sorted(registry.list_servers()):
        for tool in registry.list_tools(server_name):
            # Extract parameter list from input_schema
            params = []
            properties = tool.input_schema.get("properties", {})
            required = set(tool.input_schema.get("required", []))
            for param_name in sorted(properties.keys()):
                # Required params shown as-is, optional with ?
                params.append(param_name if param_name in required else f"{param_name}?")
            params_str = ", ".join(params) if params else ""

            # Truncate description if too long
            desc = tool.description
            if len(desc) > 60:
                desc = desc[:57] + "..."

            # Format: server.tool(params): desc
            full_name = f"{server_name}.{tool.name}"
            if params_str:
                tools_desc_lines.append(f"  - {full_name}({params_str}): {desc}")
            else:
                tools_desc_lines.append(f"  - {full_name}: {desc}")

    return "\n".join(tools_desc_lines)
```

**Step 2: 更新 inspect → describe 的描述生成**

更新 `create_server` 中描述的初始化，使用新格式。

**Step 3: 运行测试**

```bash
uv run pytest tests/ -v -k "tools_description"
```

**Step 4: 提交**

```bash
git add src/mcpx/__main__.py
git commit -m "refactor: rewrite tools description to compact format"
```

---

### Task 4: 更新 generate_resources_description（可选）

**Files:**
- Modify: `src/mcpx/__main__.py:101-126`

**Step 1: 保持一致风格**

资源描述保持当前格式，因为资源有复杂的 URI 结构：

```
Available resources:
  Server: filesystem
    - file:///tmp/file.txt [text/plain]
```

**Step 2: 运行测试**

```bash
uv run pytest tests/ -v -k "resources_description"
```

**Step 3: 提交（如有变更）**

```bash
git add src/mcpx/__main__.py
git commit -m "refactor: update resources description for consistency"
```

---

## Phase 4: 测试更新

### Task 5: 更新所有测试中的 API 调用

**Files:**
- Modify: `tests/test_mcpx.py`
- Modify: `tests/test_e2e.py`

**Step 1: 全局替换**

```bash
# 在测试文件中替换 API 调用
# inspect -> describe
# exec -> call
# (server_name, tool_name) -> method="server.tool"
```

**Step 2: 更新测试用例示例**

```python
# 旧格式
# result = await exec(server_name="filesystem", tool_name="read_file", arguments={"path": "/tmp/file.txt"})

# 新格式
result = await call(method="filesystem.read_file", arguments={"path": "/tmp/file.txt"})
```

**Step 3: 运行所有测试**

```bash
uv run pytest tests/ -v
```

**Step 4: 修复所有失败测试**

逐个修复测试，确保使用新 API。

**Step 5: 提交**

```bash
git add tests/
git commit -m "test: update all tests to use new API (describe/call)"
```

---

### Task 6: 添加新 API 的专门测试

**Files:**
- Create: `tests/test_api_redesign.py`

**Step 1: 编写新 API 测试**

```python
"""Test new describe/call API with method parameter."""

import pytest

from mcpx.config import McpServerConfig, ProxyConfig
from mcpx.registry import Registry
from mcpx.executor import Executor


async def test_describe_with_server_only():
    """Test describe(method='server') returns all tools from server."""
    config = ProxyConfig(
        mcp_servers=[
            McpServerConfig(
                name="filesystem",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                type="stdio",
            )
        ]
    )

    registry = Registry(config)
    await registry.initialize()

    tools = registry.list_tools("filesystem")
    assert len(tools) > 0

    await registry.close()


async def test_describe_with_server_tool():
    """Test describe(method='server.tool') returns specific tool schema."""
    config = ProxyConfig(
        mcp_servers=[
            McpServerConfig(
                name="filesystem",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                type="stdio",
            )
        ]
    )

    registry = Registry(config)
    await registry.initialize()

    tool = registry.get_tool("filesystem", "read_file")
    assert tool is not None
    assert tool.name == "read_file"
    assert "path" in tool.input_schema.get("properties", {})

    await registry.close()


async def test_method_parsing():
    """Test method string parsing."""
    test_cases = [
        ("server", ("server", None)),
        ("server.tool", ("server", "tool")),
        ("server.nested.tool", ("server", "nested.tool")),  # 保持原样
    ]

    for method_str, expected in test_cases:
        parts = method_str.split(".", 1)
        result = (parts[0], parts[1] if len(parts) > 1 else None)
        assert result == expected


async def test_invalid_method_format():
    """Test error handling for invalid method format."""
    # method 必须至少包含 server 部分
    invalid_methods = [
        "",  # 空
        ".tool",  # 缺少 server
    ]

    for method in invalid_methods:
        parts = method.split(".", 1)
        assert len(parts) >= 1  # 至少有 server 部分
```

**Step 2: 运行新测试**

```bash
uv run pytest tests/test_api_redesign.py -v
```

**Step 3: 提交**

```bash
git add tests/test_api_redesign.py
git commit -m "test: add API redesign specific tests"
```

---

## Phase 5: 文档更新

### Task 7: 更新 CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: 更新核心架构部分**

```markdown
## 核心架构

### 设计模式

MCPX 将多个 MCP 服务器的工具和资源收敛为三个入口点：
- **describe**: 查询工具列表和 Schema（按需获取详情）
- **call**: 执行工具（使用 method 参数，格式为 "server.tool"）
- **resources**: 列出或读取 MCP 服务器的资源
```

**Step 2: 更新数据流部分**

```markdown
### 数据流

```
AI → describe(method="server.tool") → Registry._tools (缓存) → 压缩的 Schema
AI → call(method="server.tool", arguments={...}) → Executor → 临时会话 → MCP Server
AI → resources(server_name, uri) → Registry._resources / read_resource() → 资源
```
```

**Step 3: 更新示例**

```markdown
## API 示例

### 查询工具
```python
# 列出服务器的所有工具
describe(method="filesystem")

# 获取特定工具的 schema
describe(method="filesystem.read_file")
```

### 执行工具
```python
# 读取文件
call(method="filesystem.read_file", arguments={"path": "/tmp/file.txt"})

# 写入文件
call(method="filesystem.write_file", arguments={"path": "/tmp/file.txt", "content": "hello"})
```
```

**Step 4: 提交**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for new API"
```

---

### Task 8: 更新 README.md

**Files:**
- Modify: `README.md`

**Step 1: 更新 API 文档**

确保 README 反映新的 API。

**Step 2: 提交**

```bash
git add README.md
git commit -m "docs: update README.md for new API"
```

---

## Phase 6: 完整验证

### Task 9: 运行完整测试套件

**Files:**
- Test: `tests/`

**Step 1: 运行所有测试**

```bash
uv run pytest tests/ -v --cov=src/mcpx --cov-report=term-missing
```

**Step 2: 验证覆盖率**

确保覆盖率 ≥ 70%。

**Step 3: 类型检查**

```bash
uv run mypy src/mcpx
```

**Step 4: 代码检查**

```bash
uv run ruff check src/mcpx tests/
```

**Step 5: 提交（如有修复）**

```bash
git add src/mcpx tests/
git commit -m "test: fix failing tests after API redesign"
```

---

### Task 10: E2E 测试验证

**Files:**
- Test: `tests/test_e2e.py`

**Step 1: 运行 E2E 测试**

```bash
uv run pytest tests/test_e2e.py -v
```

**Step 2: 验证功能清单**

- [ ] describe(method) 返回工具列表
- [ ] describe(method="server.tool") 返回详细 schema
- [ ] call(method, arguments) 执行工具成功
- [ ] resources(server_name, uri) 读取资源成功
- [ ] TOON 压缩正常工作
- [ ] Schema 压缩正常工作

**Step 3: 提交（如有修复）**

```bash
git add tests/
git commit -m "test: fix E2E tests for new API"
```

---

### Task 11: 创建 PR 准备清单

**Step 1: 生成 PR 描述**

```bash
cat > /Users/yanwu/conductor/workspaces/mcpx/san-jose/.context/pr-description.md << 'EOF'
# API 语义化重构

## 概述

重构 MCPX API，使命名和格式更接近传统编程语言，提升开发者体验。

## 主要变更

### API 重命名
| 旧名称 | 新名称 | 变更 |
|-------|-------|------|
| `inspect(server_name, tool_name?)` | `describe(method)` | 参数合并为 method |
| `exec(server_name, tool_name, args)` | `call(method, args)` | 参数合并为 method |
| `resources(server_name, uri)` | `resources(server_name, uri)` | 保持不变 |

### method 参数格式
- `"server"` - 列出服务器所有工具
- `"server.tool"` - 指定具体工具

### 描述格式变更
**旧格式：**
```
Server: filesystem - Filesystem access
  - read_file(path, encoding?): Read file...
```

**新格式：**
```
- filesystem.read_file(path, encoding?): Read file...
```

## 兼容性

- ⚠️ **破坏性变更**: API 签名变化，需要客户端更新
- ✅ 配置格式不变
- ✅ TOON 压缩功能不受影响
- ✅ Schema 压缩功能不受影响
- ✅ 多模态内容透传不受影响

## 测试

- 所有现有测试已更新
- 新增 API 专门测试
- 覆盖率 ≥ 70%
EOF
```

**Step 2: 检查分支状态**

```bash
git status
git log --oneline -10
```

**Step 3: 最终验证**

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

### 使用 /superpowers:subagent-driven-development 执行

1. 启动子代理执行：
   ```
   /superpowers:subagent-driven-development
   ```

2. 逐任务执行上述 12 个任务

3. 每个任务完成后检查：
   - 测试是否通过
   - 是否需要调整

### 检查点

在每个 Phase 结束后检查：
- Phase 1 (Task 0): 基线验证完成
- Phase 2 (Task 1-2): 工具重命名完成
- Phase 3 (Task 3-4): 描述格式重构完成
- Phase 4 (Task 5-6): 测试更新完成
- Phase 5 (Task 7-8): 文档更新完成
- Phase 6 (Task 9-11): 最终验证和 PR 准备

### 回滚条件

如果出现以下情况，停止并评估：
- 任何现有需求测试失败
- 覆盖率下降超过 5%
- 压缩功能异常
