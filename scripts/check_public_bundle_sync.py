"""
Garante que vercel_public/ é espelho byte-a-byte de public/ (deploy Vercel).

Execute na raiz: python scripts/check_public_bundle_sync.py
Exit code 0 = OK; 1 = dessincronizado.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
VERCEL_PUBLIC = ROOT / "vercel_public"


def _rel_files(root: Path) -> set[Path]:
    if not root.is_dir():
        return set()
    out: set[Path] = set()
    for p in root.rglob("*"):
        if p.is_file():
            out.add(p.relative_to(root))
    return out


def compare_public_trees() -> list[str]:
    errors: list[str] = []
    if not PUBLIC.is_dir():
        errors.append(f"Pasta ausente: {PUBLIC}")
        return errors
    if not VERCEL_PUBLIC.is_dir():
        errors.append(
            f"Pasta ausente: {VERCEL_PUBLIC} — execute: python scripts/sync_vercel_public.py"
        )
        return errors

    a = _rel_files(PUBLIC)
    b = _rel_files(VERCEL_PUBLIC)
    for rel in sorted(a - b):
        errors.append(f"Só em public/: {rel.as_posix()}")
    for rel in sorted(b - a):
        errors.append(f"Só em vercel_public/: {rel.as_posix()}")
    for rel in sorted(a & b):
        fa = PUBLIC / rel
        fb = VERCEL_PUBLIC / rel
        if fa.read_bytes() != fb.read_bytes():
            errors.append(f"Conteúdo diferente: {rel.as_posix()} — python scripts/sync_vercel_public.py")
    return errors


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    errs = compare_public_trees()
    if errs:
        print("vercel_public/ dessincronizado de public/:")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("OK: vercel_public/ espelha public/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
