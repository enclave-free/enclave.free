"""
Model Provider base class and compatibility factory.

Provides an abstract interface for the configured OpenAI-compatible Model
Provider path used by Python compatibility checks and legacy utility routes.
The LLM* names remain as public import compatibility aliases.
"""

import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("sanctum.llm.provider")


@dataclass
class LLMResponse:
    """Unified response from the configured OpenAI-compatible Model Provider."""
    content: str
    model: str
    provider: str
    usage: Optional[dict] = None


class LLMProvider(ABC):
    """Abstract base class for OpenAI-compatible Model Provider adapters."""

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


ModelProviderResponse = LLMResponse
ModelProvider = LLMProvider


def get_provider(provider_name: Optional[str] = None) -> ModelProvider:
    """
    Factory function to get the configured Model Provider adapter.

    Args:
        provider_name: Optional service name override.

    Returns:
        Configured ModelProvider instance.
    """
    requested = (provider_name or os.getenv("LLM_PROVIDER", "sage")).strip().lower()
    if requested not in {"", "sage", "maple"}:
        logger.warning("Unsupported Model Provider compatibility label %r requested; forcing sage-compatible provider", requested)
        requested = "sage"

    from .sage_tinfoil import SageTinfoilProvider
    return SageTinfoilProvider(provider_name=requested or "sage")


def get_sage_provider() -> ModelProvider:
    """Explicit Sage/Tinfoil-compatible provider accessor."""
    return get_provider("sage")


def get_maple_provider() -> ModelProvider:
    """Deprecated compatibility accessor for old Maple-era imports."""
    return get_provider("maple")
