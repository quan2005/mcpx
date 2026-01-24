"""JSON Schema to TypeScript type conversion for token-efficient schema representation.

Converts verbose JSON Schema definitions to compact TypeScript type syntax,
reducing token usage by ~60-70% while maintaining LLM comprehension.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["json_schema_to_typescript", "SchemaConverter"]


class SchemaConverter:
    """Converts JSON Schema to TypeScript type definitions.

    Supports:
    - Basic types: string, number, boolean, null
    - Arrays with typed items
    - Objects with properties (required/optional)
    - Union types (anyOf/oneOf)
    - Enum literals
    - Nested structures
    - $ref resolution (within same schema)
    """

    def __init__(self, include_descriptions: bool = True, max_description_len: int = 50) -> None:
        """Initialize converter.

        Args:
            include_descriptions: Whether to include field descriptions as comments
            max_description_len: Maximum length for inline description comments
        """
        self.include_descriptions = include_descriptions
        self.max_description_len = max_description_len
        self._definitions: dict[str, Any] = {}

    def convert(self, schema: dict[str, Any]) -> str:
        """Convert JSON Schema to TypeScript type definition.

        Args:
            schema: JSON Schema dictionary

        Returns:
            TypeScript type definition string
        """
        if not schema:
            return "unknown"

        # Store definitions for $ref resolution
        if "$defs" in schema:
            self._definitions = schema["$defs"]
        elif "definitions" in schema:
            self._definitions = schema["definitions"]

        try:
            return self._convert_type(schema)
        except Exception as e:
            logger.warning(f"Schema conversion failed: {e}")
            return "unknown"

    def _convert_type(self, schema: dict[str, Any], required: bool = True) -> str:
        """Convert a schema type to TypeScript.

        Args:
            schema: Schema to convert
            required: Whether this field is required (affects output for objects)

        Returns:
            TypeScript type string
        """
        if not isinstance(schema, dict):
            return "unknown"

        # Handle $ref
        if "$ref" in schema:
            return self._resolve_ref(schema["$ref"])

        # Handle enum
        if "enum" in schema:
            return self._convert_enum(schema["enum"])

        # Handle const
        if "const" in schema:
            return self._format_literal(schema["const"])

        # Handle anyOf/oneOf (union types)
        if "anyOf" in schema:
            return self._convert_union(schema["anyOf"])
        if "oneOf" in schema:
            return self._convert_union(schema["oneOf"])

        # Handle allOf (intersection - simplified to first type)
        if "allOf" in schema:
            if schema["allOf"]:
                return self._convert_type(schema["allOf"][0])
            return "unknown"

        # Get type
        schema_type = schema.get("type")

        # Handle array of types (e.g., ["string", "null"])
        if isinstance(schema_type, list):
            types = [self._convert_simple_type(t, schema) for t in schema_type]
            return " | ".join(types)

        # Handle simple types
        if schema_type == "string":
            return "string"
        if schema_type in ("number", "integer"):
            return "number"
        if schema_type == "boolean":
            return "boolean"
        if schema_type == "null":
            return "null"

        # Handle array
        if schema_type == "array":
            return self._convert_array(schema)

        # Handle object
        if schema_type == "object":
            return self._convert_object(schema)

        # No type specified - try to infer
        if "properties" in schema:
            return self._convert_object(schema)
        if "items" in schema:
            return self._convert_array(schema)

        return "unknown"

    def _convert_simple_type(self, type_name: str, schema: dict[str, Any]) -> str:
        """Convert a simple type name to TypeScript."""
        if type_name == "string":
            return "string"
        if type_name in ("number", "integer"):
            return "number"
        if type_name == "boolean":
            return "boolean"
        if type_name == "null":
            return "null"
        if type_name == "array":
            return self._convert_array(schema)
        if type_name == "object":
            return self._convert_object(schema)
        return "unknown"

    def _convert_array(self, schema: dict[str, Any]) -> str:
        """Convert array schema to TypeScript array type."""
        items = schema.get("items")
        if items:
            item_type = self._convert_type(items)
            # Wrap union types in parentheses for clarity
            if " | " in item_type:
                return f"({item_type})[]"
            return f"{item_type}[]"
        return "unknown[]"

    def _convert_object(self, schema: dict[str, Any]) -> str:
        """Convert object schema to TypeScript object type."""
        properties = schema.get("properties", {})
        required_fields = set(schema.get("required", []))

        if not properties:
            # Empty object or additionalProperties only
            additional = schema.get("additionalProperties")
            if additional is True:
                return "Record<string, unknown>"
            if isinstance(additional, dict):
                value_type = self._convert_type(additional)
                return f"Record<string, {value_type}>"
            return "{}"

        fields = []
        for name, prop_schema in properties.items():
            is_required = name in required_fields
            field_type = self._convert_type(prop_schema)

            # Format field with optional marker
            optional_marker = "" if is_required else "?"
            field_str = f"{name}{optional_marker}: {field_type}"

            # Add description comment if enabled and present
            if self.include_descriptions and isinstance(prop_schema, dict):
                desc = prop_schema.get("description", "")
                if desc:
                    if len(desc) > self.max_description_len:
                        desc = desc[: self.max_description_len - 3] + "..."
                    field_str += f" /* {desc} */"

            fields.append(field_str)

        return "{" + "; ".join(fields) + "}"

    def _convert_union(self, schemas: list[dict[str, Any]]) -> str:
        """Convert anyOf/oneOf to TypeScript union type."""
        types = []
        for s in schemas:
            t = self._convert_type(s)
            if t not in types:  # Deduplicate
                types.append(t)
        return " | ".join(types)

    def _convert_enum(self, values: list[Any]) -> str:
        """Convert enum values to TypeScript union of literals."""
        literals = [self._format_literal(v) for v in values]
        return " | ".join(literals)

    def _format_literal(self, value: Any) -> str:
        """Format a literal value for TypeScript."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            # Escape quotes in string
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        if isinstance(value, (int, float)):
            return str(value)
        return "unknown"

    def _resolve_ref(self, ref: str) -> str:
        """Resolve a $ref reference."""
        # Handle local references like "#/$defs/MyType" or "#/definitions/MyType"
        if ref.startswith("#/"):
            parts = ref[2:].split("/")
            if len(parts) >= 2 and parts[0] in ("$defs", "definitions"):
                def_name = parts[1]
                if def_name in self._definitions:
                    return self._convert_type(self._definitions[def_name])
        # Could not resolve - return the reference name
        return ref.split("/")[-1] if "/" in ref else ref


def json_schema_to_typescript(
    schema: dict[str, Any],
    include_descriptions: bool = True,
    max_description_len: int = 50,
) -> str:
    """Convert JSON Schema to TypeScript type definition.

    This is a convenience function that creates a SchemaConverter and converts
    the given schema.

    Args:
        schema: JSON Schema dictionary
        include_descriptions: Whether to include field descriptions as comments
        max_description_len: Maximum length for inline description comments

    Returns:
        TypeScript type definition string

    Examples:
        >>> schema = {
        ...     "type": "object",
        ...     "properties": {
        ...         "path": {"type": "string", "description": "File path"},
        ...         "encoding": {"type": "string"}
        ...     },
        ...     "required": ["path"]
        ... }
        >>> json_schema_to_typescript(schema)
        '{path: string /* File path */; encoding?: string}'
    """
    converter = SchemaConverter(
        include_descriptions=include_descriptions,
        max_description_len=max_description_len,
    )
    return converter.convert(schema)
