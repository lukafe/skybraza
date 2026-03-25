"""
Ponto de entrada ASGI na raiz do repositório.

A Vercel referencia por vezes `api/index.py` como caminho e falha ao importar;
o detetor oficial aceita `index.py` na raiz com `app` (ver pyproject.toml).
"""

from api.index import app

__all__ = ["app"]
