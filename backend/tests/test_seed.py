from __future__ import annotations

import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class SeedSqliteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_sqlite_path = os.environ.get("SQLITE_PATH")
        self._orig_seed_demo_resources = os.environ.get("SEED_DEMO_RESOURCES")
        self._orig_qdrant_client = sys.modules.get("qdrant_client")
        self._orig_qdrant_models = sys.modules.get("qdrant_client.models")
        self._orig_store = sys.modules.get("store")

        os.environ["SQLITE_PATH"] = str(Path(self.tmp.name) / "enclave.db")
        os.environ.pop("SEED_DEMO_RESOURCES", None)
        sys.modules["qdrant_client"] = types.SimpleNamespace(QdrantClient=object)
        sys.modules["qdrant_client.models"] = types.SimpleNamespace(
            Distance=object,
            VectorParams=object,
            PointStruct=object,
        )
        sys.modules["store"] = types.SimpleNamespace(
            embed_texts=lambda *_args, **_kwargs: [],
            get_embedding_dimension=lambda: 384,
            EMBEDDING_MODEL="test",
            EMBEDDING_PROVIDER="test",
        )

        import database
        import seed

        self.database = importlib.reload(database)
        self.seed = importlib.reload(seed)

    def tearDown(self) -> None:
        if self.database._connection is not None:
            self.database._connection.close()
            self.database._connection = None
        self._restore_env("SQLITE_PATH", self._orig_sqlite_path)
        self._restore_env("SEED_DEMO_RESOURCES", self._orig_seed_demo_resources)
        self._restore_module("qdrant_client", self._orig_qdrant_client)
        self._restore_module("qdrant_client.models", self._orig_qdrant_models)
        self._restore_module("store", self._orig_store)
        self.tmp.cleanup()

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    @staticmethod
    def _restore_module(name: str, value: object | None) -> None:
        if value is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = value

    def _resource_count(self) -> int:
        with self.database.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS count FROM resources")
            return int(cursor.fetchone()["count"])

    def test_seed_sqlite_does_not_seed_demo_resources_by_default(self) -> None:
        self.seed.seed_sqlite()

        self.assertEqual(self._resource_count(), 0)

    def test_seed_sqlite_can_seed_demo_resources_by_flag(self) -> None:
        self.seed.seed_sqlite(seed_demo_resources=True)

        self.assertGreater(self._resource_count(), 0)

    def test_seed_sqlite_can_seed_demo_resources_by_env(self) -> None:
        os.environ["SEED_DEMO_RESOURCES"] = "true"

        self.seed.seed_sqlite()

        self.assertGreater(self._resource_count(), 0)


if __name__ == "__main__":
    unittest.main()
