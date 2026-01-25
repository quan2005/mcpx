# Session Isolation 重构需求文档

**版本**: v0.4.0
**日期**: 2026-01-25
**状态**: ✅ 已完成

## 1. 概述

将 MCPX 从「长连接 + 手动重连」架构重构为「client_factory + 会话隔离」模式，简化连接管理。

## 2. 背景与动机

### 2.1 当前架构问题

| 问题 | 影响 |
|------|------|
| 长连接管理复杂 | 需手动维护 `_sessions` 状态 |
| 手动重连逻辑冗长 | `reconnect_server()` 代码约 100 行 |
| 连接状态同步 | `_sessions` 与实际连接可能不一致 |
| 健康检查额外复杂度 | 需要特殊处理会话生命周期 |

### 2.2 FastMCP Session Isolation

FastMCP 的 client_factory 模式提供会话隔离：

```python
# 每次请求创建新会话
factory = _create_client_factory(server_config)
client = factory()
async with client:
    result = await client.call_tool(tool_name, arguments)
# 会话自动关闭
```

**优势**：
- 无需维护 `_sessions` 字典
- 每次请求是新连接，无需手动重连
- 连接错误后下次请求自动恢复

## 3. 核心需求

### 3.1 Registry 改造

**删除**:
- `_sessions: dict[str, McpClient]`
- `reconnect_server()` 方法
- `get_session()` 方法
- `sessions` 属性

**新增**:
- `_client_factories: dict[str, Callable[[], McpClient]]`
- `get_client_factory()` 方法

### 3.2 Executor 改造

使用 client_factory + async with 模式：

```python
async def execute(self, server_name, tool_name, arguments):
    factory = self._registry.get_client_factory(server_name)
    client = factory()
    async with client:
        result = await client.call_tool(tool_name, arguments)
    return process_result(result)
```

### 3.3 HealthChecker 适配

使用临时会话进行健康检查：

```python
async def check_server(self, server_name):
    client = await self._get_client_callback(server_name)
    async with client:
        await client.ping()
    return True
```

### 3.4 接口兼容性

- `inspect` 接口：返回格式不变
- `exec` 接口：返回格式不变
- `resources` 接口：返回格式不变
- 配置文件：格式不变

## 4. 验收标准

- [x] `Registry._sessions` 已删除
- [x] `Registry._client_factories` 已添加
- [x] `Executor.execute()` 使用 client_factory
- [x] `HealthChecker` 使用临时会话
- [x] 接口返回格式不变
- [x] 测试覆盖率 ≥ 70%
- [x] 所有现有测试通过

## 5. 影响范围

| 文件 | 变更 |
|------|------|
| `src/mcpx/registry.py` | 删除 _sessions，新增 _client_factories |
| `src/mcpx/executor.py` | 使用 client_factory，删除重连逻辑 |
| `src/mcpx/health.py` | 使用临时会话进行检测 |
| `tests/test_e2e.py` | 新增验收测试 |
| `tests/test_health.py` | 更新 mock 支持 async context manager |
