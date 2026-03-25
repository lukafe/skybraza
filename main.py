"""Atalho local: mesma app que api.index (evita duplicar código)."""

from api.index import API_SCHEMA_VERSION, app

__all__ = ["app", "API_SCHEMA_VERSION"]
