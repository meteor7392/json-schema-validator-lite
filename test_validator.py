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

    def test_nested_invalid(self):
        schema = {"user": {"id": "integer"}}
        data = {"user": {"id": "abc"}}
        validator = SchemaValidator(schema)
        is_valid, errors = validator.validate(data)
        self.assertFalse(is_valid)
        self.assertIn("Expected integer at root.user.id, got str", errors)

if __name__ == "__main__":
    unittest.main()