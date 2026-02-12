# MCPX Roadmap

## 项目状态

根据 [验证文档](./requirements/)，核心功能（8 个条款）已全部完成：

- ✅ FastMCP 框架架构
- ✅ 工具注册表与缓存（Session Isolation 模式）
- ✅ client_factory 执行器（每次请求独立会话）
- ✅ MCP 代理服务器（inspect + exec + resources）
- ✅ 双传输方式（stdio + HTTP/SSE）
- ✅ 配置驱动
- ✅ 错误处理与降级
- ✅ E2E 测试覆盖（74%）

---

## 已完成功能

| # | 功能 | PR | 日期 |
|---|------|----|----|
| 1 | 核心功能（Registry、Executor、inspect/exec） | #1 | 2026-01-24 |
| 2 | Docker 支持 | #2 | 2026-01-24 |
| 3 | TOON 压缩 + 健康检查 + 多模态内容 | #3 | 2026-01-25 |
| 4 | Schema 压缩（TypeScript 风格） | #4 | 2026-01-25 |
| 5 | MCP Resource 动态加载 | #5 | 2026-01-25 |
| 6 | 连接稳定性重构（Session Isolation） | - | 2026-01-25 |
| 7 | SSE 传输支持 + 开发流程 skills | #16 | 2026-01-27 |
| 8 | 端口自动检测和切换 | - | 2026-01-27 |
| 9 | Web Dashboard（React SPA + REST API） | - | 2026-02-09 |

---

## 待办事项

### P0 - 紧急 / 高价值

#### 1. ✅ 连接稳定性（Session Isolation 重构）
**状态**：已完成 ✅

**描述**：采用 FastMCP 的 client_factory 模式重构连接管理，实现 Session Isolation。

**完成内容**：
- ✅ Registry 使用 `_client_factories` 替代 `_sessions`
- ✅ Executor 每次请求通过 `factory()` 创建新会话
- ✅ 使用 `async with client:` 自动管理会话生命周期
- ✅ 移除 `reconnect_server()` 手动重连逻辑
- ✅ HealthChecker 使用临时会话进行检测
- ✅ 202 个测试通过，覆盖率 74%

**影响范围**：`registry.py`, `executor.py`, `health.py`

---

### P1 - 高优先级

#### 2. 📊 可观测性增强
**状态**：待开发

**描述**：添加日志、指标和追踪支持。

**实现要点**：
- 结构化日志（JSON 格式）
- 关键指标暴露：连接状态、工具调用次数和延迟、错误率
- OpenTelemetry 集成（可选）

---

#### 3. ⚡ 性能优化
**状态**：待开发

**描述**：提升高并发场景下的性能表现。

**实现要点**：
- 连接池优化（复用策略）
- 并发限制（每服务器最大并发数）
- 请求超时配置
- 工具结果缓存（可选，短 TTL）

---

#### 4. 🧪 测试覆盖率提升
**状态**：持续改进

**描述**：将测试覆盖率从 74% 提升到 85%+。

**重点区域**：边界条件和错误路径、并发场景、配置解析

---

### P3 - 低优先级

#### 5. 🔥 配置热加载
**状态**：已完成 ✅

**描述**：支持不重启服务更新配置。

**实现要点**：
- ✅ Settings 页面支持修改配置并热重载
- ✅ 增量更新连接（新增/移除服务器）
- ✅ PUT /config API 触发重载

---

#### 6. 🖥️ Web 管理界面
**状态**：已完成 ✅

**描述**：提供可视化管理界面。

**功能**：
- ✅ Dashboard 总览页面
- ✅ Servers 页面（查看详情、启用/禁用服务器）
- ✅ Tools 页面（浏览、搜索、启用/禁用工具）
- ✅ Resources 页面（浏览、预览内容）
- ✅ Health 页面（健康状态、手动检查）
- ✅ Settings 页面（配置编辑、热重载）

**技术栈**：React 19 + TypeScript + Vite + Tailwind CSS v4

**启动方式**：
- `mcpx-toolkit --gui --open config.json` - 浏览器模式
- `mcpx-toolkit --gui --desktop config.json` - 桌面模式

---

#### 7. 🔌 连接池动态扩缩容
**状态**：待开发

**描述**：根据负载自动调整连接池大小。

---

## 优先级说明

| 优先级 | 含义 | 决策依据 |
|--------|------|----------|
| P0 | 紧急 / 高价值 | 影响核心稳定性或已在开发中 |
| P1 | 高优先级 | 对用户体验有重大提升 |
| P2 | 中优先级 | 改进性能和可维护性 |
| P3 | 低优先级 | 锦上添花，可延后 |

---

## 版本规划

### v0.1.0 - 基础版本 ✅
- ✅ 核心功能（Registry、Executor、inspect/exec）
- ✅ stdio + HTTP/SSE 双传输
- ✅ 配置驱动
- ✅ E2E 测试 74% 覆盖率

### v0.2.0 - 增强版本 ✅
- ✅ TOON 压缩
- ✅ 健康检查
- ✅ 多模态内容透传
- ✅ Docker 支持
- ✅ Schema 压缩（TypeScript 风格）

### v0.3.0 - 资源支持版本 ✅
- ✅ MCP Resource 动态加载
- ✅ resources 工具（列表/读取资源）

### v0.4.0 - 稳定性版本 ✅
- ✅ 连接稳定性（Session Isolation 重构）
- ✅ 移除长连接和手动重连逻辑
- ✅ client_factory 模式
- ✅ 202 个测试，74% 覆盖率

### v0.5.0 - API 简化版本 ✅
- ✅ 移除 describe 工具（功能合并到 invoke）
- ✅ call 更名为 invoke
- ✅ resources 更名为 read
- ✅ 工具数量从 3 个减少到 2 个
- ✅ 215 个测试，73% 覆盖率

### v0.1.4 - SSE 支持版本 ✅
- ✅ SSE 传输自动检测（URL 包含 `/sse`）
- ✅ `SSETransport` 支持
- ✅ 项目开发流程 skills

### v0.2.1 - 用户体验改进 ✅
- ✅ 端口自动检测和切换（8000 端口被占用时自动尝试 8001、8002...）
- ✅ `port_utils.py` 模块（`find_available_port` 函数）
- ✅ Claude Desktop 配置文档修正（使用 HTTP 类型）

### v0.5.0 - Dashboard 基础版本 ✅
- ✅ Web Dashboard（React + TypeScript）
- ✅ 14 个 REST API 端点
- ✅ 服务器增量启停
- ✅ 工具启用/禁用管理
- ✅ 配置热重载

### v0.6.0 - Dashboard 增强版本（当前目标）
- [x] 工具详情模态框 + 执行测试界面
- [x] 服务器配置编辑器（添加/编辑/删除）
- [x] Toast 通知 + 确认对话框
- [x] 后端 API 测试覆盖 88%
- [ ] WebSocket 实时更新（可选）

### v0.7.0 - 优化版本（规划）
- [ ] 可观测性增强
- [ ] 性能优化
- [ ] 测试覆盖率提升到 85%+

---

*最后更新：2026-02-12（v0.6.0：Dashboard 增强版本规划）*
