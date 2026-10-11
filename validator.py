from typing import Any, Dict, List, Tuple, Union, Callable, Optional
import re
import math
import json

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

    FORMATS = {
        "email": r"^\S+@\S+\.\S+$",
        "date": r"^\d{4}-\d{2}-\d{2}$",
        "uuid": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    }

    def __init__(self, schema: Dict[str, Any], error_callback: Optional[Callable[[str], None]] = None):
        self.schema = schema
        self.error_callback = error_callback

    @classmethod
    def from_json(cls, file_path: str, error_callback: Optional[Callable[[str], None]] = None) -> 'SchemaValidator':
        """Creates a SchemaValidator instance by loading a schema from a JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        return cls(schema, error_callback)

    def validate(self, data: Any, mutate: bool = False, context: str = "both", strict: bool = False) -> Tuple[bool, List[str]]:
        """
        Validates the provided data against the schema.
        Returns a tuple of (is_valid, list_of_errors).
        If mutate is True, missing fields with default values will be added to the data.
        
        context can be "read", "write", or "both" (default). 
        - If "read", writeOnly fields are ignored/invalid.
        - If "write", readOnly fields are prohibited.
        
        If strict is True, any fields in the data not explicitly listed in 'properties' or matching 'patternProperties' 
        are treated as additional properties, regardless of whether they appear elsewhere in the schema.
        """
        errors = []
        # Handle root-level default if data is None
        if data is None and isinstance(self.schema, dict) and "default" in self.schema:
            data = self.schema["default"]

        self._validate_recursive(self.schema, data, "root", errors, mutate, context, strict)
        return len(errors) == 0, errors

    def get_descriptions(self) -> Dict[str, str]:
        """
        Extracts all 'description' fields from the schema.
        Returns a dictionary mapping paths to descriptions.
        """
        descriptions = {}
        self._extract_descriptions(self.schema, "root", descriptions)
        return descriptions

    def generate_sample(self) -> Any:
        """
        Generates a sample data object that satisfies the schema using default values 
        where possible, and basic placeholders for types otherwise.
        """
        return self._generate_sample_recursive(self.schema)

    def _generate_sample_recursive(self, schema: Any) -> Any:
        if isinstance(schema, str):
            return self._get_type_placeholder(schema)
        
        if not isinstance(schema, dict):
            return None

        if "default" in schema:
            return schema["default"]
        
        if "const" in schema:
            return schema["const"]

        if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
            return schema["enum"][0]

        if "anyOf" in schema and isinstance(schema["anyOf"], list) and schema["anyOf"]:
            return self._generate_sample_recursive(schema["anyOf"][0])
        
        if "allOf" in schema and isinstance(schema["allOf"], list) and schema["allOf"]:
            # Merge allOf samples (simplified: use the first one as base)
            base = self._generate_sample_recursive(schema["allOf"][0])
            if isinstance(base, dict):
                for s in schema["allOf"][1:]:
                    sample = self._generate_sample_recursive(s)
                    if isinstance(sample, dict):
                        base.update(sample)
            return base

        if "oneOf" in schema and isinstance(schema["oneOf"], list) and schema["oneOf"]:
            return self._generate_sample_recursive(schema["oneOf"][0])

        type_def = schema.get("type")
        if isinstance(type_def, list) and type_def:
            return self._get_type_placeholder(type_def[0])
        elif isinstance(type_def, str):
            if type_def == "dict":
                sample_dict = {}
                properties = schema.get("properties", {})
                if isinstance(properties, dict):
                    for key, sub_schema in properties.items():
                        # Handle optional wrapper
                        actual_sub = sub_schema.get("optional", sub_schema) if isinstance(sub_schema, dict) else sub_schema
                        sample_dict[key] = self._generate_sample_recursive(actual_sub)
                
                # Handle propertyNames sample
                prop_names_schema = schema.get("propertyNames")
                if prop_names_schema and not sample_dict:
                    # If no properties are defined, create one key that fits propertyNames
                    sample_key = self._generate_sample_recursive(prop_names_schema)
                    if isinstance(sample_key, str):
                        sample_dict[sample_key] = self._generate_sample_recursive(schema.get("additionalProperties", "string"))

                return sample_dict
            elif type_def == "list":
                items_schema = schema.get("items")
                if items_schema:
                    return [self._generate_sample_recursive(items_schema)]
                return []
            else:
                return self._get_type_placeholder(type_def)
        
        # If no type but it's a dict with keys that aren't schema keywords, it's an implicit dict
        keywords = ("additionalProperties", "dependencies", "required", "properties", "type", "min", "max", "min_properties", "max_properties", "minProperties", "maxProperties", "const", "patternProperties", "nullable", "description", "examples", "readOnly", "writeOnly", "propertyNames", "anyOf", "allOf", "oneOf", "not", "if", "then", "else", "enum", "default", "dependentRequired", "dependentSchemas")
        implicit_props = {k: v for k, v in schema.items() if k not in keywords}
        if implicit_props:
            sample_dict = {}
            for k, v in implicit_props.items():
                actual_v = v.get("optional", v) if isinstance(v, dict) else v
                sample_dict[k] = self._generate_sample_recursive(actual_v)
            return sample_dict

        return None

    def _get_type_placeholder(self, type_name: str) -> Any:
        placeholders = {
            "string": "sample_string",
            "integer": 0,
            "float": 0.0,
            "boolean": True,
            "list": [],
            "dict": {}
        }
        return placeholders.get(type_name, None)

    def _extract_descriptions(self, schema: Any, path: str, descriptions: Dict[str, str]):
        if not isinstance(schema, dict):
            return

        if "description" in schema:
            descriptions[path] = schema["description"]

        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, sub_schema in properties.items():
                self._extract_descriptions(sub_schema, f"{path}.{key}", descriptions)

        for key, value in schema.items():
            if key in ("additionalProperties", "dependencies", "required", "properties", "type", "min", "max", "min_properties", "max_properties", "minProperties", "maxProperties", "const", "patternProperties", "nullable", "description", "examples", "readOnly", "writeOnly", "propertyNames", "dependentRequired", "dependentSchemas"):
                continue
            if isinstance(value, dict):
                self._extract_descriptions(value, f"{path}.{key}", descriptions)

        for comp in ("anyOf", "allOf", "oneOf"):
            options = schema.get(comp)
            if isinstance(options, list):
                for i, opt_schema in enumerate(options):
                    self._extract_descriptions(opt_schema, f"{path}.{comp}[{i}]", descriptions)

        if "not" in schema:
            self._extract_descriptions(schema["not"], f"{path}.not", descriptions)

        items = schema.get("items")
        if isinstance(items, dict):
            self._extract_descriptions(items, f"{path}.items", descriptions)
        elif isinstance(items, list):
            for i, item_schema in enumerate(items):
                self._extract_descriptions(item_schema, f"{path}.items[{i}]", descriptions)

    def _add_error(self, path: str, message: str, errors: List[str]):
        """Helper to log error and optionally trigger the callback."""
        full_msg = f"{message} at {path}" if "at" not in message else message
        errors.append(full_msg)
        if self.error_callback:
            self.error_callback(full_msg)

    def _validate_recursive(self, schema: Any, data: Any, path: str, errors: List[str], mutate: bool = False, context: str = "both", strict: bool = False):
        if isinstance(schema, str):
            # To support 'nullable' on string shortcuts, we treat shortcuts as a simple dict schema
            schema_dict = {"type": schema}
            self._validate_recursive(schema_dict, data, path, errors, mutate, context, strict)
            return
        
        if not isinstance(schema, dict):
            self._add_error(path, "Unsupported schema definition", errors)
            return

        if context == "read" and schema.get("writeOnly") is True:
            if data is not None:
                self._add_error(path, f"Field {path} is writeOnly and should not be present in read context", errors)
            return

        if context == "write" and schema.get("readOnly") is True:
            if data is not None:
                self._add_error(path, f"Field {path} is readOnly and cannot be modified", errors)
            return

        if data is None:
            if schema.get("nullable") is True:
                if "const" in schema:
                    if schema["const"] is not None:
                        self._add_error(path, f"Value at {path} must be exactly {repr(schema['const'])}, got None", errors)
                if "enum" in schema:
                    allowed_values = schema["enum"]
                    if not isinstance(allowed_values, list):
                        self._add_error(path, f"Invalid schema definition: 'enum' must be a list at {path}", errors)
                    elif None not in allowed_values:
                        self._add_error(path, f"Value at {path} must be one of {allowed_values}, got None", errors)
                return
            else:
                if "type" in schema:
                    self._add_error(path, f"Value at {path} cannot be null", errors)
                return

        if "anyOf" in schema:
            options = schema["anyOf"]
            if not isinstance(options, list):
                self._add_error(path, f"Invalid schema definition: 'anyOf' must be a list at {path}", errors)
                return
            any_valid = False
            all_options_errors = []
            for i, opt_schema in enumerate(options):
                opt_errors = []
                self._validate_recursive(opt_schema, data, path, opt_errors, mutate, context, strict)
                if not opt_errors:
                    any_valid = True
                    break
                all_options_errors.append(f"Option {i}: {'; '.join(opt_errors)}")
            if not any_valid:
                self._add_error(path, f"Value at {path} does not match any of the required schemas in anyOf. Errors: [{ ' | '.join(all_options_errors) }]", errors)
            return

        if "allOf" in schema:
            options = schema["allOf"]
            if not isinstance(options, list):
                self._add_error(path, f"Invalid schema definition: 'allOf' must be a list at {path}", errors)
                return
            for opt_schema in options:
                self._validate_recursive(opt_schema, data, path, errors, mutate, context, strict)
            return

        if "oneOf" in schema:
            options = schema["oneOf"]
            if not isinstance(options, list):
                self._add_error(path, f"Invalid schema definition: 'oneOf' must be a list at {path}", errors)
                return
            valid_count = 0
            all_options_errors = []
            for i, opt_schema in enumerate(options):
                opt_errors = []
                self._validate_recursive(opt_schema, data, path, opt_errors, mutate, context, strict)
                if not opt_errors:
                    valid_count += 1
                else:
                    all_options_errors.append(f"Option {i}: {'; '.join(opt_errors)}")
            if valid_count != 1:
                err_msg = f"Value at {path} must match exactly one schema in oneOf (matched {valid_count})"
                if valid_count == 0:
                    err_msg += f". Errors: [{ ' | '.join(all_options_errors) }]"
                self._add_error(path, err_msg, errors)
            return

        if "not" in schema:
            neg_schema = schema["not"]
            neg_errors = []
            self._validate_recursive(neg_schema, data, path, neg_errors, mutate, context, strict)
            if not neg_errors:
                self._add_error(path, f"Value at {path} must NOT match the schema provided in 'not'", errors)
            return

        if "if" in schema:
            if_schema = schema["if"]
            if_errors = []
            self._validate_recursive(if_schema, data, path, if_errors, mutate, context, strict)
            if not if_errors:
                if "then" in schema:
                    self._validate_recursive(schema["then"], data, path, errors, mutate, context, strict)
            elif "else" in schema:
                self._validate_recursive(schema["else"], data, path, errors, mutate, context, strict)

        if "const" in schema:
            constant_val = schema["const"]
            if data != constant_val:
                self._add_error(path, f"Value at {path} must be exactly {repr(constant_val)}, got {repr(data)}", errors)

        if "examples" in schema:
            examples = schema["examples"]
            if not isinstance(examples, list):
                self._add_error(path, f"Invalid schema definition: 'examples' must be a list at {path}", errors)

        if "type" in schema:
            type_def = schema["type"]
            if isinstance(type_def, list):
                valid_type = False
                for t in type_def:
                    temp_errors = []
                    self._check_type(t, data, path, temp_errors)
                    if not temp_errors:
                        valid_type = True
                        break
                if not valid_type:
                    self._add_error(path, f"Expected one of {type_def} at {path}, got {type(data).__name__}", errors)
            elif isinstance(type_def, str):
                self._check_type(type_def, data, path, errors)
            else:
                self._add_error(path, f"Invalid schema definition: 'type' must be a string or list of strings at {path}", errors)
                return
            
            if isinstance(data, (int, float)):
                if "min" in schema and data < schema["min"]:
                    self._add_error(path, f"Value at {path} is too small (min: {schema['min']})", errors)
                if "max" in schema and data > schema["max"]:
                    self._add_error(path, f"Value at {path} is too large (max: {schema['max']})", errors)
                ex_min = schema.get("exclusiveMinimum") if "exclusiveMinimum" in schema else schema.get("minExclusive")
                if ex_min is not None and data <= ex_min:
                    self._add_error(path, f"Value at {path} must be strictly greater than {ex_min}", errors)
                ex_max = schema.get("exclusiveMaximum") if "exclusiveMaximum" in schema else schema.get("maxExclusive")
                if ex_max is not None and data >= ex_max:
                    self._add_error(path, f"Value at {path} must be strictly less than {ex_max}", errors)
                if "multipleOf" in schema:
                    multiple = schema["multipleOf"]
                    if multiple == 0:
                        self._add_error(path, f"Invalid schema definition: 'multipleOf' cannot be 0 at {path}", errors)
                    else:
                        remainder = data % multiple
                        if not (math.isclose(remainder, 0, abs_tol=1e-9) or math.isclose(remainder, multiple, abs_tol=1e-9)):
                            self._add_error(path, f"Value at {path} must be a multiple of {multiple}", errors)
            
            elif isinstance(data, str):
                length = len(data)
                min_len = schema.get("minLength") if "minLength" in schema else schema.get("min_length")
                if min_len is not None and length < min_len:
                    self._add_error(path, f"String at {path} is too short (min_length: {min_len})", errors)
                elif "min" in schema and length < schema["min"]:
                    self._add_error(path, f"String at {path} is too short (min: {schema['min']})", errors)
                max_len = schema.get("maxLength") if "maxLength" in schema else schema.get("max_length")
                if max_len is not None and length > max_len:
                    self._add_error(path, f"String at {path} is too long (max_length: {max_len})", errors)
                elif "max" in schema and length > schema["max"]:
                    self._add_error(path, f"String at {path} is too long (max: {schema['max']})", errors)
                if "pattern" in schema:
                    pattern = schema["pattern"]
                    if not re.search(pattern, data):
                        self._add_error(path, f"String at {path} does not match pattern: {pattern}", errors)
                if "format" in schema:
                    fmt = schema["format"]
                    if fmt in self.FORMATS:
                        if not re.search(self.FORMATS[fmt], data):
                            self._add_error(path, f"String at {path} does not match format: {fmt}", errors)
                    else:
                        self._add_error(path, f"Unsupported format '{fmt}' at {path}", errors)
            
            elif isinstance(data, list):
                length = len(data)
                min_items = schema.get("minItems") if "minItems" in schema else schema.get("min_items")
                if min_items is not None and length < min_items:
                    self._add_error(path, f"List at {path} is too short (min_items: {min_items})", errors)
                elif "min" in schema and length < schema["min"]:
                    self._add_error(path, f"List at {path} is too short (min: {schema['min']})", errors)
                max_items = schema.get("maxItems") if "maxItems" in schema else schema.get("max_items")
                if max_items is not None and length > max_items:
                    self._add_error(path, f"List at {path} is too long (max_items: {max_items})", errors)
                elif "max" in schema and length > schema["max"]:
                    self._add_error(path, f"List at {path} is too long (max: {schema['max']})", errors)
                if schema.get("uniqueItems") is True:
                    seen = []
                    for item in data:
                        if any(item == existing for existing in seen):
                            self._add_error(path, f"List at {path} contains duplicate items", errors)
                            break
                        seen.append(item)
                if "items" in schema:
                    item_schema = schema["items"]
                    if isinstance(item_schema, list):
                        for i, item in enumerate(data):
                            if i < len(item_schema):
                                self._validate_recursive(item_schema[i], item, f"{path}[{i}]", errors, mutate, context, strict)
                    else:
                        for i, item in enumerate(data):
                            if item is None and isinstance(item_schema, dict):
                                if "default" in item_schema and not item_schema.get("nullable"):
                                    if mutate:
                                        data[i] = item_schema["default"]
                                    item = data[i]
                                    self._validate_recursive(item_schema, item, f"{path}[{i}]", errors, mutate, context, strict)
                                    continue
                            self._validate_recursive(item_schema, item, f"{path}[{i}]", errors, mutate, context, strict)
            
            elif isinstance(data, dict):
                length = len(data)
                min_props = schema.get("minProperties") if "minProperties" in schema else schema.get("min_properties")
                if min_props is not None and length < min_props:
                    self._add_error(path, f"Dict at {path} has too few properties (min_properties: {min_props})", errors)
                elif "min" in schema and length < schema["min"]:
                    self._add_error(path, f"Dict at {path} has too few properties (min: {schema['min']})", errors)
                max_props = schema.get("maxProperties") if "maxProperties" in schema else schema.get("max_properties")
                if max_props is not None and length > max_props:
                    self._add_error(path, f"Dict at {path} has too many properties (max_properties: {max_props})", errors)
                elif "max" in schema and length > schema["max"]:
                    self._add_error(path, f"Dict at {path} has too many properties (max: {schema['max']})", errors)
            
            if "enum" in schema:
                allowed_values = schema["enum"]
                if not isinstance(allowed_values, list):
                    self._add_error(path, f"Invalid schema definition: 'enum' must be a list at {path}", errors)
                elif data not in allowed_values:
                    self._add_error(path, f"Value at {path} must be one of {allowed_values}, got {repr(data)}", errors)
            return

        if not isinstance(data, dict):
            self._add_error(path, f"Expected dict at {path}, got {type(data).__name__}", errors)
            return
        
        if "dependencies" in schema:
            deps = schema["dependencies"]
            if not isinstance(deps, dict):
                self._add_error(path, f"Invalid schema definition: 'dependencies' must be a dict at {path}", errors)
            else:
                for key, dependency in deps.items():
                    if key in data:
                        if isinstance(dependency, list):
                            for field in dependency:
                                if field not in data:
                                    self._add_error(path, f"Field {path}.{field} is required because {path}.{key} is present", errors)
                        elif isinstance(dependency, dict):
                            self._validate_recursive(dependency, data, path, errors, mutate, context, strict)
                        else:
                            self._add_error(path, f"Invalid schema definition: dependency for {key} must be a list or a dict at {path}", errors)

        if "propertyNames" in schema:
            prop_names_schema = schema["propertyNames"]
            for key in data:
                self._validate_recursive(prop_names_schema, key, f"{path}.propertyNames({key})", errors, mutate, context, strict)

        # Implement dependentRequired
        if "dependentRequired" in schema:
            dep_req = schema["dependentRequired"]
            if not isinstance(dep_req, dict):
                self._add_error(path, f"Invalid schema definition: 'dependentRequired' must be a dict at {path}", errors)
            else:
                for key, required_fields in dep_req.items():
                    if key in data:
                        if not isinstance(required_fields, list):
                            self._add_error(path, f"Invalid schema definition: 'dependentRequired' for {key} must be a list at {path}", errors)
                        else:
                            for field in required_fields:
                                if field not in data:
                                    self._add_error(path, f"Field {path}.{field} is required because {path}.{key} is present", errors)

        # Implement dependentSchemas
        if "dependentSchemas" in schema:
            dep_schemes = schema["dependentSchemas"]
            if not isinstance(dep_schemes, dict):
                self._add_error(path, f"Invalid schema definition: 'dependentSchemas' must be a dict at {path}", errors)
            else:
                for key, sub_schema in dep_schemes.items():
                    if key in data:
                        self._validate_recursive(sub_schema, data, path, errors, mutate, context, strict)

        additional_properties = schema.get("additionalProperties", True)
        properties_schema = schema.get("properties", {})
        if not isinstance(properties_schema, dict):
            self._add_error(path, f"Invalid schema definition: 'properties' must be a dict at {path}", errors)
            properties_schema = {}

        defined_fields = set()
        for key in properties_schema:
            defined_fields.add(key)
        
        if not strict:
            for key in schema:
                if key in ("additionalProperties", "dependencies", "required", "properties", "type", "min", "max", "min_properties", "max_properties", "minProperties", "maxProperties", "const", "patternProperties", "nullable", "description", "examples", "readOnly", "writeOnly", "propertyNames", "dependentRequired", "dependentSchemas"):
                    continue
                defined_fields.add(key)

        checked_fields = set()
        required_list = schema.get("required")
        if required_list is not None and not isinstance(required_list, list):
            self._add_error(path, f"Invalid schema definition: 'required' must be a list at {path}", errors)
            required_list = []
        elif required_list is None:
            required_list = []

        for key in defined_fields:
            current_path = f"{path}.{key}"
            rules = properties_schema.get(key) if key in properties_schema else schema.get(key)
            if rules is None:
                continue
            is_optional = False
            actual_rules = rules
            if isinstance(rules, dict) and "optional" in rules:
                is_optional = True
                actual_rules = rules["optional"]
            if key not in data:
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
                    self._validate_recursive(actual_rules, default_val, current_path, errors, mutate, context, strict)
                    checked_fields.add(key)
                elif not is_optional and (required_list and key in required_list or (not required_list and key not in properties_schema and key in schema)):
                    if not properties_schema or (key not in properties_schema):
                        self._add_error(current_path, f"Missing required field: {current_path}", errors)
                    elif key in required_list:
                        self._add_error(current_path, f"Missing required field: {current_path}", errors)
                    checked_fields.add(key)
            else:
                self._validate_recursive(actual_rules, data[key], current_path, errors, mutate, context, strict)
                checked_fields.add(key)

        for req_field in required_list:
            if req_field not in checked_fields:
                current_path = f"{path}.{req_field}"
                prop_rules = properties_schema.get(req_field) if req_field in properties_schema else schema.get(req_field)
                if prop_rules is None:
                    self._add_error(current_path, f"Missing required field: {current_path}", errors)
                    continue
                has_default = False
                if isinstance(prop_rules, dict) and "default" in prop_rules:
                    has_default = True
                    if mutate:
                        data[req_field] = prop_rules["default"]
                    actual_prop_rules = prop_rules.get("optional", prop_rules) if "optional" in prop_rules else prop_rules
                    self._validate_recursive(actual_prop_rules, prop_rules["default"], current_path, errors, mutate, context, strict)
                if not has_default:
                    self._add_error(current_path, f"Missing required field: {current_path}", errors)

        pattern_props = schema.get("patternProperties", {})
        if not isinstance(pattern_props, dict):
            pattern_props = {}

        for key in data:
            if key not in defined_fields:
                matched_pattern = False
                for pattern, p_schema in pattern_props.items():
                    if re.search(pattern, key):
                        self._validate_recursive(p_schema, data[key], f"{path}.{key}", errors, mutate, context, strict)
                        matched_pattern = True
                if not matched_pattern:
                    if additional_properties is False:
                        self._add_error(path, f"Additional property {key} not allowed at {path}", errors)
                    elif isinstance(additional_properties, (str, dict)):
                        self._validate_recursive(additional_properties, data[key], f"{path}.{key}", errors, mutate, context, strict)

    def _check_type(self, type_name: str, data: Any, path: str, errors: List[str]):
        expected_type = self.TYPE_MAP.get(type_name)
        if expected_type is None:
            self._add_error(path, f"Invalid schema type '{type_name}' at {path}", errors)
            return
        if type_name == "float" and isinstance(data, (int, float)):
            return
        if not isinstance(data, expected_type):
            self._add_error(path, f"Expected {type_name} at {path}, got {type(data).__name__}", errors)
}
