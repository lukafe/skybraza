"""
Confirma que os pacotes listados em [project.dependencies] do pyproject.toml
estão instalados no ambiente (após pip install -r requirements.txt).

Alinha CI com o conjunto mínimo que a Vercel instala via pyproject.
"""

from __future__ import annotations

import importlib.metadata
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"

# Nome PEP 503 normalizado -> nome a pedir ao importlib (alguns casos especiais)
_DIST_ALIASES = {
    "pyyaml": "PyYAML",
}


def _dep_project_name(line: str) -> str:
    line = line.split(";", 1)[0].strip()
    m = re.match(r"^([A-Za-z0-9_.-]+)", line)
    if not m:
        raise ValueError(f"Dependência inválida: {line!r}")
    return m.group(1)


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    deps: list[str] = data.get("project", {}).get("dependencies") or []
    if not deps:
        print("ERRO: pyproject sem [project.dependencies]")
        return 1
    missing: list[str] = []
    for line in deps:
        raw = _dep_project_name(line)
        candidates = [raw, _DIST_ALIASES.get(raw.lower(), raw)]
        ok = False
        for name in candidates:
            try:
                importlib.metadata.distribution(name)
                ok = True
                break
            except importlib.metadata.PackageNotFoundError:
                continue
        if not ok:
            missing.append(raw)
    if missing:
        print("Pacotes do pyproject.toml não encontrados no ambiente:")
        for m in missing:
            print(f"  - {m}")
        print("Execute: pip install -r requirements.txt")
        return 1
    print(f"OK: {len(deps)} dependência(s) de runtime do pyproject presentes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
