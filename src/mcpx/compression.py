"""TOON format compression for reducing token usage.

TOON (Token-Oriented Object Notation) is a compact format for LLMs.
See: https://github.com/toon-format/toon
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "ToonCompressor",
    "is_compressible",
    "compress_toon",
    "detect_data_type",
]


# Data type classification for compression decisions
DataType = str


def detect_data_type(data: Any) -> DataType:
    """Detect the type of data for compression decision.

    Args:
        data: The data to analyze

    Returns:
        Data type string: "array", "object", "primitive", "mixed", "other"
    """
    if isinstance(data, (str, int, float, bool)) or data is None:
        return "primitive"
    if isinstance(data, list):
        if not data:
            return "array"
        # Check if all elements are objects with same keys
        if all(isinstance(item, dict) for item in data):
            keys_set = [set(item.keys()) for item in data]
            if len(set(frozenset(keys) for keys in keys_set)) == 1:
                return "array"  # Homogeneous array - good for TOON
        return "mixed"
    if isinstance(data, dict):
        return "object"
    return "other"


def is_compressible(data: Any, min_size: int = 3) -> bool:
    """Check if data is suitable for TOON compression.

    TOON works best for:
    - Arrays of objects with consistent structure (e.g., database results)
    - Objects with many keys
    - Nested JSON-like structures

    TOON is less effective for:
    - Simple primitives
    - Deeply nested non-uniform structures
    - Text-heavy content
    - Multimodal content (images, resources)

    Args:
        data: The data to check
        min_size: Minimum number of items/keys to consider compression

    Returns:
        True if data should benefit from TOON compression
    """
    # 多模态内容不压缩
    from mcpx.content import is_multimodal_content

    if is_multimodal_content(data):
        logger.debug("Skipping compression for multimodal content")
        return False

    # 包含多模态内容的列表跳过压缩
    if isinstance(data, list):
        if any(is_multimodal_content(item) for item in data):
            logger.debug("Skipping compression for list containing multimodal content")
            return False

    data_type = detect_data_type(data)

    if data_type == "primitive":
        return False

    if data_type == "array":
        # Check array size
        if isinstance(data, list) and len(data) >= min_size:
            return True
        return False

    if data_type == "object":
        # Check object key count
        if isinstance(data, dict) and len(data) >= min_size:
            return True
        return False

    if data_type == "mixed":
        # Mixed arrays might benefit if large enough
        if isinstance(data, list) and len(data) >= min_size * 2:
            return True
        return False

    return False


class ToonCompressor:
    """Compressor for TOON format.

    Note: Actual TOON encoding requires the 'toon_format' package.
    This implementation provides a fallback and interface.
    """

    def __init__(self, enabled: bool = True, min_size: int = 3) -> None:
        """Initialize TOON compressor.

        Args:
            enabled: Whether compression is enabled
            min_size: Minimum size to trigger compression
        """
        self.enabled = enabled
        self.min_size = min_size
        self._toon_available = self._check_toon_available()

    def _check_toon_available(self) -> bool:
        """Check if toons package is available."""
        try:
            import toons  # noqa: F401

            return True
        except ImportError:
            logger.debug("toons package not available, using fallback")
            return False

    def compress(self, data: Any, min_size: int | None = None) -> tuple[Any, bool]:
        """Compress data if beneficial.

        Args:
            data: The data to potentially compress
            min_size: Override the minimum size for this compression

        Returns:
            Tuple of (compressed_or_original_data, was_compressed)
        """
        if not self.enabled:
            return data, False

        size_threshold = min_size if min_size is not None else self.min_size
        if not is_compressible(data, size_threshold):
            return data, False

        if not self._toon_available:
            # Fallback: return as-is with a note
            logger.debug("TOON compression would be beneficial but package not available")
            return data, False

        try:
            import toons

            # toons.dumps() directly handles Python data structures
            toon_data = toons.dumps(data)
            return toon_data, True
        except Exception as e:
            logger.warning(f"TOON compression failed: {e}")
            return data, False

    def maybe_compress_result(self, result: Any) -> dict[str, Any]:
        """Maybe compress an exec result.

        Args:
            result: The result data from exec

        Returns:
            Dict with compressed data and metadata
        """
        compressed, was_compressed = self.compress(result)

        return {
            "data": compressed,
            "format": "toon" if was_compressed else "json",
            "compressed": was_compressed,
            "original_type": type(result).__name__,
        }


def compress_toon(data: Any, enabled: bool = True, min_size: int = 3) -> Any:
    """Convenience function to compress data with TOON.

    Args:
        data: Data to compress
        enabled: Whether compression is enabled
        min_size: Minimum size to trigger compression

    Returns:
        Compressed data or original if compression not beneficial
    """
    compressor = ToonCompressor(enabled=enabled, min_size=min_size)
    result, _ = compressor.compress(data)
    return result
