"""
Fase C — carrega laws/questionnaire.yaml e resolve gatilhos por tipo de pergunta.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from matrix_loader import INCISOS_MATRIX

PACKAGE_ROOT = Path(__file__).resolve().parent
QUESTIONNAIRE_PATH = PACKAGE_ROOT / "laws" / "questionnaire.yaml"


class QuestionnaireLoadError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _raw_questionnaire() -> dict[str, Any]:
    if not QUESTIONNAIRE_PATH.is_file():
        raise QuestionnaireLoadError(f"Questionário não encontrado: {QUESTIONNAIRE_PATH}")
    with QUESTIONNAIRE_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "questions" not in data:
        raise QuestionnaireLoadError("questionnaire.yaml inválido.")
    return data


def get_blocks() -> list[dict[str, Any]]:
    data = _raw_questionnaire()
    blocks = data.get("blocks") or []
    if not isinstance(blocks, list):
        return []
    return [dict(b) for b in blocks]


def get_questions() -> list[dict[str, Any]]:
    """Lista de perguntas com metadados (cópia segura)."""
    data = _raw_questionnaire()
    return [deepcopy(q) for q in data["questions"]]


def all_question_ids() -> list[str]:
    return [str(q["id"]) for q in get_questions()]


def questions_by_block() -> dict[str, list[dict[str, Any]]]:
    blocks_order = [b["id"] for b in get_blocks()]
    bucket: dict[str, list[dict[str, Any]]] = {bid: [] for bid in blocks_order}
    for q in sorted(get_questions(), key=lambda x: (x.get("block", "Z"), x.get("order", 0))):
        bid = q.get("block", "A")
        if bid not in bucket:
            bucket[bid] = []
        bucket[bid].append(q)
    return bucket


def _coerce_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    if isinstance(val, str):
        return val.strip().lower() in ("sim", "s", "yes", "true", "1")
    return bool(val)


def _validate_incisos(incs: list[str], ctx: str) -> None:
    for k in incs:
        if k not in INCISOS_MATRIX:
            raise QuestionnaireLoadError(f"{ctx}: inciso desconhecido '{k}'")


def validate_questionnaire_against_matrix() -> list[str]:
    warnings: list[str] = []
    for q in get_questions():
        qid = q["id"]
        t = q.get("type")
        if t == "yes_no":
            _validate_incisos(list(q.get("when_true") or []), qid)
            _validate_incisos(list(q.get("when_false") or []), qid)
        elif t == "single_choice":
            for opt in q.get("options") or []:
                _validate_incisos(list(opt.get("add_incisos") or []), f"{qid}.{opt.get('id')}")
        elif t == "multi_choice":
            for opt in q.get("options") or []:
                _validate_incisos(list(opt.get("add_incisos") or []), f"{qid}.{opt.get('id')}")
    return warnings


def potential_triggers_per_inciso() -> dict[str, list[str]]:
    """
    Para cada id de inciso na matriz, indicações de que respostas/opções podem acioná-lo
    (útil para explicar por que um inciso está fora do escopo atual).
    """
    rev: dict[str, list[str]] = {}
    for q in get_questions():
        if q.get("audit_only"):
            continue
        qid = str(q["id"])
        t = q.get("type")
        if t == "yes_no":
            for inc in q.get("when_true") or []:
                rev.setdefault(str(inc), []).append(f"{qid} = Sim")
            for inc in q.get("when_false") or []:
                if inc:
                    rev.setdefault(str(inc), []).append(f"{qid} = Não")
        elif t == "single_choice":
            for opt in q.get("options") or []:
                oid = str(opt.get("id") or "")
                label = str(opt.get("label") or oid)[:80]
                for inc in opt.get("add_incisos") or []:
                    rev.setdefault(str(inc), []).append(f"{qid} → opção «{label}»")
        elif t == "multi_choice":
            for opt in q.get("options") or []:
                oid = str(opt.get("id") or "")
                label = str(opt.get("label") or oid)[:80]
                for inc in opt.get("add_incisos") or []:
                    rev.setdefault(str(inc), []).append(f"{qid} inclui «{label}»")
    for k in rev:
        rev[k] = sorted(set(rev[k]))
    return rev


def build_yes_no_trigger_map() -> dict[str, frozenset[str]]:
    """Compatível com testes legados (apenas perguntas yes_no → when_true)."""
    out: dict[str, frozenset[str]] = {}
    for q in get_questions():
        if q.get("type") == "yes_no" and not q.get("audit_only"):
            out[str(q["id"])] = frozenset(str(x) for x in (q.get("when_true") or []))
    return out


def normalize_answers(answers: dict[str, Any]) -> dict[str, Any]:
    """Normaliza valores por tipo para cada pergunta conhecida; repassa chaves extra sem alterar."""
    out: dict[str, Any] = {}
    qmap = {q["id"]: q for q in get_questions()}
    for qid, q in qmap.items():
        raw = answers.get(qid)
        t = q.get("type")
        if t == "yes_no":
            out[qid] = _coerce_bool(raw)
        elif t == "single_choice":
            out[qid] = (raw.strip() if isinstance(raw, str) else raw) or None
        elif t == "multi_choice":
            if raw is None:
                out[qid] = []
            elif isinstance(raw, list):
                out[qid] = [str(x) for x in raw]
            elif isinstance(raw, str) and raw.strip():
                out[qid] = [s.strip() for s in raw.split(",") if s.strip()]
            else:
                out[qid] = []
        elif t == "text_short":
            s = raw if isinstance(raw, str) else ("" if raw is None else str(raw))
            mx = int(q.get("max_length") or 4000)
            out[qid] = s[:mx]
        else:
            out[qid] = raw
    for k, v in answers.items():
        if k not in out:
            out[k] = v
    return out


def resolve_triggers(answers: dict[str, Any]) -> tuple[dict[str, list[str]], dict[str, str], dict[str, bool]]:
    """
    Retorna:
      triggered_by: inciso -> lista de question_ids que contribuíram
      free_text: id -> texto (text_short)
      audit_only: id -> bool (respostas só para relatório)
    """
    norm = normalize_answers(answers)
    triggered_by: dict[str, list[str]] = {}
    free_text: dict[str, str] = {}
    audit_only: dict[str, bool] = {}

    for q in get_questions():
        qid = str(q["id"])
        t = q.get("type")
        if q.get("audit_only"):
            if t == "yes_no":
                audit_only[qid] = bool(norm.get(qid))
            continue

        if t == "text_short":
            free_text[qid] = str(norm.get(qid) or "")
            continue

        if t == "yes_no":
            incs = list(q.get("when_true") or []) if norm.get(qid) else list(q.get("when_false") or [])
            for inc in incs:
                triggered_by.setdefault(inc, []).append(qid)

        elif t == "single_choice":
            val = norm.get(qid)
            if not val:
                continue
            for opt in q.get("options") or []:
                if opt.get("id") == val:
                    for inc in opt.get("add_incisos") or []:
                        triggered_by.setdefault(inc, []).append(qid)
                    break

        elif t == "multi_choice":
            chosen = set(norm.get(qid) or [])
            for opt in q.get("options") or []:
                oid = opt.get("id")
                if oid in chosen:
                    for inc in opt.get("add_incisos") or []:
                        triggered_by.setdefault(inc, []).append(qid)

    for k, vlist in list(triggered_by.items()):
        triggered_by[k] = sorted(set(vlist))

    return triggered_by, free_text, audit_only


# Validação na importação
_Q_WARN = validate_questionnaire_against_matrix()
QUESTIONS: list[dict[str, Any]] = get_questions()
TRIGGER_MAP: dict[str, frozenset[str]] = build_yes_no_trigger_map()

__all__ = [
    "QUESTIONNAIRE_PATH",
    "QUESTIONS",
    "QuestionnaireLoadError",
    "TRIGGER_MAP",
    "all_question_ids",
    "build_yes_no_trigger_map",
    "get_blocks",
    "get_questions",
    "normalize_answers",
    "potential_triggers_per_inciso",
    "questions_by_block",
    "resolve_triggers",
]
