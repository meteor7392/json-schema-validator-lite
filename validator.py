from typing import Any, Dict, List, Tuple, Union

class SchemaValidationError(Exception):
    """Custom exception for schema validation errors."""
    pass

class SchemaValidator:
    """
    Validates dictionaries against a simplified schema.
    Supported types: 'string', 'integer', 'float', 'boolean', 'list', 'dict'
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
            # Simple type validation
            expected_type = self.TYPE_MAP.get(schema)
            if expected_type is None:
                errors.append(f"Invalid schema type '{schema}' at {path}")
                return
            
            if not isinstance(data, expected_type):
                # Handle float/int coercion if desired, but here we keep it strict
                errors.append(f"Expected {schema} at {path}, got {type(data).__name__}")
        
        elif isinstance(schema, dict):
            # Object validation
            if not isinstance(data, dict):
                errors.append(f"Expected dict at {path}, got {type(data).__name__}")
                return
            
            for key, value in schema.items():
                current_path = f"{path}.{key}"
                if key not in data:
                    errors.append(f"Missing required field: {current_path}")
                else:
                    self._validate_recursive(value, data[key], current_path, errors)
        
        else:
            errors.append(f"Unsupported schema definition at {path}")