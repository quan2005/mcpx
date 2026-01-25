# TOON 压缩与多模态支持验证文档

**版本**: v0.3.0
**日期**: 2026-01-25
**对应需求**: [toon_multimodal_requirements.md](./2026-01-25_toon_multimodal_requirements.md)

## 1. 测试概述

本文档定义 TOON 压缩、健康检查、多模态支持的验证测试用例。

## 2. TOON 压缩测试

### 2.1 压缩器测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_compress_dict` | 压缩字典 | 输入嵌套字典 | 返回 TOON 格式 |
| `test_compress_list` | 压缩列表 | 输入列表 | 返回 TOON 格式 |
| `test_compress_disabled` | 禁用压缩 | enabled=False | 返回原始数据 |
| `test_compress_small_data` | 小数据不压缩 | 数据量 < min_size | 返回原始数据 |
| `test_compress_ratio` | 压缩率检查 | 对比压缩前后 | 节省 ≥ 30% token |

### 2.2 双格式返回测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_compressed_content` | 压缩内容 | exec 返回 content | TOON 格式字符串 |
| `test_structured_content` | 原始内容 | exec 返回 structured_content | 原始 JSON |
| `test_both_present` | 双格式同时存在 | 检查返回对象 | 两者都存在 |

## 3. 健康检查测试

### 3.1 健康检查器测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_health_check_start` | 启动健康检查 | 调用 start() | 后台任务启动 |
| `test_health_check_stop` | 停止健康检查 | 调用 stop() | 后台任务停止 |
| `test_check_server` | 检查单个服务器 | 调用 check_server() | 返回健康状态 |
| `test_consecutive_failures` | 连续失败计数 | 多次失败 | consecutive_failures 递增 |
| `test_failure_threshold` | 失败阈值 | 达到阈值 | 标记为 unhealthy |

### 3.2 Registry 集成测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_registry_health_integration` | Registry 集成 | 初始化时启用健康检查 | 健康检查器启动 |
| `test_get_server_health` | 获取服务器健康 | 调用 get_server_health() | 返回健康信息 |
| `test_reconnect_unhealthy` | 重连不健康服务器 | 调用 reconnect_server() | 重新建立连接 |

## 4. 多模态内容测试

### 4.1 内容类型检测

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_is_text_content` | 检测 TextContent | 传入 TextContent | 返回 True |
| `test_is_image_content` | 检测 ImageContent | 传入 ImageContent | 返回 True |
| `test_is_resource_content` | 检测 EmbeddedResource | 传入 EmbeddedResource | 返回 True |
| `test_detect_content_type` | 检测内容类型 | 调用 detect_content_type() | 返回正确类型 |

### 4.2 内容提取测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_extract_text_content` | 提取文本内容 | 单项 TextContent | 返回 text 字段 |
| `test_extract_image_content` | 提取图片内容 | 单项 ImageContent | 返回原始对象 |
| `test_extract_resource_content` | 提取资源内容 | 单项 EmbeddedResource | 返回原始对象 |
| `test_extract_mixed_content` | 提取混合内容 | 多项内容列表 | 返回原始列表 |
| `test_extract_json_text` | 提取 JSON 文本 | TextContent 包含 JSON | 解析为 JSON 对象 |

### 4.3 透传测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_passthrough_image` | 图片透传 | exec 返回 ImageContent | 直接返回，不压缩 |
| `test_passthrough_resource` | 资源透传 | exec 返回 EmbeddedResource | 直接返回，不压缩 |
| `test_passthrough_list` | 列表透传 | exec 返回列表 | 直接返回，不压缩 |
| `test_json_still_compressed` | JSON 仍压缩 | exec 返回纯 JSON | 应用 TOON 压缩 |

## 5. 配置测试

### 5.1 配置类测试

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_proxy_config_defaults` | 默认配置 | 不传可选参数 | 使用默认值 |
| `test_proxy_config_full` | 完整配置 | 传入所有参数 | 正确解析 |
| `test_server_config_types` | 服务器配置类型 | stdio 和 http | 正确识别 |

## 6. E2E 测试

### 6.1 完整流程

| 测试用例 | 描述 | 测试步骤 | 预期结果 |
|---------|------|----------|----------|
| `test_exec_with_compression` | 执行并压缩 | exec 调用 | 返回双格式 |
| `test_exec_multimodal` | 执行多模态 | exec 返回图片 | 图片正确透传 |
| `test_health_check_during_exec` | 执行时健康检查 | 健康检查运行 | 不影响执行 |

## 7. 验收标准

所有测试用例通过，且：
- TOON 压缩节省 ≥ 30% token
- 健康检查正确探测服务器状态
- 多模态内容正确透传
- 测试覆盖率 ≥ 70%
