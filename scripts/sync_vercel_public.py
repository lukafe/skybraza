"""Copia public/ -> vercel_public/ (cópia servida pela função Python na Vercel). Execute após alterar o frontend."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src, dst = ROOT / "public", ROOT / "vercel_public"
if dst.exists():
    shutil.rmtree(dst)
shutil.copytree(src, dst)
print(f"OK: {src} -> {dst}")
