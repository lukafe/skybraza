#!/usr/bin/env python3
"""Fase 1 — valida laws/tracks/custodiante (matriz + questionário) sem carregar o motor legado."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "laws" / "tracks" / "custodiante" / "COVERAGE_MATRIX.yaml"
QUESTIONNAIRE_PATH = ROOT / "laws" / "tracks" / "custodiante" / "questionnaire.yaml"


def main() -> int:
    if not MATRIX_PATH.is_file():
        print(f"ERRO: matriz não encontrada: {MATRIX_PATH}", file=sys.stderr)
        return 1
    if not QUESTIONNAIRE_PATH.is_file():
        print(f"ERRO: questionário não encontrado: {QUESTIONNAIRE_PATH}", file=sys.stderr)
        return 1

    with MATRIX_PATH.open(encoding="utf-8") as f:
        matrix = yaml.safe_load(f)
    with QUESTIONNAIRE_PATH.open(encoding="utf-8") as f:
        quest = yaml.safe_load(f)

    if not isinstance(matrix, dict) or "incisos" not in matrix:
        print("ERRO: COVERAGE_MATRIX inválido (falta incisos).", file=sys.stderr)
        return 1

    inc_ids = {str(row["id"]) for row in matrix["incisos"] if isinstance(row, dict) and row.get("id")}
    esc = matrix.get("escopo_custodiante") or {}
    obrigatorios = [str(x) for x in (esc.get("obrigatorios") or [])]

    if not obrigatorios:
        print("ERRO: escopo_custodiante.obrigatorios vazio ou ausente.", file=sys.stderr)
        return 1

    err = 0
    for x in obrigatorios:
        if x not in inc_ids:
            print(f"ERRO: obrigatório '{x}' não existe em incisos[].id", file=sys.stderr)
            err += 1

    blocks = quest.get("blocks") or []
    block_ids = {str(b["id"]) for b in blocks if isinstance(b, dict) and b.get("id")}
    questions = quest.get("questions") or []

    qids: set[str] = set()
    for q in questions:
        if not isinstance(q, dict) or not q.get("id"):
            print("ERRO: pergunta sem id.", file=sys.stderr)
            err += 1
            continue
        qid = str(q["id"])
        if qid in qids:
            print(f"ERRO: id duplicado: {qid}", file=sys.stderr)
            err += 1
        qids.add(qid)

        b = q.get("block")
        if str(b) not in block_ids:
            print(f"ERRO: pergunta {qid} referencia block inexistente: {b}", file=sys.stderr)
            err += 1

        t = q.get("type")
        if t == "yes_no":
            for w in list(q.get("when_true") or []) + list(q.get("when_false") or []):
                ws = str(w)
                if ws and ws not in inc_ids:
                    print(f"ERRO: {qid} referencia inciso desconhecido: {ws}", file=sys.stderr)
                    err += 1
        elif t in ("single_choice", "multi_choice"):
            for opt in q.get("options") or []:
                if not isinstance(opt, dict):
                    continue
                oid = opt.get("id", "?")
                for inc in opt.get("add_incisos") or []:
                    ins = str(inc)
                    if ins not in inc_ids:
                        print(f"ERRO: {qid} opção {oid} — inciso desconhecido: {ins}", file=sys.stderr)
                        err += 1
        elif t == "text_short":
            pass
        else:
            print(f"AVISO: tipo não verificado: {qid} ({t})", file=sys.stderr)

    if err:
        return 1

    condicionais = sorted(inc_ids - set(obrigatorios))
    print("OK — trilha custodiante (Fase 1)")
    print(f"  Matriz: {MATRIX_PATH.relative_to(ROOT)}")
    print(f"  Questionário: {QUESTIONNAIRE_PATH.relative_to(ROOT)}")
    print(f"  Incisos na matriz: {len(inc_ids)} | Obrigatórios fixos: {len(obrigatorios)} | Perguntas: {len(questions)}")
    print(f"  Incisos só por gatilho (não na lista obrigatória): {', '.join(condicionais) or '—'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
