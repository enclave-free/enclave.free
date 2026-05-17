from __future__ import annotations

import asyncio
import importlib
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class FakeValkey:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expirations[key] = seconds

    async def ping(self) -> bool:
        return True


class RateLimitTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_backend = os.environ.get("RATE_LIMIT_BACKEND")
        self._orig_url = os.environ.get("RATE_LIMIT_VALKEY_URL")
        import rate_limit

        self.rate_limit = importlib.reload(rate_limit)

    def tearDown(self) -> None:
        self._restore_env("RATE_LIMIT_BACKEND", self._orig_backend)
        self._restore_env("RATE_LIMIT_VALKEY_URL", self._orig_url)
        self.rate_limit._VALKEY_CLIENT = None

    @staticmethod
    def _restore_env(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    @staticmethod
    def _request(host: str = "127.0.0.1"):
        return SimpleNamespace(
            client=SimpleNamespace(host=host),
            headers={},
            cookies={},
        )

    def test_memory_backend_limits_within_one_process(self) -> None:
        os.environ["RATE_LIMIT_BACKEND"] = "memory"
        limiter = self.rate_limit.RateLimiter(limit=2, window_seconds=60)
        request = self._request()

        asyncio.run(limiter(request))
        asyncio.run(limiter(request))

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(limiter(request))
        self.assertEqual(raised.exception.status_code, 429)

    def test_valkey_backend_uses_shared_counter(self) -> None:
        os.environ["RATE_LIMIT_BACKEND"] = "valkey"
        fake_valkey = FakeValkey()
        self.rate_limit._VALKEY_CLIENT = fake_valkey
        limiter = self.rate_limit.RateLimiter(limit=2, window_seconds=60)
        request = self._request()

        asyncio.run(limiter(request))
        asyncio.run(limiter(request))

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(limiter(request))
        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(len(fake_valkey.counts), 1)
        self.assertEqual(next(iter(fake_valkey.counts.values())), 3)
        self.assertEqual(next(iter(fake_valkey.expirations.values())), 61)

    def test_valkey_backend_fails_closed_when_unavailable(self) -> None:
        class BrokenValkey:
            async def incr(self, _key: str) -> int:
                raise RuntimeError("unavailable")

        os.environ["RATE_LIMIT_BACKEND"] = "valkey"
        self.rate_limit._VALKEY_CLIENT = BrokenValkey()
        limiter = self.rate_limit.RateLimiter(limit=2, window_seconds=60)

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(limiter(self._request()))
        self.assertEqual(raised.exception.status_code, 503)

    def test_backend_status_reports_healthy_valkey(self) -> None:
        os.environ["RATE_LIMIT_BACKEND"] = "valkey"
        self.rate_limit._VALKEY_CLIENT = FakeValkey()

        status = asyncio.run(self.rate_limit.rate_limit_backend_status())

        self.assertEqual(status["backend"], "valkey")
        self.assertEqual(status["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
