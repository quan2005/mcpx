# Schema 压缩需求文档

**版本**: v0.4.0
**日期**: 2026-01-25
**状态**: ✅ 已完成

## 1. 概述

将工具的 `input_schema` (JSON Schema) 转换为 TypeScript 类型定义语法，进一步减少 token 消耗。

## 2. 核心需求

### 2.1 Schema 压缩

**需求描述**: 将 JSON Schema 转换为 TypeScript 类型

**问题**: JSON Schema 格式冗长，TOON 格式对深度嵌套的 schema 效果不佳

**解决方案**: 使用 TypeScript 类型语法，LLM 高度熟悉且格式紧凑

### 2.2 压缩效果

```typescript
// JSON Schema (~200 tokens)
{
  "type": "object",
  "properties": {
    "path": {"type": "string", "description": "文件路径"},
    "tail": {"type": "number"}
  },
  "required": ["path"]
}

// TypeScript (~40 tokens)
{path: string /* 文件路径 */; tail?: number}
```

**压缩率**: 约 60-70%

### 2.3 配置项

```json
{
  "schema_compression_enabled": true,
  "max_description_len": 300
}
```

## 3. 功能要求

### 3.1 支持的类型

| JSON Schema | TypeScript |
|-------------|------------|
| `string` | `string` |
| `number/integer` | `number` |
| `boolean` | `boolean` |
| `null` | `null` |
| `array` | `T[]` |
| `object` | `{...}` |
| `enum` | `union` |
| `anyOf/oneOf` | `union` |

### 3.2 可选字段

```typescript
// required: ["path"]
{path: string; optional?: number}
```

### 3.3 描述注释

```typescript
// description 保留为注释
{path: string /* 文件路径 */}
```

## 4. 模块设计

### 4.1 SchemaConverter

```python
class SchemaConverter:
    def __init__(self, include_descriptions: bool, max_description_len: int)
    def convert(self, schema: dict) -> str
    def _convert_type(self, schema: dict, required: bool) -> str
    def _convert_array(self, schema: dict) -> str
    def _convert_object(self, schema: dict) -> str
    def _convert_union(self, schemas: list) -> str
    def _resolve_ref(self, ref: str) -> str
```

### 4.2 便捷函数

```python
def json_schema_to_typescript(
    schema: dict,
    include_descriptions: bool = True,
    max_description_len: int = 50
) -> str
```

## 5. 集成方式

### 5.1 inspect 工具

```python
# 在 inspect 中使用
_maybe_compress_schema(tool.input_schema)
```

### 5.2 exec 工具

```python
# 参数校验错误时返回压缩后的 Schema
return {
    "error": "...",
    "tool_schema": _maybe_compress_schema(tool.input_schema)
}
```

## 6. 高级特性

### 6.1 $ref 解析

支持解析同一 schema 内的 `$defs` 和 `definitions` 引用。

### 6.2 嵌套结构

支持深度嵌套的对象和数组。

### 6.3 联合类型

支持 `anyOf` 和 `oneOf` 转换为 TypeScript 联合类型 (`|`)。

## 7. 验收标准

- [ ] 基本类型正确转换
- [ ] 嵌套结构正确转换
- [ ] 可选字段正确标记 (`?`)
- [ ] 描述正确保留为注释
- [ ] $ref 引用正确解析
- [ ] 联合类型正确转换
- [ ] 压缩率 ≥ 60%
- [ ] 单元测试覆盖
