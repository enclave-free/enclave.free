from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from coincurve import PrivateKey


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class SessionLogsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "enclave.db"
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        os.environ["SQLITE_PATH"] = str(self.db_path)

        import database
        import encryption
        import session_logs

        self.database = importlib.reload(database)
        self.encryption = importlib.reload(encryption)
        self.session_logs = importlib.reload(session_logs)
        self.database.init_schema()

        admin_key = PrivateKey()
        self.admin_private_key = admin_key.secret
        self.admin_pubkey = admin_key.public_key.format(compressed=True)[1:].hex()
        self.database.add_admin(self.admin_pubkey)

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        if self._orig_sqlite_path is None:
            os.environ.pop("SQLITE_PATH", None)
        else:
            os.environ["SQLITE_PATH"] = self._orig_sqlite_path
        self.tmp.cleanup()

    def transcript_files(self) -> list[Path]:
        transcript_dir = Path(self.tmp.name) / "session_logs"
        return sorted(transcript_dir.glob("*.json")) if transcript_dir.exists() else []

    def clear_admins(self) -> None:
        with self.database.get_cursor() as cursor:
            cursor.execute("DELETE FROM admins")

    def test_saving_missing_session_log_leaves_no_transcript_artifact(self) -> None:
        turns = [
            {"role": "user", "content": "please help me test this instance"},
            {"role": "assistant", "content": "I can help with that."},
        ]

        with self.assertRaises(KeyError):
            self.session_logs.save_transcript("missing-log-id", turns, created_by="admin")

        self.assertEqual(self.transcript_files(), [])

    def test_no_admin_config_fails_closed_for_transcripts_and_feedback_comments(self) -> None:
        self.clear_admins()
        no_admin_log = self.session_logs.create_session_log(title="No admin transcript")

        with self.assertRaises(ValueError):
            self.session_logs.save_transcript(
                no_admin_log["log_id"],
                [
                    {"role": "user", "content": "please help me test this instance"},
                    {"role": "assistant", "content": "I can help with that."},
                ],
            )

        self.assertEqual(self.transcript_files(), [])
        no_admin_metadata = self.session_logs.get_session_log_metadata(no_admin_log["log_id"])
        self.assertIsNotNone(no_admin_metadata)
        self.assertFalse(no_admin_metadata["has_transcript"])

        self.database.add_admin(self.admin_pubkey)
        feedback_log = self.session_logs.create_session_log(title="Feedback without admin")
        self.session_logs.save_transcript(
            feedback_log["log_id"],
            [
                {"role": "user", "content": "please help me test this instance"},
                {"role": "assistant", "content": "I can help with that."},
            ],
        )
        self.clear_admins()

        with self.assertRaises(ValueError):
            self.session_logs.set_turn_feedback(
                feedback_log["log_id"],
                1,
                "up",
                comment="This plaintext note must not be stored without an admin key.",
            )

        self.assertEqual(self.session_logs.list_feedback(feedback_log["log_id"]), [])

    def test_feedback_rejects_user_turns(self) -> None:
        log = self.session_logs.create_session_log(title="Synthetic User test")
        self.session_logs.save_transcript(
            log["log_id"],
            [
                {"role": "user", "content": "please help me test this instance"},
                {"role": "assistant", "content": "I can help with that."},
            ],
            created_by="admin",
        )

        with self.assertRaises(ValueError):
            self.session_logs.set_turn_feedback(
                log["log_id"],
                0,
                "down",
                comment="This should not be ratable because it was the user turn.",
                created_by="admin",
            )

    def test_feedback_accepts_assistant_turns_with_encrypted_comments(self) -> None:
        transcript_sentinel = "assistant turn feedback transcript sentinel"
        comment_sentinel = "this assistant answer missed the key safety constraint"
        log = self.session_logs.create_session_log(title="Synthetic User test")
        self.session_logs.save_transcript(
            log["log_id"],
            [
                {"role": "user", "content": "please help me test this instance"},
                {"role": "assistant", "content": transcript_sentinel},
            ],
            created_by="admin",
        )

        feedback = self.session_logs.set_turn_feedback(
            log["log_id"],
            1,
            "down",
            comment=comment_sentinel,
            created_by="admin",
        )

        self.assertEqual(feedback["turn_index"], 1)
        self.assertEqual(feedback["rating"], "down")
        self.assertIsNotNone(feedback["comment_ciphertext"])
        self.assertNotIn(comment_sentinel, feedback["comment_ciphertext"])
        detail = self.session_logs.get_session_log(log["log_id"])
        self.assertIsNotNone(detail)
        self.assertNotIn(transcript_sentinel, detail["transcript_ciphertext"])
        with self.database.get_cursor() as cursor:
            cursor.execute(
                "SELECT transcript_ciphertext FROM session_logs WHERE log_id = ?",
                (log["log_id"],),
            )
            stored = cursor.fetchone()["transcript_ciphertext"]
        self.assertEqual(stored, detail["transcript_ciphertext"])
        self.assertNotIn(transcript_sentinel, stored)
        decrypted_transcript = self.encryption.nip04_decrypt(
            detail["transcript_ciphertext"],
            detail["transcript_ephemeral_pubkey"],
            self.admin_private_key,
        )
        self.assertEqual(json.loads(decrypted_transcript)["turns"][1]["content"], transcript_sentinel)

    def test_feedback_rejects_missing_turn_indexes(self) -> None:
        log = self.session_logs.create_session_log(title="Synthetic User test")
        self.session_logs.save_transcript(
            log["log_id"],
            [
                {"role": "user", "content": "please help me test this instance"},
                {"role": "assistant", "content": "I can help with that."},
            ],
            created_by="admin",
        )

        for turn_index in (-1, 2, 999):
            with self.subTest(turn_index=turn_index):
                with self.assertRaises(ValueError):
                    self.session_logs.set_turn_feedback(log["log_id"], turn_index, "up")

    def test_session_log_export_returns_zip_and_audits_copied_export(self) -> None:
        transcript_sentinel = "export transcript plaintext sentinel"
        comment_sentinel = "Useful answer"
        log = self.session_logs.create_session_log(title="Synthetic User export")
        self.session_logs.save_transcript(
            log["log_id"],
            [
                {"role": "user", "content": "Please test export."},
                {"role": "assistant", "content": transcript_sentinel},
            ],
            created_by="admin-pubkey",
        )
        self.session_logs.set_turn_feedback(
            log["log_id"],
            1,
            "up",
            comment=comment_sentinel,
            created_by="admin-pubkey",
        )

        filename, payload = self.session_logs.export_session_log_zip(
            log["log_id"],
            changed_by="admin-pubkey",
        )

        self.assertTrue(filename.startswith("test_feedback_"))
        self.assertTrue(filename.endswith(".zip"))
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            self.assertEqual(
                sorted(archive.namelist()),
                ["feedback.json", "metadata.json", "transcript.nip04.txt"],
            )
            metadata = json.loads(archive.read("metadata.json").decode("utf-8"))
            feedback = json.loads(archive.read("feedback.json").decode("utf-8"))
            ciphertext = archive.read("transcript.nip04.txt").decode("utf-8")

        self.assertEqual(metadata["log_id"], log["log_id"])
        self.assertEqual(metadata["title"], "Synthetic User export")
        self.assertTrue(metadata["copied_export"])
        self.assertIsNotNone(metadata["transcript_ephemeral_pubkey"])
        self.assertEqual(metadata["encrypted_to_pubkey"], self.admin_pubkey)
        self.assertEqual(feedback[0]["turn_index"], 1)
        self.assertEqual(feedback[0]["rating"], "up")
        self.assertNotIn(comment_sentinel, json.dumps(feedback))
        self.assertNotIn(transcript_sentinel, ciphertext)

        entries = self.database.get_config_audit_log(limit=1, table_name="data_deletion")
        self.assertEqual(entries[0]["config_key"], "copied_export:test_feedback_session")
        event = json.loads(entries[0]["new_value"])
        self.assertEqual(event["workflow"], "copied_export")
        self.assertEqual(event["target"], "test_feedback_session")
        self.assertEqual(event["log_id"], log["log_id"])

    def test_delete_keeps_metadata_when_transcript_file_removal_fails(self) -> None:
        log = self.session_logs.create_session_log(title="Synthetic User delete")
        self.session_logs.save_transcript(
            log["log_id"],
            [
                {"role": "user", "content": "Please test delete."},
                {"role": "assistant", "content": "Delete test answer."},
            ],
            created_by="admin",
        )

        with patch.object(self.session_logs.os, "remove", side_effect=OSError("locked")):
            with self.assertRaises(OSError):
                self.session_logs.delete_session_log(log["log_id"])

        self.assertIsNotNone(self.session_logs.get_session_log_metadata(log["log_id"]))


if __name__ == "__main__":
    unittest.main()
