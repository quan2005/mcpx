# MCPX 核心功能验证文档

**版本**: v0.1.0
**日期**: 2026-01-24
**对应需求**: [core_features_requirements.md](./2026-01-24_core_features_requirements.md)

## 1. 测试概述

本文档定义 MCPX 核心功能的验证测试用例，覆盖所有核心需求。

## 2. 单元测试

### 2.1 Registry 测试

| 测试用例 | 描述 | 预期结果 |
|---------|------|----------|
| `test_initialization` | 初始化连接所有服务器 | 成功连接所有可用服务器 |
| `test_single_server_failure` | 单个服务器连接失败 | 其他服务器正常工作 |
| `test_tool_caching` | 工具缓存正确性 | 缓存与服务器返回一致 |
| `test_get_tool` | 获取单个工具 | 返回正确的 ToolInfo |
| `test_list_tools` | 列出服务器工具 | 返回完整工具列表 |
| `test_get_session` | 获取服务器会话 | 返回有效的 Client 实例 |

### 2.2 Executor 测试

| 测试用例 | 描述 | 预期结果 |
|---------|------|----------|
| `test_execute_tool` | 执行工具 | 返回正确的执行结果 |
| `test_execute_with_arguments` | 带参数执行 | 参数正确传递 |
| `test_execute_missing_server` | 服务器不存在 | 返回清晰的错误信息 |
| `test_execute_missing_tool` | 工具不存在 | 返回清晰的错误信息 |
| `test_execute_invalid_arguments` | 无效参数 | 返回参数校验错误 |

## 3. E2E 测试

### 3.1 inspect 工具测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_inspect_list_servers` | 列出所有服务器 | 调用 `inspect()` | 返回所有服务器名称 |
| `test_inspect_list_tools` | 列出服务器工具 | 调用 `inspect(server_name)` | 返回该服务器的所有工具 |
| `test_inspect_get_tool_schema` | 获取工具 Schema | 调用 `inspect(server, tool)` | 返回工具的完整 Schema |
| `test_inspect_invalid_server` | 无效服务器 | 调用 `inspect("invalid")` | 返回错误信息 |

### 3.2 exec 工具测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_exec_simple_tool` | 执行简单工具 | 调用 `exec(server, tool, args)` | 返回执行结果 |
| `test_exec_no_arguments` | 无参数执行 | 调用 `exec(server, tool)` | 成功执行 |
| `test_exec_missing_required_arg` | 缺少必填参数 | 调用 `exec(server, tool, {})` | 返回参数校验错误 |
| `test_exec_unknown_argument` | 未知参数 | 调用 `exec(server, tool, {"unknown": 1})` | 返回参数校验错误 |

## 4. 集成测试

### 4.1 多服务器测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_multiple_servers` | 连接多个服务器 | 配置 2+ 个服务器 | 所有服务器正常工作 |
| `test_server_isolation` | 服务器隔离 | 不同服务器的工具互不影响 | 各自独立执行 |
| `test_failure_isolation` | 故障隔离 | 一个服务器失败 | 其他服务器不受影响 |

### 4.2 传输方式测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_stdio_transport` | stdio 传输 | 使用 stdio 启动 | 正常响应工具调用 |
| `test_http_transport` | HTTP/SSE 传输 | 使用 HTTP 启动 | 正常响应工具调用 |

## 5. 配置测试

| 测试用例 | 描述 | 预期结果 |
|---------|------|----------|
| `test_valid_config` | 有效配置 | 成功加载并初始化 |
| `test_missing_config` | 配置文件不存在 | 退出并提示 |
| `test_invalid_json` | JSON 格式错误 | 退出并提示 |
| `test_empty_servers` | 空服务器列表 | 正常启动（无工具） |

## 6. 性能测试

| 指标 | 测试方法 | 验收标准 |
|------|----------|----------|
| 初始化时间 | 测量启动到就绪时间 | < 5 秒 |
| inspect 响应时间 | 测量查询延迟 | < 100 ms |
| exec 响应时间 | 测量执行延迟 | 取决于下游 |

## 7. 验收标准

所有测试用例通过，且：
- 代码覆盖率 ≥ 70%
- 无已知的严重 bug
- 文档完整（README + CLAUDE.md）
