"""
Compatibilidade: testes e `uvicorn api.index:app`.

A aplicação vive em `main.py` na raiz (entrypoint suportado pela Vercel).
"""

from main import API_SCHEMA_VERSION, app

__all__ = ["app", "API_SCHEMA_VERSION"]
