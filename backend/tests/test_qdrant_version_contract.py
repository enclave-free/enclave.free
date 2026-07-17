import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS_PATH = REPO_ROOT / "backend" / "requirements.txt"
INFRA_COMPOSE_PATH = REPO_ROOT / "docker-compose.infra.yml"


class QdrantVersionContractTest(unittest.TestCase):
    def test_python_client_tracks_the_pinned_server_minor(self) -> None:
        requirements = REQUIREMENTS_PATH.read_text()
        compose = INFRA_COMPOSE_PATH.read_text()

        server_match = re.search(
            r"^\s*image:\s*qdrant/qdrant:v(\d+)\.(\d+)\.(\d+)\s*$",
            compose,
            re.MULTILINE,
        )
        client_match = re.search(
            r"^qdrant-client>=(\d+)\.(\d+)\.(\d+),<(\d+)\.(\d+)\.(\d+)\s*$",
            requirements,
            re.MULTILINE,
        )

        self.assertIsNotNone(server_match, "Qdrant server must use a pinned image tag")
        self.assertIsNotNone(
            client_match,
            "qdrant-client must be bounded to one compatible minor release",
        )

        server_major, server_minor, _ = map(int, server_match.groups())
        lower_major, lower_minor, _, upper_major, upper_minor, upper_patch = map(
            int, client_match.groups()
        )

        self.assertEqual((lower_major, lower_minor), (server_major, server_minor))
        self.assertEqual(
            (upper_major, upper_minor, upper_patch),
            (server_major, server_minor + 1, 0),
        )


if __name__ == "__main__":
    unittest.main()
