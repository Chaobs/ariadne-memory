"""
MCP Parameter Schema Validation for Ariadne.

Provides JSON Schema-based parameter validation for MCP tools:
- Required field checking
- Type validation
- Enum validation
- Range constraints (min/max)
- Pattern matching (regex)
- Custom validators

Inspired by MemPalace's parameter schema validation.
"""

from __future__ import annotations

import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Validation error with details."""

    def __init__(self, message: str, errors: List[Dict[str, Any]] = None):
        super().__init__(message)
        self.errors = errors or []


@dataclass
class FieldError:
    """Error for a specific field."""
    path: str  # JSON path to the field, e.g., "params.query"
    message: str
    code: str  # Error code, e.g., "required", "type_error"
    value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "message": self.message,
            "code": self.code,
            "value": self.value,
        }


class SchemaValidator:
    """
    JSON Schema-inspired parameter validator.

    Supports a subset of JSON Schema draft-07 for MCP tool parameters.

    Supported keywords:
    - type: string, number, integer, boolean, array, object
    - required: list of required field names
    - properties: field definitions
    - enum: allowed values
    - minimum, maximum: for numbers
    - minLength, maxLength: for strings
    - pattern: regex pattern for strings
    - items: schema for array items
    - minItems, maxItems: for arrays
    - default: default value (not validated)

    Usage:
        validator = SchemaValidator(schema)
        errors = validator.validate({"query": "test", "limit": 5})
        if errors:
            print(f"Validation failed: {errors}")
    """

    # Type mapping from JSON Schema types
    TYPE_MAP = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }

    def __init__(self, schema: Dict[str, Any]):
        """
        Initialize validator with a schema.

        Args:
            schema: JSON Schema-like definition
        """
        self.schema = schema
        self.errors: List[FieldError] = []

    def validate(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Validate parameters against schema.

        Args:
            params: Parameters to validate

        Returns:
            List of validation errors (empty if valid)
        """
        self.errors = []

        # Handle root-level type
        if "type" in self.schema:
            self._validate_type("params", params, self.schema["type"])

        # Handle properties
        if "properties" in self.schema:
            self._validate_properties("params", params, self.schema)

        # Handle required fields
        if "required" in self.schema:
            self._validate_required("params", params, self.schema["required"])

        return [e.to_dict() for e in self.errors]

    def _validate_type(
        self,
        path: str,
        value: Any,
        expected_type: Union[str, List[str]],
    ) -> None:
        """Validate value type."""
        if value is None:
            return  # None is valid for optional fields

        types = expected_type if isinstance(expected_type, list) else [expected_type]

        for t in types:
            if t in self.TYPE_MAP:
                expected_python_type = self.TYPE_MAP[t]
                if isinstance(value, expected_python_type):
                    return
            elif t == "null" and value is None:
                return

        type_names = ", ".join(types)
        self.errors.append(FieldError(
            path=path,
            message=f"Expected type {type_names}, got {type(value).__name__}",
            code="type_error",
            value=value,
        ))

    def _validate_properties(
        self,
        path: str,
        params: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> None:
        """Validate object properties."""
        if not isinstance(params, dict):
            return

        for field_name, field_schema in schema["properties"].items():
            field_path = f"{path}.{field_name}"
            field_value = params.get(field_name)

            # Skip if not present and no default
            if field_value is None and "default" not in field_schema:
                continue

            # Apply default if not provided
            if field_name not in params and "default" in field_schema:
                continue  # Default will be applied by caller

            # Validate type
            if "type" in field_schema:
                self._validate_type(field_path, field_value, field_schema["type"])

            # Skip further validation if type check failed
            if field_value is None:
                continue

            # Validate enum
            if "enum" in field_schema:
                self._validate_enum(field_path, field_value, field_schema["enum"])

            # Validate string constraints
            if "minLength" in field_schema:
                self._validate_min_length(field_path, field_value, field_schema["minLength"])
            if "maxLength" in field_schema:
                self._validate_max_length(field_path, field_value, field_schema["maxLength"])
            if "pattern" in field_schema:
                self._validate_pattern(field_path, field_value, field_schema["pattern"])

            # Validate number constraints
            if "minimum" in field_schema:
                self._validate_minimum(field_path, field_value, field_schema["minimum"])
            if "maximum" in field_schema:
                self._validate_maximum(field_path, field_value, field_schema["maximum"])

            # Validate array constraints
            if "minItems" in field_schema:
                self._validate_min_items(field_path, field_value, field_schema["minItems"])
            if "maxItems" in field_schema:
                self._validate_max_items(field_path, field_value, field_schema["maxItems"])

            # Validate nested items (for arrays)
            if "items" in field_schema and isinstance(field_value, list):
                self._validate_items(field_path, field_value, field_schema["items"])

    def _validate_required(
        self,
        path: str,
        params: Dict[str, Any],
        required: List[str],
    ) -> None:
        """Validate required fields."""
        if not isinstance(params, dict):
            return

        for field_name in required:
            if field_name not in params or params[field_name] is None:
                # Check if field has a default
                default = None
                if "properties" in self.schema:
                    default = self.schema["properties"].get(field_name, {}).get("default")

                if default is None:
                    self.errors.append(FieldError(
                        path=f"{path}.{field_name}",
                        message=f"Required field '{field_name}' is missing",
                        code="required",
                    ))

    def _validate_enum(
        self,
        path: str,
        value: Any,
        enum_values: List[Any],
    ) -> None:
        """Validate enum values."""
        if value not in enum_values:
            self.errors.append(FieldError(
                path=path,
                message=f"Value must be one of {enum_values}, got {value!r}",
                code="enum",
                value=value,
            ))

    def _validate_min_length(
        self,
        path: str,
        value: Any,
        min_length: int,
    ) -> None:
        """Validate string minimum length."""
        if not isinstance(value, str):
            return
        if len(value) < min_length:
            self.errors.append(FieldError(
                path=path,
                message=f"String length must be at least {min_length}, got {len(value)}",
                code="min_length",
                value=value,
            ))

    def _validate_max_length(
        self,
        path: str,
        value: Any,
        max_length: int,
    ) -> None:
        """Validate string maximum length."""
        if not isinstance(value, str):
            return
        if len(value) > max_length:
            self.errors.append(FieldError(
                path=path,
                message=f"String length must be at most {max_length}, got {len(value)}",
                code="max_length",
                value=value,
            ))

    def _validate_pattern(
        self,
        path: str,
        value: Any,
        pattern: str,
    ) -> None:
        """Validate string against regex pattern."""
        if not isinstance(value, str):
            return
        try:
            if not re.match(pattern, value):
                self.errors.append(FieldError(
                    path=path,
                    message=f"String does not match pattern {pattern!r}",
                    code="pattern",
                    value=value,
                ))
        except re.error as e:
            logger.warning(f"Invalid regex pattern {pattern}: {e}")

    def _validate_minimum(
        self,
        path: str,
        value: Any,
        minimum: Union[int, float],
    ) -> None:
        """Validate numeric minimum."""
        if not isinstance(value, (int, float)):
            return
        if value < minimum:
            self.errors.append(FieldError(
                path=path,
                message=f"Value must be at least {minimum}, got {value}",
                code="minimum",
                value=value,
            ))

    def _validate_maximum(
        self,
        path: str,
        value: Any,
        maximum: Union[int, float],
    ) -> None:
        """Validate numeric maximum."""
        if not isinstance(value, (int, float)):
            return
        if value > maximum:
            self.errors.append(FieldError(
                path=path,
                message=f"Value must be at most {maximum}, got {value}",
                code="maximum",
                value=value,
            ))

    def _validate_min_items(
        self,
        path: str,
        value: Any,
        min_items: int,
    ) -> None:
        """Validate array minimum items."""
        if not isinstance(value, list):
            return
        if len(value) < min_items:
            self.errors.append(FieldError(
                path=path,
                message=f"Array must have at least {min_items} items, got {len(value)}",
                code="min_items",
                value=value,
            ))

    def _validate_max_items(
        self,
        path: str,
        value: Any,
        max_items: int,
    ) -> None:
        """Validate array maximum items."""
        if not isinstance(value, list):
            return
        if len(value) > max_items:
            self.errors.append(FieldError(
                path=path,
                message=f"Array must have at most {max_items} items, got {len(value)}",
                code="max_items",
                value=value,
            ))

    def _validate_items(
        self,
        path: str,
        items: List[Any],
        item_schema: Dict[str, Any],
    ) -> None:
        """Validate array items against schema."""
        for i, item in enumerate(items):
            item_path = f"{path}[{i}]"
            if "type" in item_schema:
                self._validate_type(item_path, item, item_schema["type"])
            if "enum" in item_schema:
                self._validate_enum(item_path, item, item_schema["enum"])


class ValidatedTool:
    """
    A tool wrapper that validates parameters before execution.

    Usage:
        def search_handler(query: str, limit: int = 5) -> dict:
            return do_search(query, limit)

        tool = ValidatedTool(
            name="ariadne_search",
            handler=search_handler,
            schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": ["query"],
            },
        )

        # Automatic validation on call
        result = tool.execute({"query": "test", "limit": 10})
    """

    def __init__(
        self,
        name: str,
        handler: Callable,
        schema: Dict[str, Any],
        description: str = "",
    ):
        """
        Initialize validated tool.

        Args:
            name: Tool name
            handler: Function to call with validated params
            schema: JSON Schema for parameters
            description: Tool description
        """
        self.name = name
        self.handler = handler
        self.schema = schema
        self.description = description
        self.validator = SchemaValidator(schema)

    def validate(self, params: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Validate parameters.

        Args:
            params: Parameters to validate

        Returns:
            Tuple of (is_valid, errors)
        """
        # Apply defaults
        params = self._apply_defaults(params)

        errors = self.validator.validate(params)
        return len(errors) == 0, errors

    def _apply_defaults(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default values to missing parameters."""
        if "properties" not in self.schema:
            return params

        result = dict(params)
        for field_name, field_schema in self.schema["properties"].items():
            if field_name not in result and "default" in field_schema:
                result[field_name] = field_schema["default"]

        return result

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute tool with parameter validation.

        Args:
            params: Parameters to validate and pass to handler

        Returns:
            Result dictionary with 'success' and either 'result' or 'errors'
        """
        # Apply defaults
        params = self._apply_defaults(params)

        # Validate
        is_valid, errors = self.validate(params)
        if not is_valid:
            return {
                "success": False,
                "error": f"Validation failed: {len(errors)} error(s)",
                "errors": errors,
            }

        # Execute
        try:
            result = self.handler(**params)
            return {
                "success": True,
                "result": result,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "errors": [],
            }


def validate_tool_schema(schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validate a tool schema itself (meta-validation).

    Useful for detecting schema definition errors.

    Args:
        schema: Schema to validate

    Returns:
        List of errors (empty if valid)
    """
    errors = []

    # Check for valid type
    if "type" in schema:
        valid_types = {"object", "string", "number", "integer", "boolean", "array", "null"}
        if schema["type"] not in valid_types:
            errors.append({
                "path": "type",
                "message": f"Invalid type: {schema['type']}",
                "code": "invalid_schema",
            })

    # Check properties structure
    if "properties" in schema:
        if not isinstance(schema["properties"], dict):
            errors.append({
                "path": "properties",
                "message": "Properties must be an object",
                "code": "invalid_schema",
            })
        else:
            for name, prop in schema["properties"].items():
                if not isinstance(prop, dict):
                    errors.append({
                        "path": f"properties.{name}",
                        "message": "Property schema must be an object",
                        "code": "invalid_schema",
                    })

    # Check required is array
    if "required" in schema:
        if not isinstance(schema["required"], list):
            errors.append({
                "path": "required",
                "message": "Required must be an array",
                "code": "invalid_schema",
            })
        elif "properties" in schema:
            for field in schema["required"]:
                if field not in schema["properties"]:
                    errors.append({
                        "path": f"required.{field}",
                        "message": f"Required field '{field}' not defined in properties",
                        "code": "invalid_schema",
                    })

    # Check enum values
    if "enum" in schema:
        if not isinstance(schema["enum"], list):
            errors.append({
                "path": "enum",
                "message": "Enum must be an array",
                "code": "invalid_schema",
            })

    return errors
