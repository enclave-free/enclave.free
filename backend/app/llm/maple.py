"""Deprecated compatibility shim for old Maple-era imports."""

from .sage_tinfoil import SageTinfoilProvider


class MapleProvider(SageTinfoilProvider):
    """Legacy Maple identity wrapper around the Sage/Tinfoil provider."""

    def __init__(self, provider_name: str = "maple") -> None:
        super().__init__(provider_name=provider_name)

__all__ = ["MapleProvider", "SageTinfoilProvider"]
