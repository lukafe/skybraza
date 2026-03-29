"""
Actualiza status: incompleto → parcial para incisos que agora têm ficheiro real em laws/.
Opera directamente na string YAML para não alterar formatação geral.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAWS = ROOT / "laws"

MATRIX_PATHS = [
    LAWS / "COVERAGE_MATRIX.yaml",
    LAWS / "tracks" / "custodiante" / "COVERAGE_MATRIX.yaml",
    LAWS / "tracks" / "corretora" / "COVERAGE_MATRIX.yaml",
]

# Incisos cujos ficheiros foram criados e o status deve subir de incompleto → parcial
# (não inclui X_b_i que ainda usa stub)
PROMOTE_TO_PARCIAL = {
    "I_a", "I_b", "IV", "VI_a", "VII", "VIII", "IX_a", "XI", "XIII",
    "XVI", "XVII", "par1_I", "par1_II", "par1_III", "par1_I_h",
}

import re

for path in MATRIX_PATHS:
    if not path.exists():
        print(f"AVISO: {path} não encontrado")
        continue

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    new_lines = []
    current_id = None

    for i, line in enumerate(lines):
        # Detectar o id do inciso actual
        m = re.match(r'\s+- id:\s+(\S+)', line)
        if m:
            current_id = m.group(1)

        # Mudar status: incompleto → parcial para incisos elegíveis
        if current_id in PROMOTE_TO_PARCIAL:
            line = re.sub(r'^(\s+status:\s*)incompleto(\s*)$', r'\1parcial\2', line)

        new_lines.append(line)

    new_text = "".join(new_lines)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        print(f"Actualizado: {path.relative_to(ROOT)}")
    else:
        print(f"Sem alterações: {path.relative_to(ROOT)}")

print("Concluído.")
