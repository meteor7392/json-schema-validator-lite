import unittest
from validator import SchemaValidator

class TestSchemaValidator(unittest.TestCase):
    def test_valid_schema(self):
        schema = {
            "name": "string",
            "age": "integer",
            "meta": {
                "active": "boolean"
            }
        }
        data = {
            "name": "Bob",
            "age": 25,
            "meta": {
                "active": True
            }
        }
        validator = SchemaValidator(schema)
        is_valid, errors = validator.validate(data)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_invalid_types(self):
        schema = {"age": "integer"}
        data = {"age": "twenty-five"}
        validator = SchemaValidator(schema)
        is_valid, errors = validator.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("Expected integer at root.age, got str", errors)

    def test_missing_fields(self):
        schema = {"name": "string", "email": "string"}
        data = {"name": "Bob"}
        validator = SchemaValidator(schema)
        is_valid, errors = validator.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("Missing required field: root.email", errors)

    def test_optional_fields(self):
        schema = {
            "name": "string",
            "age": {"optional": "integer"}
        }
        data = {"name": "Bob"}
        validator = SchemaValidator(schema)
        is_valid, errors = validator.validate(data)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_numeric_constraints(self):
        schema = {
            "score": {"type": "integer", "min": 0, "max": 100}
        }
        
        # Too low
        v1 = SchemaValidator(schema).validate({"score": -1})
        self.assertFalse(v1[0])
        self.assertIn("Value at root.score is too small (min: 0)", v1[1])
        
        # Too high
        v2 = SchemaValidator(schema).validate({"score": 101})
        self.assertFalse(v2[0])
        self.assertIn("Value at root.score is too large (max: 100)", v2[1])
        
        # Valid
        v3 = SchemaValidator(schema).validate({"score": 50})
        self.assertTrue(v3[0])

    def test_string_constraints(self):
        schema = {
            "username": {"type": "string", "min_length": 3, "max_length": 10}
        }
        
        # Too short
        v1 = SchemaValidator(schema).validate({"username": "ab"})
        self.assertFalse(v1[0])
        self.assertIn("String at root.username is too short (min_length: 3)", v1[1])
        
        # Too long
        v2 = SchemaValidator(schema).validate({"username": "verylongusername"})
        self.assertFalse(v2[0])
        self.assertIn("String at root.username is too long (max_length: 10)", v2[1])
        
        # Valid
        v3 = SchemaValidator(schema).validate({"username": "bob"})
        self.assertTrue(v3[0])

    def test_string_pattern(self):
        schema = {
            "email": {"type": "string", "pattern": r"^\S+@\S+\.\S+$"}
        }
        
        # Valid
        v1 = SchemaValidator(schema).validate({"email": "test@example.com"})
        self.assertTrue(v1[0])
        
        # Invalid
        v2 = SchemaValidator(schema).validate({"email": "not-an-email"})
        self.assertFalse(v2[0])
        self.assertIn("String at root.email does not match pattern: ^\\S+@\\S+\\.\\S+$", v2[1])

    def test_list_item_validation(self):
        schema = {
            "tags": {"type": "list", "items": "string"}
        }
        
        # Valid
        v1 = SchemaValidator(schema).validate({"tags": ["a", "b"]})
        self.assertTrue(v1[0])
        
        # Invalid item
        v2 = SchemaValidator(schema).validate({"tags": ["a", 1]})
        self.assertFalse(v2[0])
        self.assertIn("Expected string at root.tags[1], got int", v2[1])

    def test_list_size_validation(self):
        schema = {
            "tags": {"type": "list", "min_items": 2, "max_items": 3}
        }
        
        # Too few
        v1 = SchemaValidator(schema).validate({"tags": ["a"]})
        self.assertFalse(v1[0])
        self.assertIn("List at root.tags is too short (min_items: 2)", v1[1])
        
        # Too many
        v2 = SchemaValidator(schema).validate({"tags": ["a", "b", "c", "d"]})
        self.assertFalse(v2[0])
        self.assertIn("List at root.tags is too long (max_items: 3)", v2[1])
        
        # Valid
        v3 = SchemaValidator(schema).validate({"tags": ["a", "b"]})
        self.assertTrue(v3[0])

    def test_dict_size_validation(self):
        schema = {
            "meta": {"type": "dict", "min_properties": 1, "max_properties": 2}
        }
        
        # Too few
        v1 = SchemaValidator(schema).validate({"meta": {}})
        self.assertFalse(v1[0])
        self.assertIn("Dict at root.meta has too few properties (min_properties: 1)", v1[1])
        
        # Too many
        v2 = SchemaValidator(schema).validate({"meta": {"a": 1, "b": 2, "c": 3}})
        self.assertFalse(v2[0])
        self.assertIn("Dict at root.meta has too many properties (max_properties: 2)", v2[1])
        
        # Valid
        v3 = SchemaValidator(schema).validate({"meta": {"a": 1}})
        self.assertTrue(v3[0])

    def test_nested_invalid(self):
        schema = {"user": {"id": "integer"}}
        data = {"user": {"id": "abc"}}
        validator = SchemaValidator(schema)
        is_valid, errors = validator.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("Expected integer at root.user.id, got str", errors)

    def test_enum_validation(self):
        schema = {
            "status": {"type": "string", "enum": ["pending", "active", "closed"]}
        }
        
        # Valid
        v1 = SchemaValidator(schema).validate({"status": "active"})
        self.assertTrue(v1[0])
        
        # Invalid
        v2 = SchemaValidator(schema).validate({"status": "unknown"})
        self.assertFalse(v2[0])
        self.assertIn("Value at root.status must be one of ['pending', 'active', 'closed'], got 'unknown'", v2[1])

    def test_anyof_validation(self):
        schema = {
            "id": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "integer"}
                ]
            }
        }
        self.assertTrue(SchemaValidator(schema).validate({"id": "abc"})[0])
        self.assertTrue(SchemaValidator(schema).validate({"id": 123})[0])
        self.assertFalse(SchemaValidator(schema).validate({"id": 12.3})[0])

    def test_allof_validation(self):
        schema = {
            "score": {
                "allOf": [
                    {"type": "integer"},
                    {"min": 0, "max": 100}
                ]
            }
        }
        self.assertTrue(SchemaValidator(schema).validate({"score": 50})[0])
        self.assertFalse(SchemaValidator(schema).validate({"score": 150})[0])
        self.assertFalse(SchemaValidator(schema).validate({"score": "50"})[0])

    def test_oneof_validation(self):
        schema = {
            "value": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "integer"}
                ]
            }
        }
        # Valid cases
        self.assertTrue(SchemaValidator(schema).validate({"value": "abc"})[0])
        self.assertTrue(SchemaValidator(schema).validate({"value": 123})[0])
        # Invalid cases
        self.assertFalse(SchemaValidator(schema).validate({"value": 12.3})[0])

    def test_not_validation(self):
        schema = {
            "value": {
                "not": {"type": "integer"}
            }
        }
        # Valid case (is a string, so NOT an integer)
        self.assertTrue(SchemaValidator(schema).validate({"value": "abc"})[0])
        # Invalid case (is an integer)
        self.assertFalse(SchemaValidator(schema).validate({"value": 123})[0])

if __name__ == "__main__":
    unittest.main()