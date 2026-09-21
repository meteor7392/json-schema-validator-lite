# JSON Schema Validator Lite

A lightweight, zero-dependency Python library to validate JSON-like dictionaries against simple schema definitions.

## Features
- Type checking (string, integer, float, boolean, list, dict)
- Required field validation
- Nested schema support
- Custom error messages
- Default value injection
- Numeric constraints (min, max, exclusiveMinimum, exclusiveMaximum, multipleOf)
- String constraints (minLength, maxLength, pattern)
- List/Dict size constraints
- Composition (anyOf, allOf, oneOf, not)

## Usage

```python
from validator import SchemaValidator

schema = {
    "name": "string",
    "age": "integer",
    "tags": "list",
    "address": {
        "city": "string",
        "zip": "integer"
    }
}

data = {
    "name": "Alice",
    "age": 30,
    "tags": ["python", "coding"],
    "address": {
        "city": "New York",
        "zip": 10001
    }
}

validator = SchemaValidator(schema)
is_valid, errors = validator.validate(data)
```