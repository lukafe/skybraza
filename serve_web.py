"""
Inicia a aplicação web (FastAPI + front estático) e abre o navegador.

Execute sempre a partir da pasta do projeto, ou use este script com caminho absoluto:
  python serve_web.py

Requisitos: pip install -r requirements.txt
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "public" / "index.html"


def _pick_port(host: str = "127.0.0.1", start: int = 8000, attempts: int = 15) -> int | None:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    return None


def _open_later(url: str, delay: float = 1.5) -> None:
    time.sleep(delay)
    webbrowser.open(url)


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    if not INDEX.is_file():
        print(f"ERRO: Frontend não encontrado: {INDEX}")
        print("Confirme que a pasta 'public' está na raiz do projeto Certik_VASP.")
        sys.exit(1)

    try:
        import uvicorn
    except ImportError:
        print("ERRO: uvicorn não instalado.")
        print("Execute: python -m pip install -r requirements.txt")
        sys.exit(1)

    host = "127.0.0.1"
    port = _pick_port(host, 8000)
    if port is None:
        print("ERRO: Não foi possível reservar uma porta entre 8000 e 8014.")
        sys.exit(1)

    url = f"http://{host}:{port}"
    print("CertiK — Escopo IN 701 (web)")
    print(f"Pasta do projeto: {ROOT}")
    print(f"Servidor: {url}")
    print("Pressione Ctrl+C para encerrar.\n")

    threading.Thread(target=_open_later, args=(url,), daemon=True).start()

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
