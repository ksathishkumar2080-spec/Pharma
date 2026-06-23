"""Proxy compliance endpoints from dashboard."""
from services.compliance.router import router  # re-export

__all__ = ["router"]
