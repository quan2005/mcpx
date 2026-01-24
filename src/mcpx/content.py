"""多模态内容类型检测工具。

支持检测 MCP 协议的多模态内容类型（TextContent、ImageContent、EmbeddedResource）。
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ContentType",
    "is_multimodal_content",
    "detect_content_type",
]


class ContentType:
    """内容类型枚举。"""

    TEXT = "text"
    IMAGE = "image"
    RESOURCE = "resource"
    JSON = "json"
    MIXED = "mixed"
    UNKNOWN = "unknown"


def is_multimodal_content(obj: Any) -> bool:
    """检测对象是否为 MCP 多模态内容类型。

    Args:
        obj: 待检测对象

    Returns:
        True 如果是 TextContent/ImageContent/EmbeddedResource
    """
    # 延迟导入避免循环依赖
    try:
        from mcp.types import EmbeddedResource, ImageContent, TextContent

        return isinstance(obj, (TextContent, ImageContent, EmbeddedResource))
    except ImportError:
        return False


def detect_content_type(obj: Any) -> str:
    """检测内容类型。

    Args:
        obj: 待检测对象

    Returns:
        ContentType 枚举值
    """
    if not is_multimodal_content(obj):
        if isinstance(obj, (dict, list, str, int, float, bool)) or obj is None:
            return ContentType.JSON
        return ContentType.UNKNOWN

    # 检查具体类型 - 通过类型名称判断
    type_name = type(obj).__name__
    if "Image" in type_name:
        return ContentType.IMAGE
    if "Text" in type_name:
        return ContentType.TEXT
    if "Resource" in type_name or "Embedded" in type_name:
        return ContentType.RESOURCE

    return ContentType.MIXED
