#!/usr/bin/env python3
"""
Gera public/static/data/decision_tree.json — perguntas × gatilhos × incisos por trilha.
Inclui campos ``*_en`` para todos os textos visíveis, lidos de questions_en.json.

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

# ── English fallback strings ──────────────────────────────────────────────────
_NOTE_EN: dict[str, str] = {
    "audit_only": (
        "Does not change the IN 701 scope clause set. Used for report, maturity or "
        "Journey 2 (e.g. pentest, smart contract audit)."
    ),
    "yes_true_empty":  "Adds no clauses when 'Yes'.",
    "yes_false_empty": "Adds no clauses when 'No'.",
    "opt_empty":       "This option adds no clauses.",
    "multi_note":      "Multiple options can be combined; clauses are unioned.",
    "text_short": (
        "Does not trigger clauses on its own. Context and narrative; coherence with "
        "P_narr/cust_D_narr/corr_D_narr and human review. Custody-cluster suppression "
        "depends on other questions (P_arch/cust_A_model/corr_A_model, etc.)."
    ),
    "single_empty": "Single choice.",
    "multi_empty":  "Multiple choice.",
}

_TRACK_LABELS_EN: dict[str, str] = {
    "intermediaria": "Intermediary — modality I (Res. 520 arts. 6–7)",
    "custodiante":   "Custodian — modality II (arts. 8–9)",
    "corretora":     "Broker/Exchange — intermediation and custody (art. 10)",
}

_BLOCKS_KEY: dict[str, str] = {
    "intermediaria": "blocks",
    "custodiante":   "blocks_cust",
    "corretora":     "blocks_corr",
}


def _load_en_data() -> dict[str, Any]:
    path = ROOT / "public" / "static" / "data" / "questions_en.json"
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _edges_for_question(
    q: dict[str, Any],
    en_questions: dict[str, Any],
) -> list[dict[str, Any]]:
    qtype = q.get("type")
    qid   = q.get("id", "")
    en_q  = en_questions.get(qid, {})
    opts_en: dict[str, str] = en_q.get("options_en") or {}

    if q.get("audit_only"):
        return [
            {
                "condition":    "—",
                "condition_en": "—",
                "incisos":      [],
                "note": (
                    "Não altera o conjunto de incisos do escopo IN 701. Serve para "
                    "relatório, maturidade ou Jornada 2 (ex.: pentest, smart contract audit)."
                ),
                "note_en": _NOTE_EN["audit_only"],
            }
        ]

    if qtype == "yes_no":
        wt = [str(x) for x in (q.get("when_true") or [])]
        wf = [str(x) for x in (q.get("when_false") or [])]
        return [
            {
                "condition":    "Resposta: Sim",
                "condition_en": "Answer: Yes",
                "incisos":      wt,
                "note":    "" if wt else "Não acrescenta incisos com «Sim».",
                "note_en": "" if wt else _NOTE_EN["yes_true_empty"],
            },
            {
                "condition":    "Resposta: Não",
                "condition_en": "Answer: No",
                "incisos":      wf,
                "note":    "" if wf else "Não acrescenta incisos com «Não».",
                "note_en": "" if wf else _NOTE_EN["yes_false_empty"],
            },
        ]

    if qtype == "single_choice":
        out = []
        for opt in q.get("options") or []:
            incs  = [str(x) for x in (opt.get("add_incisos") or [])]
            oid   = str(opt.get("id") or "")
            label = str(opt.get("label") or oid)
            en_label = opts_en.get(oid) or label
            out.append(
                {
                    "condition":    f"Opção: «{label}» ({oid})",
                    "condition_en": f"Option: «{en_label}» ({oid})",
                    "incisos":      incs,
                    "note":    "" if incs else "Esta opção não acrescenta incisos.",
                    "note_en": "" if incs else _NOTE_EN["opt_empty"],
                }
            )
        if not out:
            return [{"condition": "—", "condition_en": "—", "incisos": [],
                     "note": "Escolha única.", "note_en": _NOTE_EN["single_empty"]}]
        return out

    if qtype == "multi_choice":
        out = []
        for opt in q.get("options") or []:
            incs  = [str(x) for x in (opt.get("add_incisos") or [])]
            oid   = str(opt.get("id") or "")
            label = str(opt.get("label") or oid)
            en_label = opts_en.get(oid) or label
            out.append(
                {
                    "condition":    f"Se marcar «{label}»",
                    "condition_en": f"If you select «{en_label}»",
                    "incisos":      incs,
                    "note":    "Pode combinar várias opções; incisos são unidos.",
                    "note_en": _NOTE_EN["multi_note"],
                }
            )
        if not out:
            return [{"condition": "—", "condition_en": "—", "incisos": [],
                     "note": "Múltipla escolha.", "note_en": _NOTE_EN["multi_empty"]}]
        return out

    if qtype == "text_short":
        return [
            {
                "condition":    "Texto livre",
                "condition_en": "Free text",
                "incisos":      [],
                "note": (
                    "Não aciona incisos por si. Contexto e narrativa; coerência com "
                    "P_narr/cust_D_narr/corr_D_narr e revisão humana. A supressão do "
                    "cluster de custódia depende de outras perguntas "
                    "(P_arch/cust_A_model/corr_A_model, etc.)."
                ),
                "note_en": _NOTE_EN["text_short"],
            }
        ]

    return [{"condition": "—", "condition_en": "—", "incisos": [],
             "note": "", "note_en": ""}]


def main() -> int:
    en_data    = _load_en_data()
    en_qs      = en_data.get("questions") or {}

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
        mat  = build_incisos_matrix(tr)
        mand = sorted(build_mandatory_keys(tr))
        inc_cat = {
            k: {"item": str(mat[k].get("item", "")), "artigo": str(mat[k].get("artigo_in701", ""))}
            for k in mat
        }
        blocks     = get_blocks(tr)
        qs         = get_questions(tr)
        en_blk_key = _BLOCKS_KEY.get(tr, "blocks")
        en_blocks  = en_data.get(en_blk_key) or {}

        questions = []
        for q in qs:
            text = (q.get("text") or "").strip() if isinstance(q.get("text"), str) else ""
            just = (q.get("justificativa") or "").strip() if isinstance(q.get("justificativa"), str) else ""
            qid  = q["id"]
            en_q = en_qs.get(qid) or {}
            questions.append(
                {
                    "id":             qid,
                    "block":          q.get("block"),
                    "order":          q.get("order", 0),
                    "type":           q.get("type"),
                    "text":           text,
                    "text_en":        en_q.get("text_en") or text,
                    "justificativa":  just,
                    "justificativa_en": en_q.get("justificativa_en") or just,
                    "audit_only":     bool(q.get("audit_only")),
                    "edges":          _edges_for_question(q, en_qs),
                }
            )

        data["tracks"][tr] = {
            "label":    "Intermediária — modalidade I (Res. 520 arts. 6º–7º)"
                        if tr == "intermediaria"
                        else ("Custodiante — modalidade II (arts. 8º–9º)"
                              if tr == "custodiante"
                              else "Corretora — intermediação e custódia (art. 10)"),
            "label_en": _TRACK_LABELS_EN.get(tr, tr),
            "blocks": [
                {
                    "id":       b["id"],
                    "title":    b.get("title", ""),
                    "title_en": (en_blocks.get(b["id"]) or {}).get("title_en") or b.get("title", ""),
                    "lead":     (b.get("lead") or "").strip() if isinstance(b.get("lead"), str) else "",
                    "lead_en":  (en_blocks.get(b["id"]) or {}).get("lead_en") or "",
                }
                for b in blocks
            ],
            "mandatory_incisos": mand,
            "incisos_catalog":   inc_cat,
            "questions":         questions,
        }

    out_path = ROOT / "public" / "static" / "data" / "decision_tree.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
