"""
OpenAI-Compatible LLM Provider

OpenAI-compatible provider for Sage/Tinfoil and legacy Maple-style runtimes.
"""

import os
import threading
from typing import Optional
import httpx
from openai import OpenAI

from .provider import LLMProvider, LLMResponse


class MapleProvider(LLMProvider):
    """
    Generic OpenAI-compatible endpoint used by the prototype backend's legacy
    utility endpoints. Despite the class name, this now supports Sage/Tinfoil
    config through the generic LLM_* keys as well as legacy MAPLE_* aliases.
    """

    def __init__(self, provider_name: str = "sage"):
        self._lock = threading.RLock()
        self.provider_name = provider_name if provider_name in {"sage", "maple"} else "sage"

        # Use config_loader for runtime config, with env fallback
        try:
            from config_loader import get_config
            self.base_url = get_config("LLM_API_URL") or get_config("MAPLE_BASE_URL") or "http://tinfoil-proxy:8089/v1"
            self.api_key = get_config("LLM_API_KEY") or get_config("MAPLE_API_KEY") or ""
            self.default_model = get_config("LLM_MODEL") or get_config("MAPLE_MODEL") or "kimi-k2-5"
        except ImportError:
            # Fallback to env vars if config_loader not available
            # Use same order as try block: LLM_* first, then MAPLE_*
            self.base_url = os.getenv("LLM_API_URL") or os.getenv("MAPLE_BASE_URL", "http://tinfoil-proxy:8089/v1")
            self.api_key = os.getenv("LLM_API_KEY") or os.getenv("MAPLE_API_KEY", "")
            self.default_model = os.getenv("LLM_MODEL") or os.getenv("MAPLE_MODEL", "kimi-k2-5")

        # Initialize OpenAI client with Maple endpoint
        self._init_client()

    def _init_client(self):
        """Initialize or reinitialize the OpenAI client"""
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "not-required"
        )

    def _refresh_config(self):
        """Refresh config from config_loader if available"""
        with self._lock:
            try:
                from config_loader import get_config
                new_base_url = get_config("LLM_API_URL") or get_config("MAPLE_BASE_URL") or self.base_url
                new_api_key = get_config("LLM_API_KEY") or get_config("MAPLE_API_KEY") or self.api_key
                new_model = get_config("LLM_MODEL") or get_config("MAPLE_MODEL") or self.default_model

                # Only reinitialize client if URL or key changed
                if new_base_url != self.base_url or new_api_key != self.api_key:
                    self.base_url = new_base_url
                    self.api_key = new_api_key
                    self._init_client()

                self.default_model = new_model
            except Exception as e:
                # Config loader unavailable or failed - keep existing config
                if not isinstance(e, ImportError):
                    import logging
                    logging.getLogger("sanctum.llm.maple").warning(f"Config refresh failed, using cached values: {e}")

    @property
    def name(self) -> str:
        return self.provider_name

    def health_check(self) -> bool:
        """Check an OpenAI-compatible runtime via /health or /v1/models."""
        try:
            base = self.base_url.replace("/v1", "")
            health_resp = httpx.get(f"{base}/health", timeout=5.0)
            if health_resp.status_code == 200:
                return True
        except Exception:
            pass

        try:
            models_resp = httpx.get(f"{self.base_url.rstrip('/')}/models", timeout=5.0)
            return models_resp.status_code == 200
        except Exception:
            return False

    def complete(self, prompt: str, model: Optional[str] = None, temperature: float = 0.1) -> LLMResponse:
        """
        Generate completion using a streaming OpenAI-compatible endpoint.
        """
        # Refresh config before each request to pick up runtime changes
        self._refresh_config()

        # Capture references under lock to avoid race conditions
        with self._lock:
            client = self.client
            model = model or self.default_model

        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            temperature=temperature,
        )

        # Collect streamed chunks
        content_parts = []
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content_parts.append(chunk.choices[0].delta.content)

        return LLMResponse(
            content="".join(content_parts),
            model=model,
            provider=self.name,
            usage=None  # Streaming doesn't provide usage stats
        )
