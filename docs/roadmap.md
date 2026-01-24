# MCPX Roadmap

## 项目状态

根据 [验证文档](./verification.md)，核心功能（8 个条款）已全部完成：
- ✅ FastMCP 框架架构
- ✅ 工具注册表与缓存
- ✅ 长连接执行器
- ✅ MCP 代理服务器（inspect + exec）
- ✅ 双传输方式（stdio + HTTP/SSE）
- ✅ 配置驱动
- ✅ 错误处理与降级
- ✅ E2E 测试覆盖（74%）

当前分支 `add-docker-support` 正在开发 Docker 支持。

---

## 待办事项

### P0 - 紧急 / 高价值

#### 1. 🔄 连接稳定性（通过 ProxyProvider 实现）
**状态**：待开发  
**描述**：采用 FastMCP ProxyProvider 重构连接管理，利用其 Session Isolation 特性获得连接恢复能力。

**背景**：
FastMCP ProxyProvider 的 Session Isolation 设计意味着每个请求可获得独立会话，无需手动实现重连逻辑：
- 当前 MCPX：长连接 + 手动重连 = 复杂度高
- ProxyProvider：会话隔离 = 隐式连接恢复

**实现要点**：
- 使用 `ProxyClient` 替代手动 `Client` 管理
- 利用 session isolation 特性处理连接断开
- 保持 `inspect`/`exec` 接口不变
- 可选：添加连接失败时的重试配置

**收益**：
- 简化连接管理代码
- 隐式获得连接恢复能力
- 减少自定义重连逻辑

**影响范围**：
- `src/mcpx/registry.py`：使用 ProxyClient 重构

**注意**：此条目合并了原"连接重连机制"和"FastMCP ProxyProvider 集成评估"。

---

#### 2. 🐳 Docker 支持
**状态**：开发中（`add-docker-support` 分支）  
**描述**：提供 Dockerfile 和使用文档，支持容器化部署。

**已完成**：
- ✅ Dockerfile（多阶段构建）
- ✅ .dockerignore
- ✅ README 文档更新

**待验证**：
- [ ] 构建和运行测试

---

### P1 - 高优先级

#### 3. 🖼️ 多模态内容支持（图片/资源）
**状态**：待开发
**描述**：支持透传 MCP 服务器的图片、资源等多模态内容类型。

**背景**：
当前 `exec` 工具返回类型为 `str`，导致下游返回的图片内容被 JSON 序列化，AI 无法直接显示：
- Playwright 截图：`{"type": "image", "data": "base64...", "mimeType": "image/png"}`
- 计算机视觉工具：分析结果 + 标注图片
- 文件资源：PDF、图片等二进制内容

**MCP 协议内容类型**：
```python
# 文本内容
{"type": "text", "text": "..."}

# 图片内容
{"type": "image", "data": "base64...", "mimeType": "image/png"}

# 资源内容
{"type": "resource", "uri": "file://...", "mimeType": "..."}
```

**实现要点**：
- `exec` 返回类型改为 `str | TextContent | ImageContent | list[TextContent | ImageContent]`
- `Executor._extract_result_data()` 识别并透传 MCP 内容块
- 纯 JSON 数据继续使用 TOON 压缩
- 保持向后兼容：纯文本返回不受影响

**影响范围**：
- `src/mcpx/executor.py`：内容提取和透传逻辑
- `src/mcpx/__main__.py`：`exec` 工具返回类型

**收益**：
- 支持 Playwright 等工具的截图功能
- 支持计算机视觉工具的图片返回
- 完整透传 MCP 多模态内容

---

#### 4. 📦 Schema 类型压缩（TypeScript 风格）
**状态**：待开发
**描述**：将工具的 `input_schema` 转换为 TypeScript 类型定义语法，减少 schema 的 token 消耗。

**背景**：
JSON Schema 格式冗长，TOON 格式对深度嵌套的 schema 效果不佳：

```typescript
// JSON Schema（约 200 字符）
{
  "type": "object",
  "properties": {
    "path": {"type": "string"},
    "tail": {"type": "number", "optional": true}
  },
  "required": ["path"]
}

// TypeScript 类型（约 40 字符）
{path: string; tail?: number;}
```

**优势**：
- 节省约 60-70% token
- LLM 对 TypeScript 语法高度熟悉，解析准确
- 可读性强，结构清晰

**实现要点**：
- 检测 `input_schema` 字段
- 将 JSON Schema 转换为 TypeScript 类型定义
- 支持基础类型：`string` / `number` / `boolean` / `array[]` / `object`
- 支持可选字段（`?:`）和联合类型（`|`）
- 可配置开关（`enable_schema_compression: bool`）

**压缩策略分层**：
| 数据类型 | 压缩方式 | 原因 |
|---------|---------|------|
| Schema | TypeScript 类型 | 结构化、LLM 熟悉、紧凑 |
| 简单数组 | TOON 格式 | 压缩率高（~50%） |
| 复杂嵌套数据 | TOON 格式 | 保持可读性 |

---

#### 5. 💓 健康检查与心跳
**状态**：待开发  
**描述**：定期检测 MCP 服务器连接状态，主动发现断连。

**实现要点**：
- 定期心跳探测（可配置间隔，默认 30s）
- 健康状态 API（`/health` 端点）
- 不健康服务器的标记和隔离
- 与重连机制联动

---

### P2 - 中优先级

#### 6. 📊 可观测性增强
**状态**：待开发  
**描述**：添加日志、指标和追踪支持。

**实现要点**：
- 结构化日志（JSON 格式）
- 关键指标暴露：
  - 连接状态和数量
  - 工具调用次数和延迟
  - 错误率
- OpenTelemetry 集成（可选）

---

#### 7. ⚡ 性能优化
**状态**：待开发  
**描述**：提升高并发场景下的性能表现。

**实现要点**：
- 连接池优化（复用策略）
- 并发限制（每服务器最大并发数）
- 请求超时配置
- 工具结果缓存（可选，短 TTL）

---

#### 8. 🧪 测试覆盖率提升
**状态**：持续改进  
**描述**：将测试覆盖率从 74% 提升到 85%+。

**重点区域**：
- 边界条件和错误路径
- 并发场景
- 配置解析

---

### P3 - 低优先级

#### 9. 🔥 配置热加载
**状态**：待开发  
**描述**：支持不重启服务更新配置。

**实现要点**：
- 监听配置文件变更
- 增量更新连接（新增/移除服务器）
- 配置变更事件通知

---

#### 10. 🖥️ Web 管理界面
**状态**：待开发  
**描述**：提供可视化管理界面。

**功能**：
- 服务器连接状态
- 工具列表和调用统计
- 配置管理
- 日志查看

---

#### 11. 🔌 连接池动态扩缩容
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

## 版本规划（建议）

### v0.2.0 - 稳定性版本
- [ ] 连接稳定性（ProxyProvider 重构）
- [ ] Docker 支持完成
- [ ] 健康检查

### v0.3.0 - 优化版本
- [ ] 多模态内容支持（图片/资源）
- [ ] Schema 类型压缩（TypeScript 风格）
- [ ] 可观测性增强
- [ ] 性能优化

### v0.4.0 - 功能版本
- [ ] 配置热加载
- [ ] Web 管理界面

---

*最后更新：2026-01-25（Schema 压缩改为 TypeScript 风格）*
