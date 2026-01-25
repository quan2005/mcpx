# MCP Resource 动态加载需求文档

**版本**: v0.3.0
**日期**: 2026-01-25
**状态**: ✅ 已完成

## 1. 概述

为 MCPX 添加 MCP 协议 Resource（资源）支持，允许 AI 查询和读取 MCP 服务器暴露的资源，如文件、配置、数据等。

## 2. 背景与动机

### 2.1 MCP Resource 概念

MCP 协议定义了 Resource 概念，允许服务器暴露可读取的资源：

| 资源类型 | 示例 |
|---------|------|
| 文件系统 | 文件内容、目录列表 |
| 配置 | 环境变量、配置文件 |
| 数据 | 数据库查询结果、缓存内容 |
| 动态 | 日志、指标、状态信息 |

### 2.2 当前限制

MCPX 仅支持 Tools（工具）查询和执行，未实现 Resource 支持，导致 AI 无法访问 MCP 服务器暴露的资源。

## 3. 核心需求

### 3.1 resources 工具

**需求描述**: 新增 `resources` 工具，用于读取资源内容

**功能要求**:
- 读取指定 URI 的资源内容
- 支持文本和二进制内容
- URI 为必填参数

**接口设计**:
```python
resources(
    server_name: str,      # 必填：服务器名称
    uri: str,              # 必填：资源 URI
) -> str | list | dict
```

**返回格式**:
- 文本资源: 返回字符串内容
- 二进制资源: 返回包含 uri、mime_type、blob 的字典
- 多项内容: 返回内容项列表

### 3.2 资源缓存

**需求描述**: 在 Registry 中缓存资源信息，避免重复查询

**功能要求**:
- 连接时缓存资源列表
- 缓存包含: uri, name, description, mime_type, size
- 重连时自动刷新缓存
- **自动生成描述**: 文本资源若无 description，自动读取前 100 个字符作为描述

### 3.3 文本资源描述自动生成

**需求描述**: 为缺少描述的文本资源自动生成摘要

**功能要求**:
- 检测文本 MIME 类型（text/*, application/json 等）
- 读取资源内容前 100 个字符
- 超过 100 字符时添加 "..." 后缀

### 3.3 多模态内容支持

**需求描述**: 支持文本和二进制资源内容

**内容类型**:
- `TextResourceContents`: 文本内容（直接返回字符串）
- `BlobResourceContents`: 二进制内容（返回 base64 编码）

## 4. 模块设计

### 4.1 ResourceInfo 类

```python
class ResourceInfo(BaseModel):
    """Cached resource information."""

    server_name: str
    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None
    size: int | None = None

    def to_dict(self) -> dict[str, Any]
```

### 4.2 Registry 扩展

```python
class Registry:
    # 新增属性
    _resources: dict[str, ResourceInfo]

    # 新增方法
    def list_resources(self, server_name: str) -> list[ResourceInfo]
    def list_all_resources(self) -> list[ResourceInfo]
    def get_resource(self, server_name: str, uri: str) -> ResourceInfo | None
    async def read_resource(self, server_name: str, uri: str) -> Any | None
```

### 4.3 资源描述生成

```python
def generate_resources_description(registry: Registry) -> str
```

### 4.4 文本 MIME 类型检测

```python
def _is_text_mime_type(mime_type: str | None) -> bool
```

支持的文本 MIME 类型：
- `text/*`
- `application/json`
- `application/xml`
- `application/javascript`
- `application/x-yaml`
- `application/x-sh`
- `application/x-python`
- 等

## 5. 数据流

### 5.1 读取资源

```
AI → resources(server_name, uri)
    ↓
Registry.read_resource()
    ↓
MCP Server.read_resource()
    ↓
返回资源内容 (TextResourceContents / BlobResourceContents)
```

### 5.2 资源缓存（带自动描述生成）

```
MCP Server 连接
    ↓
list_resources() 获取资源列表
    ↓
对每个资源：
  - 如果 description 为空且是文本类型
  - 读取内容前 100 字符作为 description
    ↓
缓存到 Registry._resources
```

## 6. 返回格式示例

### 6.1 文本资源

```
{"theme": "dark", "language": "zh-CN"}
```

### 6.3 二进制资源

```json
{
  "uri": "image://logo.png",
  "mime_type": "image/png",
  "blob": "iVBORw0KGgo..."
}
```

## 7. 工具描述

资源描述包含以下信息：
- `server_name`: 服务器名称
- `uri`: 资源 URI
- `name`: 资源名称
- `description`: 资源描述（可选）
- `mime_type`: MIME 类型（可选）
- `size`: 大小（字节，可选）

## 8. 验收标准

- [x] `resources` 工具正常工作
- [x] `uri` 参数为必填
- [x] 读取文本资源返回字符串
- [x] 读取二进制资源返回包含 blob 的字典
- [x] 资源缓存在 Registry 中正确维护
- [x] 重连时资源缓存正确刷新
- [x] 文本资源自动生成 description（前 100 字符）
- [x] 测试覆盖率 ≥ 75%

## 9. 影响范围

| 文件 | 变更 |
|------|------|
| `src/mcpx/registry.py` | 新增 ResourceInfo 类和资源相关方法 |
| `src/mcpx/__main__.py` | 新增 `resources` 工具和资源描述生成 |
| `tests/test_e2e.py` | 新增资源相关 E2E 测试 |
