# Schema 压缩验证文档

**版本**: v0.4.0
**日期**: 2026-01-25
**对应需求**: [schema_compression_requirements.md](./2026-01-25_schema_compression_requirements.md)

## 1. 测试概述

本文档定义 Schema 压缩功能的验证测试用例。

## 2. 基本类型测试

| 测试用例 | 输入 | 预期输出 |
|---------|------|----------|
| `test_string_type` | `{"type": "string"}` | `string` |
| `test_number_type` | `{"type": "number"}` | `number` |
| `test_integer_type` | `{"type": "integer"}` | `number` |
| `test_boolean_type` | `{"type": "boolean"}` | `boolean` |
| `test_null_type` | `{"type": "null"}` | `null` |

## 3. 复合类型测试

### 3.1 数组类型

| 测试用例 | 输入 | 预期输出 |
|---------|------|----------|
| `test_simple_array` | `{"type": "array", "items": {"type": "string"}}` | `string[]` |
| `test_complex_array` | `{"type": "array", "items": {"type": "object"}}` | `{}[]` |
| `test_nested_array` | `{"type": "array", "items": {"type": "array"}}` | `unknown[][]` |

### 3.2 对象类型

| 测试用例 | 输入 | 预期输出 |
|---------|------|----------|
| `test_empty_object` | `{"type": "object", "properties": {}}` | `{}` |
| `test_simple_object` | `{"type": "object", "properties": {"a": {"type": "string"}}}` | `{a: string}` |
| `test_nested_object` | 对象嵌套 | 正确嵌套语法 |

## 4. 可选字段测试

| 测试用例 | 输入 | 预期输出 |
|---------|------|----------|
| `test_required_field` | `required: ["a"]` | `{a: T}` |
| `test_optional_field` | `required: []` | `{a?: T}` |
| `test_mixed_fields` | 部分必填 | `a?: T; b: T` |

## 5. 描述注释测试

| 测试用例 | 输入 | 预期输出 |
|---------|------|----------|
| `test_with_description` | 带描述的字段 | `{a: T /* 描述 */}` |
| `test_long_description_truncated` | 超长描述 | 截断到 max_length |
| `test_without_description` | 无描述 | 无注释 |
| `test_description_disabled` | include_descriptions=False | 无注释 |

## 6. 联合类型测试

| 测试用例 | 输入 | 预期输出 |
|---------|------|----------|
| `test_anyof` | `anyOf: [{"type": "string"}, {"type": "number"}]` | `string \| number` |
| `test_oneof` | `oneOf: [...]` | `T \| U` |
| `test_enum` | `enum: ["a", "b"]` | `"a" \| "b"` |
| `test_const` | `const: "value"` | `"value"` |

## 7. $ref 解析测试

| 测试用例 | 输入 | 预期输出 |
|---------|------|----------|
| `test_ref_defs` | `$ref: "#/$defs/Type"` | 展开引用的类型 |
| `test_ref_definitions` | `$ref: "#/definitions/Type"` | 展开引用的类型 |
| `test_nested_ref` | 嵌套引用 | 正确展开 |

## 8. 压缩率测试

| 测试用例 | 测试方法 | 验收标准 |
|---------|----------|----------|
| `test_compression_ratio_simple` | 简单 schema | ≥ 60% |
| `test_compression_ratio_complex` | 复杂 schema | ≥ 50% |
| `test_compression_ratio_nested` | 嵌套 schema | ≥ 60% |

## 9. 边界条件测试

| 测试用例 | 描述 | 预期结果 |
|---------|------|----------|
| `test_empty_schema` | 空 schema | `unknown` |
| `test_invalid_schema` | 无效 schema | 不崩溃，返回 `unknown` |
| `test_array_of_types` | 类型数组 | `string \| number \| ...` |
| `test_allOf` | allOf 交叉 | 返回第一个类型 |

## 10. 集成测试

### 10.1 inspect 集成

| 测试用例 | 描述 | 预期结果 |
|---------|------|----------|
| `test_inspect_compressed_schema` | inspect 返回压缩 schema | TypeScript 格式 |
| `test_inspect_disabled_compression` | 禁用压缩 | JSON Schema 格式 |

### 10.2 exec 集成

| 测试用例 | 描述 | 预期结果 |
|---------|------|----------|
| `test_exec_error_compressed_schema` | 参数错误返回压缩 schema | TypeScript 格式 |

## 11. 验收标准

所有测试用例通过，且：
- 基本类型转换 100% 正确
- 复杂类型转换 ≥ 95% 正确
- 压缩率 ≥ 60%
- 测试覆盖率 ≥ 80%
