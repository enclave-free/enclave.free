"""
OpenAI-compatible provider for Sage/Tinfoil and legacy-compatible runtimes.

The current prototype routes public AI traffic through Sage and Tinfoil. The
Python control plane still uses this provider for legacy utility paths and
health checks. Generic LLM_* keys are canonical; MAPLE_* aliases are retained
only as deprecated compatibility fallbacks.
"""

import logging
import os
import threading
from typing import Optional

import httpx
from openai import OpenAI

from .provider import LLMProvider, LLMResponse

logger = logging.getLogger("sanctum.llm.sage_tinfoil")


class SageTinfoilProvider(LLMProvider):
    """Generic OpenAI-compatible endpoint used by Python compatibility paths."""

    def __init__(self, provider_name: str = "sage") -> None:
        self._lock = threading.RLock()
        self.provider_name = provider_name if provider_name in {"sage", "maple"} else "sage"

        try:
            from config_loader import get_config

            self.base_url = (
                get_config("LLM_API_URL")
                or get_config("MAPLE_BASE_URL")
                or "http://tinfoil-proxy:8089/v1"
            )
            self.api_key = get_config("LLM_API_KEY") or get_config("MAPLE_API_KEY") or ""
            self.default_model = get_config("LLM_MODEL") or get_config("MAPLE_MODEL") or "kimi-k2-6"
        except ImportError:
            self.base_url = os.getenv("LLM_API_URL") or os.getenv(
                "MAPLE_BASE_URL", "http://tinfoil-proxy:8089/v1"
            )
            self.api_key = os.getenv("LLM_API_KEY") or os.getenv("MAPLE_API_KEY", "")
            self.default_model = os.getenv("LLM_MODEL") or os.getenv("MAPLE_MODEL", "kimi-k2-6")

        self._init_client()

    def _init_client(self) -> None:
        """Initialize or reinitialize the OpenAI client."""
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key or "not-required")

    def _refresh_config(self) -> None:
        """Refresh config from config_loader if available."""
        with self._lock:
            try:
                from config_loader import get_config

                new_base_url = get_config("LLM_API_URL") or get_config("MAPLE_BASE_URL") or self.base_url
                new_api_key = get_config("LLM_API_KEY") or get_config("MAPLE_API_KEY") or self.api_key
                new_model = get_config("LLM_MODEL") or get_config("MAPLE_MODEL") or self.default_model

                if new_base_url != self.base_url or new_api_key != self.api_key:
                    self.base_url = new_base_url
                    self.api_key = new_api_key
                    self._init_client()

                self.default_model = new_model
            except Exception as exc:
                if not isinstance(exc, ImportError):
                    logger.warning("Config refresh failed, using cached values: %s", exc)

    @property
    def name(self) -> str:
        return self.provider_name

    def health_check(self) -> bool:
        """Check an OpenAI-compatible runtime via /health or /v1/models."""
        self._refresh_config()
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        base = self.base_url.rstrip("/")
        health_base = base[:-3] if base.endswith("/v1") else base

        try:
            health_resp = httpx.get(f"{health_base}/health", headers=headers, timeout=5.0)
            if health_resp.status_code == 200:
                return True
        except Exception:
            pass

        try:
            models_resp = httpx.get(f"{base}/models", headers=headers, timeout=5.0)
            return models_resp.status_code == 200
        except Exception:
            return False

    def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Generate completion using a streaming OpenAI-compatible endpoint."""
        self._refresh_config()

        with self._lock:
            client = self.client
            model = model or self.default_model

        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            temperature=temperature,
        )

        content_parts = []
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content_parts.append(chunk.choices[0].delta.content)

        return LLMResponse(
            content="".join(content_parts),
            model=model,
            provider=self.name,
            usage=None,
        )
