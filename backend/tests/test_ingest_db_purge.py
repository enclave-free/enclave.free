import importlib
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class IngestDbPurgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_uploads_dir = os.environ.get("UPLOADS_DIR")
        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "enclave.db")
        os.environ["UPLOADS_DIR"] = str(Path(self.tmp.name) / "uploads")

        import database
        import ingest_db

        self.database = importlib.reload(database)
        self.ingest_db = importlib.reload(ingest_db)
        self.database.init_schema()

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("UPLOADS_DIR", self._orig_uploads_dir)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: Optional[str]) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def test_purge_old_jobs_deletes_only_jobs_older_than_cutoff(self) -> None:
        old_job = "old-document-job"
        recent_job = "recent-document-job"
        self.ingest_db.create_job(old_job, "Old.md", "/uploads/old.md", "default")
        self.ingest_db.create_job(recent_job, "Recent.md", "/uploads/recent.md", "default")
        old_timestamp = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
        recent_timestamp = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")

        with self.database.get_cursor() as cursor:
            cursor.execute(
                "UPDATE ingest_jobs SET created_at = ? WHERE job_id = ?",
                (old_timestamp, old_job),
            )
            cursor.execute(
                "UPDATE ingest_jobs SET created_at = ? WHERE job_id = ?",
                (recent_timestamp, recent_job),
            )

        deleted = self.ingest_db.purge_old_jobs(days=30)

        self.assertEqual(deleted, 1)
        self.assertIsNone(self.ingest_db.get_job(old_job))
        self.assertIsNotNone(self.ingest_db.get_job(recent_job))


if __name__ == "__main__":
    unittest.main()
