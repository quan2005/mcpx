"""测试多模态内容类型检测。"""

from __future__ import annotations

import pytest

from mcpx.content import ContentType, detect_content_type, is_multimodal_content


class TestIsMultimodalContent:
    """测试多模态内容检测。"""

    def test_text_content_is_multimodal(self) -> None:
        """测试 TextContent 被识别为多模态内容。"""
        from mcp.types import TextContent

        content = TextContent(type="text", text="hello")
        assert is_multimodal_content(content) is True

    def test_image_content_is_multimodal(self) -> None:
        """测试 ImageContent 被识别为多模态内容。"""
        from mcp.types import ImageContent

        content = ImageContent(type="image", data="aGVsbG8=", mimeType="image/png")
        assert is_multimodal_content(content) is True

    def test_resource_content_is_multimodal(self) -> None:
        """测试 EmbeddedResource 被识别为多模态内容。"""
        from mcp.types import BlobResourceContents, EmbeddedResource

        content = EmbeddedResource(
            type="resource",
            resource=BlobResourceContents(uri="file:///test.txt", mimeType="text/plain", blob=""),
        )
        assert is_multimodal_content(content) is True

    def test_dict_is_not_multimodal(self) -> None:
        """测试字典不被识别为多模态内容。"""
        assert is_multimodal_content({"key": "value"}) is False

    def test_list_is_not_multimodal(self) -> None:
        """测试列表不被识别为多模态内容。"""
        assert is_multimodal_content([1, 2, 3]) is False

    def test_string_is_not_multimodal(self) -> None:
        """测试字符串不被识别为多模态内容。"""
        assert is_multimodal_content("hello") is False

    def test_none_is_not_multimodal(self) -> None:
        """测试 None 不被识别为多模态内容。"""
        assert is_multimodal_content(None) is False


class TestDetectContentType:
    """测试内容类型检测。"""

    def test_detect_text_content(self) -> None:
        """测试检测 TextContent。"""
        from mcp.types import TextContent

        content = TextContent(type="text", text="hello")
        assert detect_content_type(content) == ContentType.TEXT

    def test_detect_image_content(self) -> None:
        """测试检测 ImageContent。"""
        from mcp.types import ImageContent

        content = ImageContent(type="image", data="abc", mimeType="image/png")
        assert detect_content_type(content) == ContentType.IMAGE

    def test_detect_resource_content(self) -> None:
        """测试检测 EmbeddedResource。"""
        from mcp.types import BlobResourceContents, EmbeddedResource

        content = EmbeddedResource(
            type="resource",
            resource=BlobResourceContents(uri="file:///test.txt", mimeType="text/plain", blob=""),
        )
        assert detect_content_type(content) == ContentType.RESOURCE

    def test_detect_json_dict(self) -> None:
        """测试检测 JSON 对象。"""
        assert detect_content_type({"key": "value"}) == ContentType.JSON

    def test_detect_json_list(self) -> None:
        """测试检测 JSON 数组。"""
        assert detect_content_type([1, 2, 3]) == ContentType.JSON

    def test_detect_json_string(self) -> None:
        """测试检测 JSON 字符串。"""
        assert detect_content_type("string") == ContentType.JSON

    def test_detect_json_number(self) -> None:
        """测试检测 JSON 数字。"""
        assert detect_content_type(42) == ContentType.JSON

    def test_detect_json_bool(self) -> None:
        """测试检测 JSON 布尔值。"""
        assert detect_content_type(True) == ContentType.JSON

    def test_detect_json_none(self) -> None:
        """测试检测 JSON null。"""
        assert detect_content_type(None) == ContentType.JSON

    def test_detect_unknown_type(self) -> None:
        """测试检测未知类型。"""
        class CustomType:
            pass

        assert detect_content_type(CustomType()) == ContentType.UNKNOWN


class TestMultimodalWithCompression:
    """测试多模态内容与压缩的交互。"""

    def test_multimodal_not_compressible(self) -> None:
        """测试多模态内容不可压缩。"""
        from mcp.types import ImageContent

        from mcpx.compression import is_compressible

        content = ImageContent(type="image", data="aGVsbG8=", mimeType="image/png")
        assert is_compressible(content) is False

    def test_list_with_multimodal_not_compressible(self) -> None:
        """测试包含多模态内容的列表不可压缩。"""
        from mcp.types import ImageContent, TextContent

        from mcpx.compression import is_compressible

        content_list = [
            TextContent(type="text", text="Analysis:"),
            ImageContent(type="image", data="abc", mimeType="image/png"),
        ]
        assert is_compressible(content_list) is False

    def test_json_list_still_compressible(self) -> None:
        """测试纯 JSON 列表仍然可压缩。"""
        from mcpx.compression import is_compressible

        json_list = [{"a": 1}, {"a": 2}, {"a": 3}]
        assert is_compressible(json_list, min_size=3) is True
