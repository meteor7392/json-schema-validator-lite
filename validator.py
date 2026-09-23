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

    def validate(self, data: Any, mutate: bool = False) -> Tuple[bool, List[str]]:
        """
        Validates the provided data against the schema.
        Returns a tuple of (is_valid, list_of_errors).
        If mutate is True, missing fields with default values will be added to the data.
        """
        errors = []
        self._validate_recursive(self.schema, data, "root", errors, mutate)
        return len(errors) == 0, errors

    def _validate_recursive(self, schema: Any, data: Any, path: str, errors: List[str], mutate: bool = False):
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
                    self._validate_recursive(opt_schema, data, path, opt_errors, mutate)
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
                    self._validate_recursive(opt_schema, data, path, errors, mutate)
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
                    self._validate_recursive(opt_schema, data, path, opt_errors, mutate)
                    if not opt_errors:
                        valid_count += 1
                
                if valid_count != 1:
                    errors.append(f"Value at {path} must match exactly one schema in oneOf (matched {valid_count})")
                return

            # Negation: not
            if "not" in schema:
                neg_schema = schema["not"]
                neg_errors = []
                self._validate_recursive(neg_schema, data, path, neg_errors, mutate)
                if not neg_errors:
                    errors.append(f"Value at {path} must NOT match the schema provided in 'not'")
                return

            # Constant value validation
            if "const" in schema:
                constant_val = schema["const"]
                if data != constant_val:
                    errors.append(f"Value at {path} must be exactly {repr(constant_val)}, got {repr(data)}")

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
                    
                    ex_min = schema.get("exclusiveMinimum") if "exclusiveMinimum" in schema else schema.get("minExclusive")
                    if ex_min is not None and data <= ex_min:
                        errors.append(f"Value at {path} must be strictly greater than {ex_min}")
                    
                    ex_max = schema.get("exclusiveMaximum") if "exclusiveMaximum" in schema else schema.get("maxExclusive")
                    if ex_max is not None and data >= ex_max:
                        errors.append(f"Value at {path} must be strictly less than {ex_max}")
                    
                    if "multipleOf" in schema:
                        multiple = schema["multipleOf"]
                        if multiple == 0:
                            errors.append(f"Invalid schema definition: 'multipleOf' cannot be 0 at {path}")
                        elif data % multiple != 0:
                            errors.append(f"Value at {path} must be a multiple of {multiple}")
                
                # Length and pattern validation for strings
                elif isinstance(data, str):
                    length = len(data)
                    min_len = schema.get("minLength") if "minLength" in schema else schema.get("min_length")
                    if min_len is not None and length < min_len:
                        errors.append(f"String at {path} is too short (min_length: {min_len})")
                    elif "min" in schema and length < schema["min"]:
                        errors.append(f"String at {path} is too short (min: {schema['min']})")
                    
                    max_len = schema.get("maxLength") if "maxLength" in schema else schema.get("max_length")
                    if max_len is not None and length > max_len:
                        errors.append(f"String at {path} is too long (max_length: {max_len})")
                    elif "max" in schema and length > schema["max"]:
                        errors.append(f"String at {path} is too long (max: {schema['max']})")
                    
                    if "pattern" in schema:
                        pattern = schema["pattern"]
                        if not re.search(pattern, data):
                            errors.append(f"String at {path} does not match pattern: {pattern}")
                
                # Item and size validation for lists
                elif isinstance(data, list):
                    length = len(data)
                    min_items = schema.get("minItems") if "minItems" in schema else schema.get("min_items")
                    if min_items is not None and length < min_items:
                        errors.append(f"List at {path} is too short (min_items: {min_items})")
                    elif "min" in schema and length < schema["min"]:
                        errors.append(f"List at {path} is too short (min: {schema['min']})")
                    
                    max_items = schema.get("maxItems") if "maxItems" in schema else schema.get("max_items")
                    if max_items is not None and length > max_items:
                        errors.append(f"List at {path} is too long (max_items: {max_items})")
                    elif "max" in schema and length > schema["max"]:
                        errors.append(f"List at {path} is too long (max: {schema['max']})")
                    
                    if schema.get("uniqueItems") is True:
                        try:
                            if len(set(data)) != length:
                                errors.append(f"List at {path} contains duplicate items")
                        except TypeError:
                            # For unhashable types (like dicts in lists), manual check
                            seen = []
                            for item in data:
                                if item in seen:
                                    errors.append(f"List at {path} contains duplicate items")
                                    break
                                seen.append(item)

                    if "items" in schema:
                        item_schema = schema["items"]
                        if isinstance(item_schema, list):
                            # Tuple validation: each item in the list is a schema for the corresponding element
                            for i, item in enumerate(data):
                                if i < len(item_schema):
                                    self._validate_recursive(item_schema[i], item, f"{path}[{i}]", errors, mutate)
                        else:
                            # Uniform validation: all items match the same schema
                            for i, item in enumerate(data):
                                self._validate_recursive(item_schema, item, f"{path}[{i}]", errors, mutate)
                
                # Size validation for dicts
                elif isinstance(data, dict):
                    length = len(data)
                    min_props = schema.get("minProperties") if "minProperties" in schema else schema.get("min_properties")
                    if min_props is not None and length < min_props:
                        errors.append(f"Dict at {path} has too few properties (min_properties: {min_props})")
                    elif "min" in schema and length < schema["min"]:
                        errors.append(f"Dict at {path} has too few properties (min: {schema['min']})")
                    
                    max_props = schema.get("maxProperties") if "maxProperties" in schema else schema.get("max_properties")
                    if max_props is not None and length > max_props:
                        errors.append(f"Dict at {path} has too many properties (max_properties: {max_props})")
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
            
            # Extract properties from both the root schema and the 'properties' key
            properties_schema = schema.get("properties", {})
            if not isinstance(properties_schema, dict):
                errors.append(f"Invalid schema definition: 'properties' must be a dict at {path}")
                properties_schema = {}

            defined_fields = set()
            # Fields defined directly in the schema
            for key in schema:
                if key in ("additionalProperties", "dependencies", "required", "properties", "type", "min", "max", "min_properties", "max_properties", "minProperties", "maxProperties", "const", "patternProperties"):
                    continue
                defined_fields.add(key)
            # Fields defined in the 'properties' keyword
            for key in properties_schema:
                defined_fields.add(key)

            # Validate defined fields
            for key in defined_fields:
                current_path = f"{path}.{key}"
                
                # Rule can be in 'properties' or directly in schema
                rules = properties_schema.get(key) if key in properties_schema else schema.get(key)
                
                # Check for optional flag
                is_optional = False
                actual_rules = rules
                if isinstance(rules, dict) and "optional" in rules:
                    is_optional = True
                    actual_rules = rules["optional"]

                if key not in data:
                    # Handle default value
                    default_val = None
                    has_default = False
                    if isinstance(rules, dict) and "default" in rules:
                        default_val = rules["default"]
                        has_default = True
                    elif isinstance(actual_rules, dict) and "default" in actual_rules:
                        default_val = actual_rules["default"]
                        has_default = True

                    if has_default:
                        if mutate:
                            data[key] = default_val
                        self._validate_recursive(actual_rules, default_val, current_path, errors, mutate)
                    elif not is_optional:
                        # Check if the field is missing from the 'required' list if 'required' is defined
                        required_list = schema.get("required")
                        if required_list is not None:
                            if not isinstance(required_list, list):
                                errors.append(f"Invalid schema definition: 'required' must be a list at {path}")
                            elif key not in required_list:
                                is_optional = True
                        
                        if not is_optional:
                            errors.append(f"Missing required field: {current_path}")
                else:
                    self._validate_recursive(actual_rules, data[key], current_path, errors, mutate)

            # Handle 'required' list for fields NOT explicitly listed in defined_fields
            required_list = schema.get("required")
            if isinstance(required_list, list):
                for req_field in required_list:
                    if req_field not in data:
                        # Check for default value in properties or schema
                        has_default = False
                        prop_rules = properties_schema.get(req_field) if req_field in properties_schema else schema.get(req_field)
                        if isinstance(prop_rules, dict) and "default" in prop_rules:
                            has_default = True
                        
                        if not has_default:
                            current_path = f"{path}.{req_field}"
                            if not any(current_path in err for err in errors):
                                errors.append(f"Missing required field: {current_path}")

            # Validate additional fields
            pattern_props = schema.get("patternProperties", {})
            if not isinstance(pattern_props, dict):
                pattern_props = {}

            for key in data:
                if key not in defined_fields:
                    # Check if it matches any patternProperties
                    matched_pattern = False
                    for pattern, p_schema in pattern_props.items():
                        if re.search(pattern, key):
                            self._validate_recursive(p_schema, data[key], f"{path}.{key}", errors, mutate)
                            matched_pattern = True
                    
                    if not matched_pattern:
                        if additional_properties is False:
                            errors.append(f"Additional property {key} not allowed at {path}")
                        elif isinstance(additional_properties, (str, dict)):
                            self._validate_recursive(additional_properties, data[key], f"{path}.{key}", errors, mutate)
        
        else:
            errors.append(f"Unsupported schema definition at {path}")

    def _check_type(self, type_name: str, data: Any, path: str, errors: List[str]):
        expected_type = self.TYPE_MAP.get(type_name)
        if expected_type is None:
            errors.append(f"Invalid schema type '{type_name}' at {path}")
            return
        
        # Allow integers to be treated as floats
        if type_name == "float" and isinstance(data, int):
            return

        if not isinstance(data, expected_type):
            errors.append(f"Expected {type_name} at {path}, got {type(data).__name__}")