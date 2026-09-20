from typing import Any, Dict, List, Tuple, Union
import re

class SchemaValidationError(Exception):
    """Custom exception for schema validation errors."""
    pass

class SchemaValidator:
    """
    Validates dictionaries against a simplified schema.
    Supported types: 'string', 'integer', 'float', 'boolean', 'list', 'dict'
    Optional fields can be defined by wrapping the schema in {'optional': ...}
    Numeric constraints can be defined by wrapping the schema in {'type': ..., 'min': ..., 'max': ...}
    String constraints can be defined by wrapping the schema in {'type': 'string', 'min_length': ..., 'max_length': ..., 'pattern': ...}
    List constraints can be defined by wrapping the schema in {'type': 'list', 'items': ..., 'min_items': ..., 'max_items': ...}
    Dict constraints can be defined by wrapping the schema in {'type': 'dict', 'min_properties': ..., 'max_properties': ...}
    Enum constraints can be defined by adding an 'enum' key with a list of allowed values.
    Composition constraints can be defined by using 'anyOf', 'allOf', 'oneOf' with a list of schemas, or 'not' for negation.
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
            # Composition: anyOf
            if "anyOf" in schema:
                options = schema["anyOf"]
                if not isinstance(options, list):
                    errors.append(f"Invalid schema definition: 'anyOf' must be a list at {path}")
                    return
                
                any_valid = False
                for opt_schema in options:
                    opt_errors = []
                    self._validate_recursive(opt_schema, data, path, opt_errors)
                    if not opt_errors:
                        any_valid = True
                        break
                
                if not any_valid:
                    errors.append(f"Value at {path} does not match any of the required schemas in anyOf")
                return

            # Composition: allOf
            if "allOf" in schema:
                options = schema["allOf"]
                if not isinstance(options, list):
                    errors.append(f"Invalid schema definition: 'allOf' must be a list at {path}")
                    return
                
                for opt_schema in options:
                    self._validate_recursive(opt_schema, data, path, errors)
                return

            # Composition: oneOf
            if "oneOf" in schema:
                options = schema["oneOf"]
                if not isinstance(options, list):
                    errors.append(f"Invalid schema definition: 'oneOf' must be a list at {path}")
                    return
                
                valid_count = 0
                for opt_schema in options:
                    opt_errors = []
                    self._validate_recursive(opt_schema, data, path, opt_errors)
                    if not opt_errors:
                        valid_count += 1
                
                if valid_count != 1:
                    errors.append(f"Value at {path} must match exactly one schema in oneOf (matched {valid_count})")
                return

            # Negation: not
            if "not" in schema:
                neg_schema = schema["not"]
                neg_errors = []
                self._validate_recursive(neg_schema, data, path, neg_errors)
                if not neg_errors:
                    errors.append(f"Value at {path} must NOT match the schema provided in 'not'")
                return

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
                
                # Length and pattern validation for strings
                elif isinstance(data, str):
                    length = len(data)
                    if "min_length" in schema and length < schema["min_length"]:
                        errors.append(f"String at {path} is too short (min_length: {schema['min_length']})")
                    elif "min" in schema and length < schema["min"]:
                        errors.append(f"String at {path} is too short (min: {schema['min']})")
                    
                    if "max_length" in schema and length > schema["max_length"]:
                        errors.append(f"String at {path} is too long (max_length: {schema['max_length']})")
                    elif "max" in schema and length > schema["max"]:
                        errors.append(f"String at {path} is too long (max: {schema['max']})")
                    
                    if "pattern" in schema:
                        pattern = schema["pattern"]
                        if not re.search(pattern, data):
                            errors.append(f"String at {path} does not match pattern: {pattern}")
                
                # Item and size validation for lists
                elif isinstance(data, list):
                    length = len(data)
                    if "min_items" in schema and length < schema["min_items"]:
                        errors.append(f"List at {path} is too short (min_items: {schema['min_items']})")
                    elif "min" in schema and length < schema["min"]:
                        errors.append(f"List at {path} is too short (min: {schema['min']})")
                    
                    if "max_items" in schema and length > schema["max_items"]:
                        errors.append(f"List at {path} is too long (max_items: {schema['max_items']})")
                    elif "max" in schema and length > schema["max"]:
                        errors.append(f"List at {path} is too long (max: {schema['max']})")
                    
                    if "items" in schema:
                        item_schema = schema["items"]
                        for i, item in enumerate(data):
                            self._validate_recursive(item_schema, item, f"{path}[{i}]", errors)
                
                # Size validation for dicts
                elif isinstance(data, dict):
                    length = len(data)
                    if "min_properties" in schema and length < schema["min_properties"]:
                        errors.append(f"Dict at {path} has too few properties (min_properties: {schema['min_properties']})")
                    elif "min" in schema and length < schema["min"]:
                        errors.append(f"Dict at {path} has too few properties (min: {schema['min']})")
                    
                    if "max_properties" in schema and length > schema["max_properties"]:
                        errors.append(f"Dict at {path} has too many properties (max_properties: {schema['max_properties']})")
                    elif "max" in schema and length > schema["max"]:
                        errors.append(f"Dict at {path} has too many properties (max: {schema['max']})")
                
                # Enum validation
                if "enum" in schema:
                    allowed_values = schema["enum"]
                    if not isinstance(allowed_values, list):
                        errors.append(f"Invalid schema definition: 'enum' must be a list at {path}")
                    elif data not in allowed_values:
                        errors.append(f"Value at {path} must be one of {allowed_values}, got {repr(data)}")
                
                return

            # Object validation
            if not isinstance(data, dict):
                errors.append(f"Expected dict at {path}, got {type(data).__name__}")
                return
            
            # Check for dependencies
            if "dependencies" in schema:
                deps = schema["dependencies"]
                if not isinstance(deps, dict):
                    errors.append(f"Invalid schema definition: 'dependencies' must be a dict at {path}")
                else:
                    for key, required_fields in deps.items():
                        if key in data:
                            if not isinstance(required_fields, list):
                                errors.append(f"Invalid schema definition: dependencies for {key} must be a list at {path}")
                                continue
                            for field in required_fields:
                                if field not in data:
                                    errors.append(f"Field {path}.{field} is required because {path}.{key} is present")

            # Check for additionalProperties
            additional_properties = schema.get("additionalProperties", True)
            
            # We need to know which fields are explicitly defined in the schema
            defined_fields = set()
            for key, rules in schema.items():
                if key in ("additionalProperties", "dependencies"):
                    continue
                defined_fields.add(key)

            # Validate defined fields
            for key, rules in schema.items():
                if key in ("additionalProperties", "dependencies"):
                    continue
                
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

            # Validate additional fields
            if additional_properties is False:
                for key in data:
                    if key not in defined_fields:
                        errors.append(f"Additional property {key} not allowed at {path}")
            elif isinstance(additional_properties, (str, dict)):
                for key in data:
                    if key not in defined_fields:
                        self._validate_recursive(additional_properties, data[key], f"{path}.{key}", errors)
        
        else:
            errors.append(f"Unsupported schema definition at {path}")

    def _check_type(self, type_name: str, data: Any, path: str, errors: List[str]):
        expected_type = self.TYPE_MAP.get(type_name)
        if expected_type is None:
            errors.append(f"Invalid schema type '{type_name}' at {path}")
            return
        
        if not isinstance(data, expected_type):
            errors.append(f"Expected {type_name} at {path}, got {type(data).__name__}")