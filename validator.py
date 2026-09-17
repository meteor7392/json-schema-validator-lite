from typing import Any, Dict, List, Tuple, Union

class SchemaValidationError(Exception):
    """Custom exception for schema validation errors."""
    pass

class SchemaValidator:
    """
    Validates dictionaries against a simplified schema.
    Supported types: 'string', 'integer', 'float', 'boolean', 'list', 'dict'
    Optional fields can be defined by wrapping the schema in {'optional': ...}
    Numeric constraints can be defined by wrapping the schema in {'type': ..., 'min': ..., 'max': ...}
    """
    
    TYPE_MAP = {
        "string": str,
        "integer": int,
        "float": float,
        "boolean": bool,
        "list": list,
        "dict": dict
    }

    def __init__(self, schema: Dict[str, Any]):
        self.schema = schema

    def validate(self, data: Any) -> Tuple[bool, List[str]]:
        """
        Validates the provided data against the schema.
        Returns a tuple of (is_valid, list_of_errors).
        """
        errors = []
        self._validate_recursive(self.schema, data, "root", errors)
        return len(errors) == 0, errors

    def _validate_recursive(self, schema: Any, data: Any, path: str, errors: List[str]):
        if isinstance(schema, str):
            self._check_type(schema, data, path, errors)
        
        elif isinstance(schema, dict):
            # Check if this is a constraint definition rather than a nested object
            if "type" in schema:
                type_name = schema["type"]
                self._check_type(type_name, data, path, errors)
                
                # Range validation for numbers
                if isinstance(data, (int, float)):
                    if "min" in schema and data < schema["min"]:
                        errors.append(f"Value at {path} is too small (min: {schema['min']})")
                    if "max" in schema and data > schema["max"]:
                        errors.append(f"Value at {path} is too large (max: {schema['max']})")
                return

            # Object validation
            if not isinstance(data, dict):
                errors.append(f"Expected dict at {path}, got {type(data).__name__}")
                return
            
            for key, rules in schema.items():
                current_path = f"{path}.{key}"
                
                # Check for optional flag
                is_optional = False
                actual_rules = rules
                if isinstance(rules, dict) and "optional" in rules:
                    is_optional = True
                    actual_rules = rules["optional"]

                if key not in data:
                    if not is_optional:
                        errors.append(f"Missing required field: {current_path}")
                else:
                    self._validate_recursive(actual_rules, data[key], current_path, errors)
        
        else:
            errors.append(f"Unsupported schema definition at {path}")

    def _check_type(self, type_name: str, data: Any, path: str, errors: List[str]):
        expected_type = self.TYPE_MAP.get(type_name)
        if expected_type is None:
            errors.append(f"Invalid schema type '{type_name}' at {path}")
            return
        
        if not isinstance(data, expected_type):
            errors.append(f"Expected {type_name} at {path}, got {type(data).__name__}")