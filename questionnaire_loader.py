"""
Fase C — carrega questionário por trilha (intermediária | custodiante) e resolve gatilhos.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from matrix_loader import TRACK_DEFAULT, TRACK_IDS, build_incisos_matrix, normalize_track

PACKAGE_ROOT = Path(__file__).resolve().parent
QUESTIONNAIRE_PATH = PACKAGE_ROOT / "laws" / "questionnaire.yaml"

_QUESTIONNAIRE_PATH_BY_TRACK: dict[str, Path] = {
    "intermediaria": PACKAGE_ROOT / "laws" / "questionnaire.yaml",
    "custodiante": PACKAGE_ROOT / "laws" / "tracks" / "custodiante" / "questionnaire.yaml",
}


class QuestionnaireLoadError(RuntimeError):
    pass


@lru_cache(maxsize=len(TRACK_IDS))
def _raw_questionnaire(track: str) -> dict[str, Any]:
    t = normalize_track(track)
    path = _QUESTIONNAIRE_PATH_BY_TRACK[t]
    if not path.is_file():
        raise QuestionnaireLoadError(f"Questionário não encontrado (trilha {t}): {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "questions" not in data:
        raise QuestionnaireLoadError(f"questionnaire.yaml inválido (trilha {t}).")
    return data


def get_blocks(track: str | None = None) -> list[dict[str, Any]]:
    t = normalize_track(track)
    data = _raw_questionnaire(t)
    blocks = data.get("blocks") or []
    if not isinstance(blocks, list):
        return []
    return [dict(b) for b in blocks]


def get_questions(track: str | None = None) -> list[dict[str, Any]]:
    t = normalize_track(track)
    data = _raw_questionnaire(t)
    return [deepcopy(q) for q in data["questions"]]


def all_question_ids(track: str | None = None) -> list[str]:
    return [str(q["id"]) for q in get_questions(track)]


def questions_by_block(track: str | None = None) -> dict[str, list[dict[str, Any]]]:
    t = normalize_track(track)
    blocks_order = [b["id"] for b in get_blocks(t)]
    bucket: dict[str, list[dict[str, Any]]] = {bid: [] for bid in blocks_order}
    for q in sorted(get_questions(t), key=lambda x: (x.get("block", "Z"), x.get("order", 0))):
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


def _validate_incisos(incs: list[Any], ctx: str, track: str) -> None:
    mat = build_incisos_matrix(track)
    for k in incs:
        sk = str(k)
        if sk not in mat:
            raise QuestionnaireLoadError(f"{ctx}: inciso desconhecido '{k}' (trilha {track})")


def assert_questionnaire_incisos_align_with_matrix(track: str | None = None) -> None:
    t = normalize_track(track)
    for q in get_questions(t):
        qid = q["id"]
        qtype = q.get("type")
        if qtype == "yes_no":
            _validate_incisos(list(q.get("when_true") or []), str(qid), t)
            _validate_incisos(list(q.get("when_false") or []), str(qid), t)
        elif qtype == "single_choice":
            for opt in q.get("options") or []:
                _validate_incisos(list(opt.get("add_incisos") or []), f"{qid}.{opt.get('id')}", t)
        elif qtype == "multi_choice":
            for opt in q.get("options") or []:
                _validate_incisos(list(opt.get("add_incisos") or []), f"{qid}.{opt.get('id')}", t)


def potential_triggers_per_inciso(track: str | None = None) -> dict[str, list[str]]:
    t = normalize_track(track)
    rev: dict[str, list[str]] = {}
    for q in get_questions(t):
        if q.get("audit_only"):
            continue
        qid = str(q["id"])
        qtype = q.get("type")
        if qtype == "yes_no":
            for inc in q.get("when_true") or []:
                rev.setdefault(str(inc), []).append(f"{qid} = Sim")
            for inc in q.get("when_false") or []:
                if inc:
                    rev.setdefault(str(inc), []).append(f"{qid} = Não")
        elif qtype == "single_choice":
            for opt in q.get("options") or []:
                oid = str(opt.get("id") or "")
                label = str(opt.get("label") or oid)[:80]
                for inc in opt.get("add_incisos") or []:
                    rev.setdefault(str(inc), []).append(f"{qid} → opção «{label}»")
        elif qtype == "multi_choice":
            for opt in q.get("options") or []:
                oid = str(opt.get("id") or "")
                label = str(opt.get("label") or oid)[:80]
                for inc in opt.get("add_incisos") or []:
                    rev.setdefault(str(inc), []).append(f"{qid} inclui «{label}»")
    for k in rev:
        rev[k] = sorted(set(rev[k]))
    return rev


def build_yes_no_trigger_map(track: str | None = None) -> dict[str, frozenset[str]]:
    t = normalize_track(track)
    out: dict[str, frozenset[str]] = {}
    for q in get_questions(t):
        if q.get("type") == "yes_no" and not q.get("audit_only"):
            out[str(q["id"])] = frozenset(str(x) for x in (q.get("when_true") or []))
    return out


def normalize_answers(answers: dict[str, Any], track: str | None = None) -> dict[str, Any]:
    t = normalize_track(track)
    out: dict[str, Any] = {}
    qmap = {q["id"]: q for q in get_questions(t)}
    for qid, q in qmap.items():
        raw = answers.get(qid)
        qtype = q.get("type")
        if qtype == "yes_no":
            out[qid] = _coerce_bool(raw)
        elif qtype == "single_choice":
            out[qid] = (raw.strip() if isinstance(raw, str) else raw) or None
        elif qtype == "multi_choice":
            if raw is None:
                out[qid] = []
            elif isinstance(raw, list):
                out[qid] = [str(x) for x in raw]
            elif isinstance(raw, str) and raw.strip():
                out[qid] = [s.strip() for s in raw.split(",") if s.strip()]
            else:
                out[qid] = []
        elif qtype == "text_short":
            s = raw if isinstance(raw, str) else ("" if raw is None else str(raw))
            mx = int(q.get("max_length") or 4000)
            out[qid] = s[:mx]
        else:
            out[qid] = raw
    for k, v in answers.items():
        if k not in out:
            out[k] = v
    return out


def resolve_triggers(
    answers: dict[str, Any], track: str | None = None
) -> tuple[dict[str, list[str]], dict[str, str], dict[str, bool]]:
    t = normalize_track(track)
    norm = normalize_answers(answers, t)
    triggered_by: dict[str, list[str]] = {}
    free_text: dict[str, str] = {}
    audit_only: dict[str, bool] = {}

    for q in get_questions(t):
        qid = str(q["id"])
        qtype = q.get("type")
        if q.get("audit_only"):
            if qtype == "yes_no":
                audit_only[qid] = bool(norm.get(qid))
            continue

        if qtype == "text_short":
            free_text[qid] = str(norm.get(qid) or "")
            continue

        if qtype == "yes_no":
            incs = list(q.get("when_true") or []) if norm.get(qid) else list(q.get("when_false") or [])
            for inc in incs:
                triggered_by.setdefault(str(inc), []).append(qid)

        elif qtype == "single_choice":
            val = norm.get(qid)
            if not val:
                continue
            for opt in q.get("options") or []:
                if opt.get("id") == val:
                    for inc in opt.get("add_incisos") or []:
                        triggered_by.setdefault(str(inc), []).append(qid)
                    break

        elif qtype == "multi_choice":
            chosen = set(norm.get(qid) or [])
            for opt in q.get("options") or []:
                oid = opt.get("id")
                if oid in chosen:
                    for inc in opt.get("add_incisos") or []:
                        triggered_by.setdefault(str(inc), []).append(qid)

    for k, vlist in list(triggered_by.items()):
        triggered_by[k] = sorted(set(vlist))

    return triggered_by, free_text, audit_only


for _tq in sorted(TRACK_IDS):
    assert_questionnaire_incisos_align_with_matrix(_tq)

QUESTIONS: list[dict[str, Any]] = get_questions(TRACK_DEFAULT)
TRIGGER_MAP: dict[str, frozenset[str]] = build_yes_no_trigger_map(TRACK_DEFAULT)

__all__ = [
    "QUESTIONNAIRE_PATH",
    "QUESTIONS",
    "QuestionnaireLoadError",
    "TRIGGER_MAP",
    "assert_questionnaire_incisos_align_with_matrix",
    "all_question_ids",
    "build_yes_no_trigger_map",
    "get_blocks",
    "get_questions",
    "normalize_answers",
    "potential_triggers_per_inciso",
    "questions_by_block",
    "resolve_triggers",
]
