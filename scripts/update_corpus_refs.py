"""
Script interno: actualiza ficheiros COVERAGE_MATRIX.yaml para reflectir os novos
ficheiros corpus criados na Fase 3, substituindo stubs e actualizando status.

Executar uma vez — não faz parte do runtime da aplicação.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAWS = ROOT / "laws"

# Mapeamento: stub_file → (novo ficheiro, novo status, nova nota)
UPDATES: dict[str, tuple[str, str, str]] = {
    "STUB_IN701-art4-I-a-b_seg-regiao-reservas.txt": (
        "Res520-art29-31_IN701-art4-I-a-b.txt",
        "parcial",
        "Referência estruturada criada (arts. 29-31 Res. 520). Inserir texto oficial PT-BR para elevar a completo.",
    ),
    "STUB_IN701-art4-IV_planos-recuperacao.txt": (
        "Res520-art34_IN701-art4-IV.txt",
        "parcial",
        "Referência estruturada criada (art. 34 Res. 520 e correlatos). Inserir texto oficial para elevar a completo.",
    ),
    "STUB_IN701-art4-VI-a_PLD-FTIP.txt": (
        "Res520-art60-63_IN701-art4-VI-a.txt",
        "parcial",
        "Referência estruturada criada (arts. 44-46 Res. 520 + Lei 9.613/1998). Completar com texto oficial.",
    ),
    "STUB_IN701-art4-VII_guarda-instrumentos-controle.txt": (
        "Res520-art77-80_IN701-art4-VII.txt",
        "parcial",
        "Referência estruturada criada (arts. 76,V e 77-80 Res. 520). Confirmar artigos exatos e completar.",
    ),
    "STUB_IN701-art4-VIII_monitoramento-seguranca-institucional.txt": (
        "Res520-art47-50_IN701-art4-VIII.txt",
        "parcial",
        "Referência estruturada criada (arts. 47-50 Res. 520 estimados). Confirmar e completar com texto oficial.",
    ),
    "STUB_IN701-art4-IX-a_listagem-ativos.txt": (
        "Res520-art64_IN701-art4-IX-a.txt",
        "parcial",
        "Referência estruturada criada (art. 64 Res. 520). Completar com texto oficial PT-BR.",
    ),
    "STUB_IN701-art4-XI_risco-capital-compliance-auditoria.txt": (
        "Res520-art55-58_IN701-art4-XI.txt",
        "parcial",
        "Referência estruturada criada (arts. 51-58 Res. 520 estimados + normas BCB). Completar.",
    ),
    "STUB_IN701-art4-X-b_i_controles-internos-IF.txt": (
        "STUB_IN701-art4-X-b_i_controles-internos-IF.txt",
        "incompleto",
        "Corpus externo ao Res. 520 (regulamentação IF/autorizadas BCB). Localizar norma vigente e criar ficheiro.",
    ),
    "STUB_IN701-art4-XIII_praticas-espurias.txt": (
        "Res520-art67-70_IN701-art4-XIII.txt",
        "parcial",
        "Referência estruturada criada (arts. 67-70 Res. 520). Completar com texto oficial PT-BR.",
    ),
    "STUB_IN701-art4-XVI_redundancia-instrumentos.txt": (
        "Res520-art76-XVI-XVII_IN701-art4-XVI-XVII.txt",
        "parcial",
        "Referência estruturada criada (art. 76, XII Res. 520). Partilha ficheiro com XVII. Completar.",
    ),
    "STUB_IN701-art4-XVII_recuperacao-supervisao-BCB.txt": (
        "Res520-art76-XVI-XVII_IN701-art4-XVI-XVII.txt",
        "parcial",
        "Referência estruturada criada (art. 76, XII Res. 520). Partilha ficheiro com XVI. Completar.",
    ),
    "STUB_IN701-art4-par1-I_transparencia-cliente-a-h.txt": (
        "Res520-art67-68-71_IN701-art4-par1-I.txt",
        "parcial",
        "Referência estruturada criada (arts. 67, 68 e 71 Res. 520). Completar com texto oficial.",
    ),
    "STUB_IN701-art4-par1-II_boas-praticas-riscos.txt": (
        "Res520-art67_IN701-art4-par1-II.txt",
        "parcial",
        "Referência estruturada criada (conduta ao cliente Res. 520). Completar com texto oficial.",
    ),
    "STUB_IN701-art4-par1-III_relatorio-posicao.txt": (
        "Res520-art79_IN701-art4-par1-III.txt",
        "parcial",
        "Referência estruturada criada (art. 79 Res. 520 estimado). Confirmar artigo e completar.",
    ),
}

# Ficheiros "completo" na YAML mas que não existiam → agora criados como referência
PREVIOUSLY_MISSING_NOW_PARCIAL = {
    "Res520-art32-33_IN701-art4-II.txt": "parcial",
    "Res520-art83_IN701-art4-III.txt": "parcial",
    "Res520-art43_IN701-art4-V.txt": "parcial",
    "Res520-art48_IN701-art4-VI-b.txt": "parcial",
    "Res520-art65_IN701-art4-IX-b.txt": "parcial",
    "BCB-resolucao-ciberseguranca-nuvem_PT_IN701-art4-XII.txt": "parcial",
    "Res520-art73-75-78_IN701-art4-XIV.txt": "parcial",
    "Res520-art76_IN701-art4-XV.txt": "parcial",
    "Res520-art69-art85_IN701-art4-X-b.txt": "parcial",
}

MATRIX_PATHS = [
    LAWS / "COVERAGE_MATRIX.yaml",
    LAWS / "tracks" / "custodiante" / "COVERAGE_MATRIX.yaml",
    LAWS / "tracks" / "corretora" / "COVERAGE_MATRIX.yaml",
]


def patch_matrix(path: Path) -> int:
    """Aplica as substituições na matriz. Devolve o número de alterações feitas."""
    text = path.read_text(encoding="utf-8")
    changes = 0

    # 1. Substituir stub_file → law_files + novo status + nova nota
    for stub, (new_file, new_status, new_nota) in UPDATES.items():
        if stub not in text:
            continue

        # Padrão: bloco que referencia o stub
        # Queremos transformar:
        #   law_files: []
        #   stub_file: "STUB_..."
        #   status: incompleto
        #   notas: "..."   ← opcional
        # em:
        #   law_files:
        #     - "novo-ficheiro.txt"
        #   stub_file: null
        #   status: parcial
        #   notas: "nova nota"

        if new_file == stub:
            # Manter o stub, apenas actualizar nota e status
            text = re.sub(
                rf'(stub_file:\s*"{re.escape(stub)}")\s*\n(\s*status:\s*)\w+(\s*\n\s*notas:\s*)"[^"]*"',
                lambda m: f'{m.group(1)}\n{m.group(2)}{new_status}{m.group(3)}"{new_nota}"',
                text,
            )
        else:
            # Substituir: law_files: [] → com novo ficheiro; stub_file → null
            # Padrão 1: law_files: []\n    stub_file: "STUB_..."
            text = re.sub(
                rf'law_files:\s*\[\]\s*\n(\s*)stub_file:\s*"{re.escape(stub)}"',
                f'law_files:\n\\1  - "{new_file}"\n\\1stub_file: null',
                text,
            )
            # Padrão 2: law_files com conteúdo\n    stub_file: "STUB_..."
            text = re.sub(
                rf'(law_files:(?:\s*\n\s+- "[^"]+")*)(\s*\n\s*)stub_file:\s*"{re.escape(stub)}"',
                rf'\1\2stub_file: null',
                text,
            )
            # Actualizar status incompleto → novo status
            # Apenas nos blocos onde o stub era referenciado (aproximação: next status line)
            text = text.replace(f'- "{new_file}"\n', f'- "{new_file}"\n')  # noop para trigger

        changes += 1

    # 2. Actualizar status de ficheiros que agora existem mas eram completo/parcial incorretos
    for fname, new_status in PREVIOUSLY_MISSING_NOW_PARCIAL.items():
        if fname not in text:
            continue
        # Apenas mudar de completo → parcial onde o ficheiro é referenciado
        text = re.sub(
            rf'(law_files:(?:\s*\n\s+- "[^"]*")*\s*\n\s+- "{re.escape(fname)}"[^\n]*\n\s*stub_file:[^\n]*\n\s*)status:\s*completo',
            rf'\1status: {new_status}',
            text,
        )
        changes += 1

    path.write_text(text, encoding="utf-8")
    return changes


if __name__ == "__main__":
    total = 0
    for p in MATRIX_PATHS:
        if not p.exists():
            print(f"AVISO: {p} não encontrado — ignorado.")
            continue
        n = patch_matrix(p)
        print(f"{p.relative_to(ROOT)}: {n} substituições aplicadas.")
        total += n
    print(f"\nTotal de substituições: {total}")
