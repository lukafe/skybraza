"""Invariantes dos questionários por trilha (Fase 3 do plano de revisão)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matrix_loader import TRACK_IDS  # noqa: E402
from questionnaire_loader import all_question_ids, get_blocks, get_questions, normalize_answers  # noqa: E402


@pytest.mark.parametrize("track", sorted(TRACK_IDS))
def test_normalize_answers_empty_covers_every_question(track: str) -> None:
    norm = normalize_answers({}, track)
    assert set(norm.keys()) == set(all_question_ids(track))


@pytest.mark.parametrize("track", sorted(TRACK_IDS))
def test_every_question_block_exists_in_blocks(track: str) -> None:
    bids = {b["id"] for b in get_blocks(track)}
    for q in get_questions(track):
        assert q.get("block") in bids, f"{track} {q['id']} block={q.get('block')!r}"
