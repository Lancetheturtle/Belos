"""Uvicorn entry point: python -m uvicorn backend.main:app --port 8000."""

from .transport_api import app

__all__ = ["app"]
