# TOON 压缩与多模态支持需求文档

**版本**: v0.3.0
**日期**: 2026-01-25
**状态**: ✅ 已完成

## 1. 概述

为 MCPX 添加 TOON 数据压缩、健康检查和多模态内容支持。

## 2. 核心需求

### 2.1 TOON 压缩

**需求描述**: 对工具执行结果进行 TOON 格式压缩，减少 token 消耗

**功能要求**:
- 可配置压缩开关
- 可配置最小压缩阈值
- 双格式返回：压缩后 (`content`) + 原始 (`structured_content`)

**配置项**:
```json
{
  "toon_compression_enabled": true,
  "toon_compression_min_size": 3
}
```

### 2.2 健康检查

**需求描述**: 定期检测 MCP 服务器连接状态，主动发现断连

**功能要求**:
- 定期心跳探测（可配置间隔）
- 失败阈值标记不健康
- 与重连机制联动

**配置项**:
```json
{
  "health_check_enabled": true,
  "health_check_interval": 30,
  "health_check_timeout": 5,
  "health_check_failure_threshold": 2
}
```

### 2.3 多模态内容支持

**需求描述**: 透传 MCP 服务器的图片、资源等多模态内容

**功能要求**:
- 识别 `TextContent`、`ImageContent`、`EmbeddedResource`
- 多模态内容直接透传，不经过 TOON 压缩
- 支持单项和多项内容列表

### 2.4 配置管理模块

**需求描述**: 将配置类独立到 `config.py` 模块

**模块**:
```python
src/mcpx/
├── config.py       # 配置类
├── compression.py  # TOON 压缩器
├── content.py      # 多模态内容处理
└── health.py       # 健康检查器
```

## 3. 模块设计

### 3.1 ToonCompressor

```python
class ToonCompressor:
    def __init__(self, enabled: bool, min_size: int)
    def compress(self, data: Any, min_size: int) -> tuple
```

### 3.2 HealthChecker

```python
class HealthChecker:
    def __init__(self, check_interval, check_timeout, failure_threshold)
    async def start(self, server_names: list[str])
    async def stop()
    async def check_server(self, server_name: str) -> bool
    def get_server_health(self, server_name: str) -> ServerHealth
```

### 3.3 ContentType 检测

```python
def is_multimodal_content(obj: Any) -> bool
def detect_content_type(obj: Any) -> str
```

## 4. 数据流变化

### 4.1 压缩流程

```
MCP Server 响应
    ↓
Executor._extract_result_data()
    ↓
TOON 压缩 (ToonCompressor)
    ↓
返回 ToolResult(content=压缩, structured_content=原始)
```

### 4.2 多模态透传

```
MCP Server 多模态响应
    ↓
is_multimodal_content() 检测
    ↓
直接返回原始对象 (不压缩)
```

## 5. 返回格式

### 5.1 普通数据

```python
ToolResult(
    content="...",  # TOON 压缩后
    structured_content={"result": {...}}  # 原始数据
)
```

### 5.2 多模态数据

```python
ImageContent(data="base64...", mimeType="image/png")
# 或
[TextContent(text="..."), ImageContent(...)]
```

## 6. 验收标准

- [ ] TOON 压缩正常工作，节省 30%+ token
- [ ] 健康检查定期探测，正确标记不健康服务器
- [ ] 多模态内容正确透传
- [ ] 双格式返回正确（压缩 + 原始）
- [ ] 配置类独立到 config.py
- [ ] 测试覆盖率 ≥ 70%
