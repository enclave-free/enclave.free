"""Deprecated compatibility shim for old Maple-era imports."""

from .sage_tinfoil import SageTinfoilProvider

MapleProvider = SageTinfoilProvider

__all__ = ["MapleProvider", "SageTinfoilProvider"]
