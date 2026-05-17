from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]


class ConversationRetentionDocsTest(unittest.TestCase):
    def test_sessions_doc_states_visible_conversation_retention_semantics(self) -> None:
        sessions = (REPO_ROOT / "docs" / "sessions.md").read_text(encoding="utf-8")

        for expected in (
            "Opening, viewing, inspecting, exporting, or lifecycle scanning a Conversation does not refresh retention eligibility.",
            "last human or Sage assistant turn",
            "Admin Conversations and User Conversations use the same Conversation Content and Session Memory retention window.",
            "Expired or tombstoned Conversations disappear from ordinary conversation history.",
            "metadata-only",
            "former titles",
            "first-message summaries",
            "prompts",
            "tool outputs",
            "source snippets",
            "immediate user-facing status",
            "Admin-visible",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, sessions)


if __name__ == "__main__":
    unittest.main()
