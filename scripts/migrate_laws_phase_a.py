"""
Fase A: normaliza nomes de ficheiros em laws/ (extensão .txt, sem espaços).
Executar: python scripts/migrate_laws_phase_a.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAWS = ROOT / "laws"

# (origem relativa a laws/, destino)
MIGRATIONS: list[tuple[str, str]] = [
    ("IN701.TXT", "IN701-texto-integral.txt"),
    ("2-Art32_Art33.txt", "Res520-art32-33_IN701-art4-II.txt"),
    ("3-Art83", "Res520-art83_IN701-art4-III.txt"),
    ("5-Art 43", "Res520-art43_IN701-art4-V.txt"),
    ("6b-Art48.txt", "Res520-art48_IN701-art4-VI-b.txt"),
    ("9-b-Art65.txt", "Res520-art65_IN701-art4-IX-b.txt"),
    ("10b(ii)-Art69-Art85.txt", "Res520-art69-art85_IN701-art4-X-b.txt"),
    ("12-Cybersecurity_law.txt", "BCB-resolucao-ciberseguranca-nuvem_PT_IN701-art4-XII.txt"),
    ("14-Art73-Art75-Art78.txt", "Res520-art73-75-78_IN701-art4-XIV.txt"),
    ("15-Art76.txt", "Res520-art76_IN701-art4-XV.txt"),
]


def main() -> None:
    if not LAWS.is_dir():
        raise SystemExit(f"Pasta laws/ não encontrada: {LAWS}")

    for old_name, new_name in MIGRATIONS:
        src = LAWS / old_name
        dst = LAWS / new_name
        if not src.is_file():
            print(f"[SKIP] origem inexistente: {old_name}")
            continue
        if dst.is_file() and dst != src:
            print(f"[SKIP] destino já existe: {new_name}")
            continue
        shutil.copy2(src, dst)
        if src.resolve() != dst.resolve():
            src.unlink()
        print(f"[OK] {old_name} -> {new_name}")

    print("\nConcluído. Verifique laws/COVERAGE_MATRIX.yaml e STUB_*.txt.")


if __name__ == "__main__":
    main()
