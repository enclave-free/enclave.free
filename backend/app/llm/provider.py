"""
LLM Provider Base Class and Factory

Provides an abstract interface for the configured OpenAI-compatible LLM service.
"""

import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("sanctum.llm.provider")


@dataclass
class LLMResponse:
    """Unified response from the configured OpenAI-compatible LLM service."""
    content: str
    model: str
    provider: str
    usage: Optional[dict] = None


class LLMProvider(ABC):
    """Abstract base class for OpenAI-compatible LLM services."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Service identifier."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the service is reachable."""
        pass

    @abstractmethod
    def complete(self, prompt: str, model: Optional[str] = None, temperature: float = 0.1) -> LLMResponse:
        """Generate a completion from the given prompt."""
        pass


def get_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """
    Factory function to get the configured LLM service.

    Args:
        provider_name: Optional service name override.

    Returns:
        Configured LLMProvider instance.
    """
    requested = (provider_name or os.getenv("LLM_PROVIDER", "sage")).strip().lower()
    if requested not in {"", "sage", "maple"}:
        logger.warning("Unsupported LLM provider %r requested; forcing sage-compatible provider", requested)
        requested = "sage"

    from .sage_tinfoil import SageTinfoilProvider
    return SageTinfoilProvider(provider_name=requested or "sage")


def get_sage_provider() -> LLMProvider:
    """Explicit Sage/Tinfoil-compatible provider accessor."""
    return get_provider("sage")


def get_maple_provider() -> LLMProvider:
    """Deprecated compatibility accessor for old Maple-era imports."""
    return get_provider("maple")
