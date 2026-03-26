"""
Respostas de teste partilhadas — maximizam incisos condicionais por trilha.

Usado por tests/, scripts/validar_projeto.py e validações de integridade.
"""

from __future__ import annotations

from typing import Any

from matrix_loader import TRACK_DEFAULT, normalize_track
from questionnaire_loader import get_questions


def maximize_scope_answers(track: str | None = None) -> dict[str, Any]:
    """Para cada pergunta da trilha, escolhe valores que tendem a incluir o máximo de incisos no escopo."""
    t = normalize_track(track or TRACK_DEFAULT)
    out: dict[str, Any] = {}
    for q in get_questions(t):
        qid = q["id"]
        t = q.get("type")
        if t == "yes_no":
            out[qid] = True
        elif t == "single_choice":
            opts = q.get("options") or []
            if not opts:
                out[qid] = None
            else:
                best = max(opts, key=lambda o: len(o.get("add_incisos") or []))
                out[qid] = best["id"]
        elif t == "multi_choice":
            out[qid] = [str(o["id"]) for o in (q.get("options") or [])]
        elif t == "text_short":
            out[qid] = "validação integração"
        else:
            out[qid] = None
    return out


__all__ = ["maximize_scope_answers"]
