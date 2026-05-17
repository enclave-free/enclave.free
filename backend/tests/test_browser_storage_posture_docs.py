from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]


class BrowserStoragePostureDocsTest(unittest.TestCase):
    def test_browser_storage_posture_documents_allowlist_logout_and_cache_headers(self) -> None:
        doc = REPO_ROOT / "docs" / "browser-storage-posture.md"

        self.assertTrue(doc.exists())
        content = doc.read_text(encoding="utf-8")

        for expected in (
            "localStorage",
            "sessionStorage",
            "Conversation Content",
            "Deployment Surface",
            "clearLogoutBrowserStorage",
            "Cache-Control: no-store",
            "enclave-theme",
            "i18nextLng",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, content)


if __name__ == "__main__":
    unittest.main()
