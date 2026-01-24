"""Tests for JSON Schema to TypeScript conversion."""

from __future__ import annotations

from mcpx.schema_ts import SchemaConverter, json_schema_to_typescript


class TestBasicTypes:
    """Tests for basic type conversions."""

    def test_string_type(self):
        """Test: string type converts correctly."""
        schema = {"type": "string"}
        assert json_schema_to_typescript(schema) == "string"

    def test_number_type(self):
        """Test: number type converts correctly."""
        schema = {"type": "number"}
        assert json_schema_to_typescript(schema) == "number"

    def test_integer_type(self):
        """Test: integer type converts to number."""
        schema = {"type": "integer"}
        assert json_schema_to_typescript(schema) == "number"

    def test_boolean_type(self):
        """Test: boolean type converts correctly."""
        schema = {"type": "boolean"}
        assert json_schema_to_typescript(schema) == "boolean"

    def test_null_type(self):
        """Test: null type converts correctly."""
        schema = {"type": "null"}
        assert json_schema_to_typescript(schema) == "null"

    def test_empty_schema(self):
        """Test: empty schema returns unknown."""
        assert json_schema_to_typescript({}) == "unknown"

    def test_unknown_type(self):
        """Test: unknown type returns unknown."""
        schema = {"type": "custom"}
        assert json_schema_to_typescript(schema) == "unknown"


class TestArrayTypes:
    """Tests for array type conversions."""

    def test_array_of_strings(self):
        """Test: array of strings."""
        schema = {"type": "array", "items": {"type": "string"}}
        assert json_schema_to_typescript(schema) == "string[]"

    def test_array_of_numbers(self):
        """Test: array of numbers."""
        schema = {"type": "array", "items": {"type": "number"}}
        assert json_schema_to_typescript(schema) == "number[]"

    def test_array_without_items(self):
        """Test: array without items specification."""
        schema = {"type": "array"}
        assert json_schema_to_typescript(schema) == "unknown[]"

    def test_array_of_objects(self):
        """Test: array of objects."""
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "number"}},
                "required": ["id"],
            },
        }
        result = json_schema_to_typescript(schema)
        assert result == "{id: number}[]"

    def test_array_of_union_types(self):
        """Test: array with union item types gets parentheses."""
        schema = {
            "type": "array",
            "items": {"anyOf": [{"type": "string"}, {"type": "number"}]},
        }
        result = json_schema_to_typescript(schema)
        assert result == "(string | number)[]"


class TestObjectTypes:
    """Tests for object type conversions."""

    def test_simple_object(self):
        """Test: simple object with required field."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        result = json_schema_to_typescript(schema)
        assert result == "{name: string}"

    def test_object_with_optional_field(self):
        """Test: object with optional field."""
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "encoding": {"type": "string"},
            },
            "required": ["path"],
        }
        result = json_schema_to_typescript(schema)
        assert "path: string" in result
        assert "encoding?: string" in result

    def test_object_all_optional(self):
        """Test: object with all optional fields."""
        schema = {
            "type": "object",
            "properties": {
                "a": {"type": "string"},
                "b": {"type": "number"},
            },
        }
        result = json_schema_to_typescript(schema)
        assert "a?: string" in result
        assert "b?: number" in result

    def test_empty_object(self):
        """Test: empty object."""
        schema = {"type": "object", "properties": {}}
        assert json_schema_to_typescript(schema) == "{}"

    def test_object_with_additional_properties_true(self):
        """Test: object with additionalProperties: true."""
        schema = {"type": "object", "additionalProperties": True}
        assert json_schema_to_typescript(schema) == "Record<string, unknown>"

    def test_object_with_typed_additional_properties(self):
        """Test: object with typed additionalProperties."""
        schema = {
            "type": "object",
            "additionalProperties": {"type": "string"},
        }
        assert json_schema_to_typescript(schema) == "Record<string, string>"

    def test_nested_object(self):
        """Test: nested object structure."""
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                }
            },
            "required": ["user"],
        }
        result = json_schema_to_typescript(schema)
        assert result == "{user: {name: string}}"


class TestDescriptions:
    """Tests for description handling."""

    def test_field_with_description(self):
        """Test: field description is included as comment."""
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
            },
            "required": ["path"],
        }
        result = json_schema_to_typescript(schema)
        assert "/* File path */" in result

    def test_long_description_truncated(self):
        """Test: long descriptions are truncated."""
        long_desc = "A" * 100
        schema = {
            "type": "object",
            "properties": {
                "field": {"type": "string", "description": long_desc},
            },
        }
        result = json_schema_to_typescript(schema, max_description_len=50)
        assert "..." in result
        assert len(result) < len(long_desc) + 50  # Much shorter than original

    def test_descriptions_disabled(self):
        """Test: descriptions can be disabled."""
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
            },
        }
        result = json_schema_to_typescript(schema, include_descriptions=False)
        assert "/*" not in result
        assert "File path" not in result


class TestUnionTypes:
    """Tests for union type conversions."""

    def test_anyof_union(self):
        """Test: anyOf creates union type."""
        schema = {"anyOf": [{"type": "string"}, {"type": "number"}]}
        result = json_schema_to_typescript(schema)
        assert result == "string | number"

    def test_oneof_union(self):
        """Test: oneOf creates union type."""
        schema = {"oneOf": [{"type": "boolean"}, {"type": "null"}]}
        result = json_schema_to_typescript(schema)
        assert result == "boolean | null"

    def test_type_array_as_union(self):
        """Test: type as array creates union."""
        schema = {"type": ["string", "null"]}
        result = json_schema_to_typescript(schema)
        assert result == "string | null"

    def test_allof_uses_first(self):
        """Test: allOf uses first type (simplified)."""
        schema = {"allOf": [{"type": "string"}, {"minLength": 1}]}
        result = json_schema_to_typescript(schema)
        assert result == "string"


class TestEnumTypes:
    """Tests for enum type conversions."""

    def test_string_enum(self):
        """Test: string enum becomes union of literals."""
        schema = {"enum": ["read", "write", "delete"]}
        result = json_schema_to_typescript(schema)
        assert result == '"read" | "write" | "delete"'

    def test_mixed_enum(self):
        """Test: mixed enum with different types."""
        schema = {"enum": ["auto", 0, 1, True]}
        result = json_schema_to_typescript(schema)
        assert '"auto"' in result
        assert "0" in result
        assert "1" in result
        assert "true" in result

    def test_const_value(self):
        """Test: const value becomes literal."""
        schema = {"const": "fixed"}
        result = json_schema_to_typescript(schema)
        assert result == '"fixed"'


class TestRefResolution:
    """Tests for $ref resolution."""

    def test_ref_to_defs(self):
        """Test: $ref to $defs is resolved."""
        schema = {
            "$defs": {
                "Address": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                }
            },
            "type": "object",
            "properties": {"address": {"$ref": "#/$defs/Address"}},
            "required": ["address"],
        }
        result = json_schema_to_typescript(schema)
        assert "{city: string}" in result

    def test_ref_to_definitions(self):
        """Test: $ref to definitions is resolved."""
        schema = {
            "definitions": {
                "Name": {"type": "string"},
            },
            "type": "object",
            "properties": {"name": {"$ref": "#/definitions/Name"}},
            "required": ["name"],
        }
        result = json_schema_to_typescript(schema)
        assert "name: string" in result

    def test_unresolved_ref(self):
        """Test: unresolved $ref returns type name."""
        schema = {"$ref": "#/definitions/Unknown"}
        result = json_schema_to_typescript(schema)
        assert result == "Unknown"


class TestRealWorldSchemas:
    """Tests with real MCP tool schemas."""

    def test_filesystem_read_file(self):
        """Test: filesystem read_file schema."""
        schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read",
                },
            },
            "required": ["path"],
        }
        result = json_schema_to_typescript(schema)
        assert "path: string" in result
        assert "/* Path to the file to read */" in result

    def test_search_tool_schema(self):
        """Test: search tool with optional parameters."""
        schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results"},
                "offset": {"type": "integer"},
            },
            "required": ["query"],
        }
        result = json_schema_to_typescript(schema)
        assert "query: string" in result
        assert "limit?: number" in result
        assert "offset?: number" in result

    def test_complex_tool_schema(self):
        """Test: complex tool with nested types."""
        schema = {
            "type": "object",
            "properties": {
                "action": {"enum": ["create", "update", "delete"]},
                "data": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id"],
                },
            },
            "required": ["action", "data"],
        }
        result = json_schema_to_typescript(schema)
        assert '"create" | "update" | "delete"' in result
        assert "string[]" in result
        assert "id: string" in result
        assert "tags?: string[]" in result


class TestSchemaConverterClass:
    """Tests for SchemaConverter class directly."""

    def test_converter_instance_reuse(self):
        """Test: converter can be reused."""
        converter = SchemaConverter()
        result1 = converter.convert({"type": "string"})
        result2 = converter.convert({"type": "number"})
        assert result1 == "string"
        assert result2 == "number"

    def test_converter_custom_settings(self):
        """Test: converter respects custom settings."""
        converter = SchemaConverter(include_descriptions=False, max_description_len=20)
        schema = {
            "type": "object",
            "properties": {
                "field": {"type": "string", "description": "Long description here"},
            },
        }
        result = converter.convert(schema)
        assert "/*" not in result


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_none_schema(self):
        """Test: None-like schema handling."""
        # Empty dict
        assert json_schema_to_typescript({}) == "unknown"

    def test_non_dict_input(self):
        """Test: non-dict input returns unknown."""
        converter = SchemaConverter()
        assert converter._convert_type("not a dict") == "unknown"  # type: ignore
        assert converter._convert_type(123) == "unknown"  # type: ignore
        assert converter._convert_type(None) == "unknown"  # type: ignore

    def test_infer_object_from_properties(self):
        """Test: object inferred from properties without type."""
        schema = {
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        result = json_schema_to_typescript(schema)
        assert "name: string" in result

    def test_infer_array_from_items(self):
        """Test: array inferred from items without type."""
        schema = {"items": {"type": "number"}}
        result = json_schema_to_typescript(schema)
        assert result == "number[]"

    def test_string_with_special_chars(self):
        """Test: string enum with special characters."""
        schema = {"enum": ['with "quotes"', "with\\backslash"]}
        result = json_schema_to_typescript(schema)
        assert '\\"' in result or "quotes" in result  # Escaped quotes

    def test_empty_allof(self):
        """Test: empty allOf returns unknown."""
        schema = {"allOf": []}
        assert json_schema_to_typescript(schema) == "unknown"

    def test_duplicate_union_types_deduplicated(self):
        """Test: duplicate types in union are deduplicated."""
        schema = {"anyOf": [{"type": "string"}, {"type": "string"}, {"type": "number"}]}
        result = json_schema_to_typescript(schema)
        # Should not have duplicate "string"
        assert result.count("string") == 1


class TestTokenSavings:
    """Tests to verify token savings."""

    def test_significant_token_reduction(self):
        """Test: TypeScript format is significantly shorter than JSON."""
        import json as json_module

        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "encoding": {"type": "string", "default": "utf-8"},
                "offset": {"type": "integer"},
                "limit": {"type": "integer"},
            },
            "required": ["path"],
        }

        json_output = json_module.dumps(schema)
        ts_output = json_schema_to_typescript(schema)

        # TypeScript should be at least 50% shorter
        assert len(ts_output) < len(json_output) * 0.5

    def test_complex_schema_token_reduction(self):
        """Test: complex schema still achieves good reduction."""
        import json as json_module

        schema = {
            "type": "object",
            "properties": {
                "action": {"enum": ["create", "read", "update", "delete"]},
                "resource": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id"],
                },
                "options": {
                    "type": "object",
                    "properties": {
                        "timeout": {"type": "integer"},
                        "retry": {"type": "boolean"},
                    },
                },
            },
            "required": ["action", "resource"],
        }

        json_output = json_module.dumps(schema)
        ts_output = json_schema_to_typescript(schema)

        # Should still achieve significant reduction
        assert len(ts_output) < len(json_output) * 0.6
