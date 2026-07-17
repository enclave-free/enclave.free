#!/usr/bin/env python3
"""Verify the compiled frontend through its public HTTP interface."""

from __future__ import annotations

from html.parser import HTMLParser
import os
import urllib.error
import urllib.parse
import urllib.request
import unittest


BASE_URL = os.environ.get("FRONTEND_RUNTIME_URL", "http://127.0.0.1:55173").rstrip(
    "/"
)


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.assets: set[str] = set()

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        attribute_map = dict(attributes)
        candidate = attribute_map.get("src") if tag == "script" else None
        if tag == "link" and attribute_map.get("rel") == "stylesheet":
            candidate = attribute_map.get("href")
        if candidate and urllib.parse.urlparse(candidate).path.startswith("/assets/"):
            self.assets.add(candidate)


def fetch(path: str) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, dict(response.headers.items()), response.read()


class FrontendHttpContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        status, headers, body = fetch("/")
        cls.entry_status = status
        cls.entry_headers = headers
        cls.entry_body = body

    def test_root_is_compiled_refreshable_entry_document(self) -> None:
        self.assertEqual(self.entry_status, 200)
        self.assertIn("text/html", self.entry_headers["Content-Type"])
        self.assertIn("no-cache", self.entry_headers["Cache-Control"])
        self.assertNotIn("immutable", self.entry_headers["Cache-Control"])
        self.assertNotIn(b"/@vite/client", self.entry_body)
        self.assertNotIn(b"vite/client", self.entry_body)

    def test_direct_user_and_admin_routes_use_spa_fallback(self) -> None:
        for route in ("/login", "/admin/setup"):
            with self.subTest(route=route):
                status, headers, body = fetch(route)
                self.assertEqual(status, 200)
                self.assertIn("text/html", headers["Content-Type"])
                self.assertEqual(body, self.entry_body)

    def test_referenced_hashed_assets_are_immutable(self) -> None:
        parser = AssetParser()
        parser.feed(self.entry_body.decode("utf-8"))
        self.assertGreaterEqual(len(parser.assets), 2)

        for asset in parser.assets:
            with self.subTest(asset=asset):
                status, headers, body = fetch(asset)
                self.assertEqual(status, 200)
                self.assertGreater(len(body), 0)
                cache_control = headers["Cache-Control"]
                self.assertIn("public", cache_control)
                self.assertIn("max-age=31536000", cache_control)
                self.assertIn("immutable", cache_control)

    def test_frontend_does_not_claim_api_routing(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as raised:
            fetch("/api/health")
        self.assertEqual(raised.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
