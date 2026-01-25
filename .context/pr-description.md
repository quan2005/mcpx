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
**旧格式**:
```
Server: filesystem - Filesystem access
  - read_file(path, encoding?): Read file...
```

**新格式**:
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

- 所有现有测试已更新（229/229 通过）
- 新增 27 个 API 专门测试
- 覆盖率 74%（超过基线 70%）
