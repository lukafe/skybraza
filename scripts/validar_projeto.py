"""
Fase E — validação offline do projeto (matriz, questionário, motor, export JSON).

Execute na raiz: python scripts/validar_projeto.py
Exit code 0 = OK; 1 = falha.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    errors: list[str] = []

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    try:
        from bcb_hints_loader import missing_explicit_bcb_hints
        from evidence_requests import missing_evidence_yaml_incisos
        from matrix_loader import (
            INCISOS_MATRIX,
            TRACK_IDS,
            build_incisos_matrix,
            build_mandatory_keys,
            get_coverage_meta,
        )
        from questionnaire_loader import get_blocks, get_questions
        from readiness import build_export_package
        from rules_engine import compute_scope
        from scope_fixtures import maximize_scope_answers
    except Exception as e:
        print(f"ERRO de importação: {e}")
        return 1

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_public_bundle_sync",
        ROOT / "scripts" / "check_public_bundle_sync.py",
    )
    _sync_mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(_sync_mod)
    sync_errs = _sync_mod.compare_public_trees()
    for e in sync_errs:
        errors.append(f"[public↔vercel_public] {e}")

    dt_json = ROOT / "public" / "static" / "data" / "decision_tree.json"
    if not dt_json.is_file():
        errors.append(
            "Falta public/static/data/decision_tree.json — execute: python scripts/export_decision_tree_data.py"
        )
    else:
        try:
            dt_data = json.loads(dt_json.read_text(encoding="utf-8"))
            tr_map = dt_data.get("tracks") or {}
            for tr in sorted(TRACK_IDS):
                if tr not in tr_map:
                    errors.append(f"decision_tree.json sem trilha {tr!r}")
        except Exception as e:
            errors.append(f"decision_tree.json inválido: {e}")

    meta_yaml = get_coverage_meta()
    if meta_yaml.get("fase") != "E":
        errors.append(f"meta.fase esperado 'E', veio {meta_yaml.get('fase')!r}")

    for tr in sorted(TRACK_IDS):
        block_ids = {str(b["id"]) for b in get_blocks(tr)}
        for q in get_questions(tr):
            if str(q.get("block", "")) not in block_ids:
                errors.append(f"[{tr}] Pergunta {q['id']}: bloco inválido")

    for tr in sorted(TRACK_IDS):
        mat = build_incisos_matrix(tr)
        for k in build_mandatory_keys(tr):
            if k not in mat:
                errors.append(f"[{tr}] Obrigatório '{k}' ausente na matriz")

    for tr in sorted(TRACK_IDS):
        miss_hints = missing_explicit_bcb_hints(tr)
        if miss_hints:
            errors.append(f"BCB_REPORT_HINTS sem texto para incisos [{tr}]: {', '.join(miss_hints)}")

    miss_ev = missing_evidence_yaml_incisos()
    if miss_ev:
        errors.append(f"AUDITOR_EVIDENCE_BY_INCISO sem bloco para incisos: {', '.join(miss_ev)}")

    try:
        for tr in sorted(TRACK_IDS):
            mat_keys = set(build_incisos_matrix(tr).keys())
            df, meta = compute_scope(maximize_scope_answers(tr), track=tr)
            if meta["active_keys"] != mat_keys:
                errors.append(f"[{tr}] Escopo máximo não cobre todos os incisos da matriz")
            pack = build_export_package(
                institution="validar_projeto",
                meta=meta,
                scope_items=df.to_dict(orient="records"),
            )
            json.dumps(pack, ensure_ascii=True)
    except Exception as e:
        errors.append(f"Motor/exportação: {e}")

    if errors:
        print("Falhas:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("CertiK VASP — validação OK (Fase E)")
    print(f"  Incisos (intermediária): {len(INCISOS_MATRIX)}")
    for tr in sorted(TRACK_IDS):
        print(f"  Perguntas [{tr}]: {len(get_questions(tr))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
