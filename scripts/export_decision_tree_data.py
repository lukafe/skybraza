#!/usr/bin/env python3
"""
Gera public/static/data/decision_tree.json — perguntas × gatilhos × incisos por trilha.

Execute após alterar questionnaire.yaml ou COVERAGE_MATRIX:
  python scripts/export_decision_tree_data.py

O deploy Vercel usa vercel_public/; após gerar, execute também:
  python scripts/sync_vercel_public.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from matrix_loader import TRACK_IDS, build_incisos_matrix, build_mandatory_keys
from questionnaire_loader import get_blocks, get_questions


def _edges_for_question(q: dict[str, Any]) -> list[dict[str, Any]]:
    qtype = q.get("type")
    if q.get("audit_only"):
        return [
            {
                "condition": "—",
                "incisos": [],
                "note": "Não altera o conjunto de incisos do escopo IN 701. Serve para relatório, maturidade ou Jornada 2 (ex.: pentest, smart contract audit).",
            }
        ]

    if qtype == "yes_no":
        wt = [str(x) for x in (q.get("when_true") or [])]
        wf = [str(x) for x in (q.get("when_false") or [])]
        out: list[dict[str, Any]] = [
            {
                "condition": "Resposta: Sim",
                "incisos": wt,
                "note": "" if wt else "Não acrescenta incisos com «Sim».",
            },
            {
                "condition": "Resposta: Não",
                "incisos": wf,
                "note": "" if wf else "Não acrescenta incisos com «Não».",
            },
        ]
        return out

    if qtype == "single_choice":
        out = []
        for opt in q.get("options") or []:
            incs = [str(x) for x in (opt.get("add_incisos") or [])]
            oid = str(opt.get("id") or "")
            label = str(opt.get("label") or oid)
            out.append(
                {
                    "condition": f"Opção: «{label}» ({oid})",
                    "incisos": incs,
                    "note": "" if incs else "Esta opção não acrescenta incisos.",
                }
            )
        return out or [{"condition": "—", "incisos": [], "note": "Escolha única."}]

    if qtype == "multi_choice":
        out = []
        for opt in q.get("options") or []:
            incs = [str(x) for x in (opt.get("add_incisos") or [])]
            label = str(opt.get("label") or opt.get("id") or "")
            out.append(
                {
                    "condition": f"Se marcar «{label}»",
                    "incisos": incs,
                    "note": "Pode combinar várias opções; incisos são unidos.",
                }
            )
        return out or [{"condition": "—", "incisos": [], "note": "Múltipla escolha."}]

    if qtype == "text_short":
        return [
            {
                "condition": "Texto livre",
                "incisos": [],
                "note": "Não aciona incisos por si. Usado para contexto, narrativa e regras especiais (ex.: supressão do cluster de custódia na intermediária).",
            }
        ]

    return [{"condition": "—", "incisos": [], "note": ""}]


def main() -> int:
    track_labels = {
        "intermediaria": "Intermediária — modalidade I (Res. 520 arts. 6º–7º)",
        "custodiante": "Custodiante — modalidade II (arts. 8º–9º)",
        "corretora": "Corretora — intermediação e custódia (art. 10)",
    }

    data: dict[str, Any] = {
        "version": 1,
        "tracks": {},
        "notes": {
            "suppress_custody_non_custodial": (
                "Em qualquer trilha, se o modelo declarado for exclusivamente não custodial — intermediária: P1 = Não, "
                "P_arch = client_only, P_tp sem custody_inst; custodiante: cust_A_model = client_only, cust_A_transit = Não, "
                "cust_B_tp sem subcustody; corretora: corr_A_model = client_only, corr_A_transit = Não, corr_B_tp sem subcustody — "
                "o motor remove VII, XIV, XVI e XVII do escopo. Nas trilhas custodiante e corretora remove também XV. "
                "Regra: scope_narrative.suppress_custody_cluster_if_non_custodial. Respostas contraditórias (ex.: trânsito Sim com "
                "«Apenas o cliente») devem ser corrigidas pelo utilizador; não há resolução automática de conflito."
            ),
        },
    }

    for tr in sorted(TRACK_IDS):
        mat = build_incisos_matrix(tr)
        mand = sorted(build_mandatory_keys(tr))
        inc_cat = {
            k: {"item": str(mat[k].get("item", "")), "artigo": str(mat[k].get("artigo_in701", ""))}
            for k in mat
        }
        blocks = get_blocks(tr)
        qs = get_questions(tr)
        questions = []
        for q in qs:
            text = q.get("text") or ""
            if isinstance(text, str):
                text = text.strip()
            just = q.get("justificativa") or ""
            if isinstance(just, str):
                just = just.strip()
            questions.append(
                {
                    "id": q["id"],
                    "block": q.get("block"),
                    "order": q.get("order", 0),
                    "type": q.get("type"),
                    "text": text,
                    "justificativa": just,
                    "audit_only": bool(q.get("audit_only")),
                    "edges": _edges_for_question(q),
                }
            )

        data["tracks"][tr] = {
            "label": track_labels.get(tr, tr),
            "blocks": [
                {
                    "id": b["id"],
                    "title": b.get("title", ""),
                    "lead": (b.get("lead") or "").strip() if isinstance(b.get("lead"), str) else "",
                }
                for b in blocks
            ],
            "mandatory_incisos": mand,
            "incisos_catalog": inc_cat,
            "questions": questions,
        }

    out_path = ROOT / "public" / "static" / "data" / "decision_tree.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
