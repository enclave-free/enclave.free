import sys
import unittest
from pathlib import Path

from pydantic import ValidationError


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class DataClassificationAndInputValidationTest(unittest.TestCase):
    def test_data_classification_inventory_covers_security_readiness_terms(self) -> None:
        import data_classification

        inventory = data_classification.get_data_classification_inventory()
        keys = {item["key"] for item in inventory["items"]}

        self.assertEqual(inventory["summary"]["total"], len(inventory["items"]))
        self.assertTrue({
            "pii_fields",
            "uploaded_documents",
            "derived_chunks_embeddings",
            "secrets",
            "audit_log_evidence",
            "inference_verification_records",
            "user_memory",
            "session_memory",
            "copied_exports",
        }.issubset(keys))

    def test_api_boundary_models_reject_oversized_and_malformed_inputs(self) -> None:
        from models import DBQueryRequest, FieldDefinitionCreate, FieldDefinitionUpdate, MagicLinkRequest, UserTypeCreate

        invalid_payloads = [
            (MagicLinkRequest, {"email": "not-an-email", "name": "Ada"}),
            (MagicLinkRequest, {"email": "person@example.com", "name": "x" * 201}),
            (UserTypeCreate, {"name": ""}),
            (UserTypeCreate, {"name": "x" * 121}),
            (FieldDefinitionCreate, {"field_name": "Focus", "field_type": "script"}),
            (FieldDefinitionCreate, {"field_name": "Focus", "field_type": "select", "options": ["x" * 201]}),
            (FieldDefinitionUpdate, {"field_type": "script"}),
            (FieldDefinitionUpdate, {"options": [" "]}),
            (DBQueryRequest, {"sql": ""}),
            (DBQueryRequest, {"sql": "SELECT 1 " + ("x" * 10000)}),
        ]

        for model, payload in invalid_payloads:
            with self.subTest(model=model.__name__, payload=payload):
                with self.assertRaises(ValidationError):
                    model(**payload)

    def test_api_boundary_models_accept_representative_valid_inputs(self) -> None:
        from models import DBQueryRequest, FieldDefinitionCreate, FieldDefinitionUpdate, MagicLinkRequest, UserTypeCreate

        self.assertEqual(MagicLinkRequest(email="person@example.com", name="Ada").email, "person@example.com")
        self.assertEqual(UserTypeCreate(name="Organizer").name, "Organizer")
        self.assertEqual(
            FieldDefinitionCreate(
                field_name="Focus",
                field_type="select",
                options=["Housing", "Benefits"],
            ).field_type,
            "select",
        )
        self.assertEqual(FieldDefinitionUpdate(field_type=" EMAIL ", options=[" Housing "]).field_type, "email")
        self.assertEqual(FieldDefinitionUpdate(field_type=" EMAIL ", options=[" Housing "]).options, ["Housing"])
        self.assertEqual(DBQueryRequest(sql="SELECT id FROM users LIMIT 5").sql, "SELECT id FROM users LIMIT 5")


if __name__ == "__main__":
    unittest.main()
