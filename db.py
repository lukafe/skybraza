"""
Persistence layer for scope submissions.

Supports SQLite (local dev) and PostgreSQL (production / Vercel).
Set DATABASE_URL env var:
  sqlite:///submissions.db          (local)
  postgresql://user:pass@host/db    (production — Neon, Supabase, Railway, etc.)

If DATABASE_URL is not set, persistence is silently disabled and the rest of
the app keeps working normally.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

_engine = None
_SessionLocal = None
_Base = None
_Submission = None


def _get_model():
    """Lazy-build the SQLAlchemy model so the app doesn't crash if sqlalchemy isn't installed."""
    global _Base, _Submission
    if _Submission is not None:
        return _Submission

    from sqlalchemy import Column, DateTime, String, Text
    from sqlalchemy.orm import DeclarativeBase

    class Base(DeclarativeBase):
        pass

    class Submission(Base):
        __tablename__ = "submissions"

        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
        institution = Column(String(500), default="")
        track = Column(String(50), default="intermediaria")
        lang = Column(String(5), default="pt")
        answers = Column(Text, default="{}")
        scope_snapshot = Column(Text, default="{}")

    _Base = Base
    _Submission = Submission
    return Submission


def init_db() -> bool:
    """Initialise engine + create tables. Returns True if DB is ready."""
    global _engine, _SessionLocal
    if _engine is not None:
        return True
    if not DATABASE_URL:
        logger.info("DATABASE_URL not set — submission persistence disabled.")
        return False
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        connect_args: dict[str, Any] = {}
        if DATABASE_URL.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        _engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        _SessionLocal = sessionmaker(bind=_engine)
        _get_model()
        _Base.metadata.create_all(_engine)  # type: ignore[union-attr]
        masked = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
        logger.info("Database ready: %s", masked)
        return True
    except Exception:
        logger.exception("Failed to initialise database — persistence disabled")
        _engine = None
        _SessionLocal = None
        return False


def db_available() -> bool:
    return _SessionLocal is not None


# ── Write ────────────────────────────────────────────────────────────────────

def save_submission(
    institution: str,
    track: str,
    lang: str,
    answers: dict[str, Any],
    scope_snapshot: dict[str, Any],
) -> Optional[str]:
    """Persist a submission. Returns the UUID on success, None on failure/skip."""
    if not db_available():
        return None
    Submission = _get_model()
    session = _SessionLocal()  # type: ignore[misc]
    try:
        sub = Submission(
            institution=institution,
            track=track,
            lang=lang,
            answers=json.dumps(answers, ensure_ascii=False, separators=(",", ":")),
            scope_snapshot=json.dumps(scope_snapshot, ensure_ascii=False, separators=(",", ":")),
        )
        session.add(sub)
        session.commit()
        return sub.id  # type: ignore[return-value]
    except Exception:
        logger.exception("Failed to save submission")
        session.rollback()
        return None
    finally:
        session.close()


# ── Read (admin) ─────────────────────────────────────────────────────────────

def _row_to_summary(row: Any) -> dict[str, Any]:
    snapshot = json.loads(row.scope_snapshot or "{}")
    resumo = snapshot.get("resumo", {})
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        "institution": row.institution,
        "track": row.track,
        "lang": row.lang,
        "total_sujeitos": resumo.get("total_sujeitos_auditoria", 0),
        "total_fora": resumo.get("total_fora_escopo_auditoria", 0),
    }


def list_submissions(
    limit: int = 50,
    offset: int = 0,
    track: str | None = None,
    search: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return (rows, total_count) for the admin listing."""
    if not db_available():
        return [], 0
    Submission = _get_model()
    session = _SessionLocal()  # type: ignore[misc]
    try:
        from sqlalchemy import desc, func  # noqa: E402

        q = session.query(Submission)
        if track:
            q = q.filter(Submission.track == track)
        if search:
            q = q.filter(Submission.institution.ilike(f"%{search}%"))
        total = q.with_entities(func.count(Submission.id)).scalar() or 0
        rows = q.order_by(desc(Submission.created_at)).offset(offset).limit(limit).all()
        return [_row_to_summary(r) for r in rows], total
    finally:
        session.close()


def get_submission(sub_id: str) -> Optional[dict[str, Any]]:
    """Return full detail for a single submission."""
    if not db_available():
        return None
    Submission = _get_model()
    session = _SessionLocal()  # type: ignore[misc]
    try:
        sub = session.query(Submission).filter(Submission.id == sub_id).first()
        if not sub:
            return None
        return {
            "id": sub.id,
            "created_at": sub.created_at.isoformat() + "Z" if sub.created_at else None,
            "institution": sub.institution,
            "track": sub.track,
            "lang": sub.lang,
            "answers": json.loads(sub.answers or "{}"),
            "scope_snapshot": json.loads(sub.scope_snapshot or "{}"),
        }
    finally:
        session.close()


def delete_submission(sub_id: str) -> bool:
    """Delete a submission by ID. Returns True if deleted."""
    if not db_available():
        return False
    Submission = _get_model()
    session = _SessionLocal()  # type: ignore[misc]
    try:
        n = session.query(Submission).filter(Submission.id == sub_id).delete()
        session.commit()
        return n > 0
    except Exception:
        logger.exception("Failed to delete submission %s", sub_id)
        session.rollback()
        return False
    finally:
        session.close()


def submission_stats() -> dict[str, Any]:
    """Aggregated stats for the admin dashboard."""
    if not db_available():
        return {"total": 0, "by_track": {}}
    Submission = _get_model()
    session = _SessionLocal()  # type: ignore[misc]
    try:
        from sqlalchemy import func  # noqa: E402

        total = session.query(func.count(Submission.id)).scalar() or 0
        by_track_rows = (
            session.query(Submission.track, func.count(Submission.id))
            .group_by(Submission.track)
            .all()
        )
        by_track = {row[0]: row[1] for row in by_track_rows}
        return {"total": total, "by_track": by_track}
    finally:
        session.close()
