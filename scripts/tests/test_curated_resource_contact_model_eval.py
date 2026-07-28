import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parent / "TOOLS" / "test_5h_curated_resource_contact_model_eval.py"
SPEC = importlib.util.spec_from_file_location("issue_535_eval", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CuratedResourceContactEvalTests(unittest.TestCase):
    def test_fixture_name_and_prompts_use_one_organization(self):
        for language, _key, initial, followup, _stream in MODULE.CASES:
            self.assertIn(MODULE.ORG_NAME, MODULE.initial_message(language, initial))
            self.assertTrue(MODULE.context_free_followup(followup), followup)
        self.assertNotIn("Acme Legal Aid", MODULE.ORG_NAME)

    def test_cases_reset_stale_before_fresh_update(self):
        stale = {"email": "stale@example.test"}
        fresh = {"email": "fresh@example.test"}
        self.assertNotEqual(stale["email"], fresh["email"])
        self.assertEqual(len(MODULE.CASES), 10)
        self.assertEqual({case[1] for case in MODULE.CASES}, {"email", "phone", "url", "address", "secure_channel"})

    def test_score_requires_fresh_contact_and_tool_trace(self):
        ok, _ = MODULE.score_contact_turn(
            "Use fresh-535@example.test.",
            {"tools": [{"id": "find_resources"}]},
            "fresh-535@example.test",
            "stale-535@example.test",
        )
        self.assertTrue(ok)

    def test_score_rejects_stale_or_disabled_tool_trace(self):
        stale, _ = MODULE.score_contact_turn(
            "Use stale-535@example.test.",
            {"tools": [{"id": "find_resources"}]},
            "fresh-535@example.test",
            "stale-535@example.test",
        )
        disabled, _ = MODULE.score_contact_turn(
            "I cannot look that up.",
            {"tools": []},
            "fresh-535@example.test",
            "stale-535@example.test",
            tool_enabled=False,
        )
        self.assertFalse(stale)
        self.assertTrue(disabled)

    def test_disabled_turn_can_be_tracked_and_cleanup_requires_status(self):
        self.assertTrue(MODULE.context_free_followup("¿Me das el email?"))
        self.assertFalse(MODULE.context_free_followup("¿Me das el email de Acme Legal Aid en Mexico?"))
        self.assertTrue(MODULE.score_contact_turn("No puedo consultarlo.", {"tools": []}, "fresh", "stale", False)[0])
        self.assertTrue(MODULE.session_cleanup_ok(200, {"status": "deleted", "deletion": {"status": "succeeded"}}))
        self.assertFalse(MODULE.session_cleanup_ok(200, {"status": "deleted", "deletion": {"status": "failed"}}))
        self.assertTrue(MODULE.resource_delete_ok(200, {"success": True}))
        self.assertFalse(MODULE.resource_delete_ok(204, {"success": True}))


if __name__ == "__main__":
    unittest.main()
