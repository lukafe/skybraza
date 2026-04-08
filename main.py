"""
API web IN 701 — FastAPI.

Entrypoint suportado pela Vercel (zero-config):
https://vercel.com/docs/frameworks/backend/fastapi
https://vercel.com/docs/functions/runtimes/python

Estáticos: a doc Vercel serve public/ na CDN; a função Python pode não ver esse FS.
Usamos vercel_public/ (cópia) em produção para FileResponse + /static.
Após editar public/, execute: python scripts/sync_vercel_public.py

Rotas versionadas: /api/v1/* (recomendado). Legado: /api/* (mesmo comportamento).

Env: LOG_LEVEL, LOG_FORMAT=text|json, RATE_LIMIT_* (ver rate_limit.py), RATE_LIMIT_DISABLED=1,
     TRUST_PROXY_DEPTH (0 = ignorar X-Forwarded-For; omissão 1),
     CORS_ALLOWED_ORIGINS (lista CSV; omissão = *),
     CERTIK_ENABLE_CUSTODIANTE_TRACK, CERTIK_ENABLE_CORRETORA_TRACK (0|false|off desativa a trilha),
     DATABASE_URL (persistence; sqlite:///x.db local, postgresql://… produção),
     ADMIN_SECRET (HMAC key for admin session tokens — also used as login password if ADMIN_PASSWORD not set),
     ADMIN_PASSWORD (optional separate password for admin login; defaults to ADMIN_SECRET),
     GOOGLE_CLIENT_ID (Google OAuth — admin login restricted to @certik.com)

Local: uvicorn main:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.middleware.gzip import GZipMiddleware  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field, model_validator  # noqa: E402

from logging_config import configure_logging  # noqa: E402
from rate_limit import build_rate_limit_middleware  # noqa: E402

configure_logging()

# ── Database (lazy — only if DATABASE_URL is set) ────────────────────────────
try:
    from db import init_db

    init_db()
except Exception:
    logging.getLogger(__name__).debug("db module not available — persistence disabled")

_ON_VERCEL = bool(os.environ.get("VERCEL"))


def custodiante_track_enabled() -> bool:
    """Trilha custodiante na API/UI. Desative com CERTIK_ENABLE_CUSTODIANTE_TRACK=0|false|off."""
    v = (os.environ.get("CERTIK_ENABLE_CUSTODIANTE_TRACK") or "").strip().lower()
    return v not in ("0", "false", "no", "off")


def corretora_track_enabled() -> bool:
    """Trilha corretora na API/UI. Desative com CERTIK_ENABLE_CORRETORA_TRACK=0|false|off."""
    v = (os.environ.get("CERTIK_ENABLE_CORRETORA_TRACK") or "").strip().lower()
    return v not in ("0", "false", "no", "off")


def _raise_if_track_disabled(t: str) -> None:
    if t == "custodiante" and not custodiante_track_enabled():
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TRACK_DISABLED",
                "message": "Trilha custodiante desativada neste ambiente (CERTIK_ENABLE_CUSTODIANTE_TRACK).",
            },
        )
    if t == "corretora" and not corretora_track_enabled():
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TRACK_DISABLED",
                "message": "Trilha corretora desativada neste ambiente (CERTIK_ENABLE_CORRETORA_TRACK).",
            },
        )


def _web_root() -> Path:
    """Raiz do SPA/CSS/JS servidos por esta app (incl. na Vercel dentro do bundle)."""
    vp = ROOT / "vercel_public"
    if _ON_VERCEL and (vp / "index.html").is_file():
        return vp
    return ROOT / "public"


PUBLIC_DIR = _web_root()
STATIC_DIR = PUBLIC_DIR / "static"

API_SCHEMA_VERSION = "3"
API_REST_VERSION = "v1"

logger = logging.getLogger(__name__)


def _cors_allowed_origins() -> list[str]:
    """Lido no arranque do processo; alterar CORS_ALLOWED_ORIGINS exige reiniciar o servidor."""
    raw = (os.environ.get("CORS_ALLOWED_ORIGINS") or "").strip()
    if not raw:
        return ["*"]
    parts = [x.strip() for x in raw.split(",") if x.strip()]
    return parts if parts else ["*"]


app = FastAPI(title="CertiK VASP Scoping API", version="1.0.0")

# GZip: compress responses ≥1 KB (CSS ~87KB→~20KB, JS ~48KB→~13KB, JSON data similarly).
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS por último no add_middleware = camada mais externa (primeira a ver o pedido).
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def cache_headers_middleware(request: Request, call_next):
    """
    Aggressive caching for versioned static assets; no-cache for HTML and API.
    Static files use ?v=N query params so max-age=1 year + immutable is safe.
    """
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        response.headers["Vary"] = "Accept-Encoding"
    elif path == "/admin":
        response.headers["Cache-Control"] = "no-store"
    elif path in ("/", "") or path.endswith(".html"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    if not request.url.path.startswith("/api"):
        return await call_next(request)
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000.0
    logger.info(
        "http_request method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        ms,
    )
    return response


app.middleware("http")(build_rate_limit_middleware())


@app.middleware("http")
async def optional_api_key_guard(request: Request, call_next):
    key = os.environ.get("CERTIK_API_KEY")
    if not key:
        return await call_next(request)
    path = request.url.path
    if path in ("/api/health", "/api/v1/health") or not path.startswith("/api"):
        return await call_next(request)
    # Admin routes use their own auth (Google OAuth + HMAC session tokens)
    if "/admin/" in path or path.endswith("/admin/config") or path.endswith("/admin/login"):
        return await call_next(request)
    if request.headers.get("X-Certik-Api-Key") == key:
        return await call_next(request)
    return JSONResponse(
        status_code=401,
        content={"detail": "Invalid or missing X-Certik-Api-Key header"},
    )


def _serialize_question(q: dict[str, Any]) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": q["id"],
        "type": q.get("type", "yes_no"),
        "text": (q.get("text") or "").strip() if isinstance(q.get("text"), str) else q.get("text", ""),
        "justificativa": q.get("justificativa", ""),
        "block": q.get("block"),
        "order": q.get("order", 0),
    }
    if q.get("tags"):
        base["tags"] = q["tags"]
    t = base["type"]
    if t == "single_choice":
        base["options"] = [{"id": o["id"], "label": o["label"]} for o in (q.get("options") or [])]
    elif t == "multi_choice":
        base["options"] = [{"id": o["id"], "label": o["label"]} for o in (q.get("options") or [])]
    elif t == "text_short":
        base["placeholder"] = q.get("placeholder", "")
        base["max_length"] = int(q.get("max_length") or 4000)
    if q.get("audit_only"):
        base["audit_only"] = True
    return base


class ScopeRequest(BaseModel):
    institution: str = Field(default="", max_length=500)
    answers: dict[str, Any] = Field(default_factory=dict)
    track: str = Field(default="intermediaria", description="intermediaria | custodiante | corretora")
    lang: str = Field(default="pt", description="pt | en — language for generated narratives")

    @model_validator(mode="after")
    def validate_answers_bounds(self) -> ScopeRequest:
        """Limita tamanho do payload de respostas (abuso / acidentes)."""
        a = self.answers
        if len(a) > 200:
            raise ValueError("answers: demasiadas chaves (máx. 200).")
        try:
            payload = json.dumps(a, default=str, separators=(",", ":"))
        except (TypeError, ValueError) as e:
            raise ValueError("answers: valores devem ser serializáveis em JSON.") from e
        if len(payload.encode("utf-8")) > 10240:
            raise ValueError("answers: JSON excede 10 KB.")
        return self


api_router = APIRouter(tags=["scope"])


@api_router.get("/health")
def health() -> dict[str, Any]:
    try:
        from db import db_available
        _db = db_available()
    except Exception:
        _db = False
    return {
        "status": "ok",
        "phase": "E",
        "api_schema_version": API_SCHEMA_VERSION,
        "api_rest_version": API_REST_VERSION,
        "features": {
            "custodiante_track": custodiante_track_enabled(),
            "corretora_track": corretora_track_enabled(),
            "database": _db,
        },
    }


@api_router.get("/questions")
def get_questions(
    response: Response,
    track: str = Query(default="intermediaria", description="intermediaria | custodiante | corretora"),
) -> dict[str, Any]:
    from matrix_loader import MatrixLoadError, normalize_track
    from questionnaire_loader import get_blocks
    from rules_engine import questions_by_block

    try:
        t = normalize_track(track)
    except MatrixLoadError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_TRACK", "message": str(e)},
        ) from e

    _raise_if_track_disabled(t)

    response.headers["Cache-Control"] = "public, max-age=300"
    by_block = questions_by_block(t)
    blocks_out: list[dict[str, Any]] = []
    for mb in get_blocks(t):
        bid = str(mb["id"])
        qs = by_block.get(bid, [])
        blocks_out.append(
            {
                "id": bid,
                "title": mb.get("title", bid),
                "lead": mb.get("lead", ""),
                "questions": [_serialize_question(q) for q in qs],
            }
        )
    return {"blocks": blocks_out, "api_schema_version": API_SCHEMA_VERSION, "track": t}


@api_router.post("/scope")
def post_scope(body: ScopeRequest) -> dict[str, Any]:
    from matrix_loader import MatrixLoadError, normalize_track
    from questionnaire_loader import QuestionnaireLoadError
    from rules_engine import compute_scope

    try:
        t = normalize_track(body.track)
    except MatrixLoadError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_TRACK", "message": str(e)},
        ) from e

    _raise_if_track_disabled(t)

    lang = body.lang if body.lang in ("pt", "en") else "pt"

    try:
        _, meta = compute_scope(body.answers, track=t, lang=lang, build_df=False)
    except QuestionnaireLoadError as e:
        logger.warning("compute_scope rejected input: %s", e)
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_SCOPE_INPUT", "message": str(e)},
        ) from e
    except Exception:
        logger.exception("compute_scope failed")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "SCOPE_INTERNAL_ERROR",
                "message": "Erro interno ao calcular o escopo. Tente novamente ou contacte o suporte.",
            },
        ) from None

    from matrix_loader import get_coverage_meta
    matrix_meta = get_coverage_meta(t)

    inst = body.institution.strip()

    result = {
        "api_schema_version": API_SCHEMA_VERSION,
        "matrix_version": matrix_meta.get("matrix_version"),
        "matrix_last_updated": matrix_meta.get("last_updated"),
        "track": t,
        "institution": inst,
        "incisos_sujeitos_auditoria": meta["incisos_sujeitos_auditoria"],
        "incisos_fora_escopo_auditoria": meta["incisos_fora_escopo_auditoria"],
        "resumo": {
            "total_sujeitos_auditoria": meta["total_count"],
            "obrigatorios_matriz": meta["mandatory_count"],
            "acionados_por_respostas": meta["conditional_count"],
            "total_fora_escopo_auditoria": meta["total_fora_escopo_auditoria"],
        },
        "corpus_readiness": meta["corpus_readiness"],
        "suppressed_incisos": meta.get("suppressed_incisos") or {},
        "journey_2": meta.get("journey_2") or {},
    }

    # Persist submission (best-effort — never blocks the client response)
    sub_id = None
    try:
        from db import save_submission

        sub_id = save_submission(
            institution=inst,
            track=t,
            lang=lang,
            answers=body.answers,
            scope_snapshot=result,
        )
    except Exception:
        logger.debug("Submission persistence skipped", exc_info=True)

    if sub_id:
        result["submission_id"] = sub_id

    return result


@api_router.post("/scope/export")
def post_scope_export(body: ScopeRequest) -> StreamingResponse:
    """
    Gera e devolve ficheiro .xlsx com o escopo completo (4 folhas: Resumo, No Escopo,
    Fora do Escopo, Prontidão Corpus). Aceita os mesmos campos que POST /scope.
    """
    from excel_export import build_scope_excel
    from matrix_loader import MatrixLoadError, normalize_track
    from questionnaire_loader import QuestionnaireLoadError
    from rules_engine import compute_scope

    try:
        t = normalize_track(body.track)
    except MatrixLoadError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_TRACK", "message": str(e)}) from e

    _raise_if_track_disabled(t)

    lang = body.lang if body.lang in ("pt", "en") else "pt"

    try:
        _, meta = compute_scope(body.answers, track=t, lang=lang, build_df=False)
    except QuestionnaireLoadError as e:
        logger.warning("compute_scope rejected input (export): %s", e)
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_SCOPE_INPUT", "message": str(e)},
        ) from e
    except Exception:
        logger.exception("compute_scope failed (export)")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "SCOPE_INTERNAL_ERROR",
                "message": "Erro interno ao calcular o escopo para exportação.",
            },
        ) from None

    inst = body.institution.strip()
    scope_response = {
        "institution": inst,
        "track": t,
        "incisos_sujeitos_auditoria": meta["incisos_sujeitos_auditoria"],
        "incisos_fora_escopo_auditoria": meta["incisos_fora_escopo_auditoria"],
        "resumo": {
            "total_sujeitos_auditoria": meta["total_count"],
            "obrigatorios_matriz": meta["mandatory_count"],
            "acionados_por_respostas": meta["conditional_count"],
            "total_fora_escopo_auditoria": meta["total_fora_escopo_auditoria"],
        },
        "corpus_readiness": meta["corpus_readiness"],
    }

    buf = build_scope_excel(scope_response, lang=lang)

    from datetime import date
    safe_inst = "".join(c if c.isalnum() or c in "-_" else "_" for c in inst)[:40] or "export"
    filename = f"certik_vasp_scope_{safe_inst}_{date.today().isoformat()}.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api_router.post("/scope/pdf")
def post_scope_pdf(body: ScopeRequest) -> StreamingResponse:
    """
    Gera e devolve ficheiro .pdf com resumo executivo do escopo, prontidão do corpus
    e listagens de incisos (mesmos campos que POST /scope e /scope/export).
    """
    from matrix_loader import MatrixLoadError, normalize_track
    from questionnaire_loader import QuestionnaireLoadError
    from rules_engine import compute_scope
    from scope_pdf import build_scope_pdf_bytes

    try:
        t = normalize_track(body.track)
    except MatrixLoadError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_TRACK", "message": str(e)}) from e

    _raise_if_track_disabled(t)

    lang = body.lang if body.lang in ("pt", "en") else "pt"

    try:
        _, meta = compute_scope(body.answers, track=t, lang=lang, build_df=False)
    except QuestionnaireLoadError as e:
        logger.warning("compute_scope rejected input (pdf): %s", e)
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_SCOPE_INPUT", "message": str(e)},
        ) from e
    except Exception:
        logger.exception("compute_scope failed (pdf)")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "SCOPE_INTERNAL_ERROR",
                "message": "Erro interno ao calcular o escopo para exportação PDF.",
            },
        ) from None

    from matrix_loader import get_coverage_meta

    matrix_meta = get_coverage_meta(t)
    inst = body.institution.strip()
    scope_response = {
        "institution": inst,
        "track": t,
        "incisos_sujeitos_auditoria": meta["incisos_sujeitos_auditoria"],
        "incisos_fora_escopo_auditoria": meta["incisos_fora_escopo_auditoria"],
        "resumo": {
            "total_sujeitos_auditoria": meta["total_count"],
            "obrigatorios_matriz": meta["mandatory_count"],
            "acionados_por_respostas": meta["conditional_count"],
            "total_fora_escopo_auditoria": meta["total_fora_escopo_auditoria"],
        },
        "corpus_readiness": meta["corpus_readiness"],
    }

    buf = build_scope_pdf_bytes(
        scope_response,
        lang=lang,
        matrix_version=str(matrix_meta.get("matrix_version") or "") or None,
        matrix_last_updated=str(matrix_meta.get("last_updated") or "") or None,
    )

    from datetime import date

    safe_inst = "".join(c if c.isalnum() or c in "-_" else "_" for c in inst)[:40] or "export"
    filename = f"certik_vasp_scope_{safe_inst}_{date.today().isoformat()}.pdf"

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Admin routes (protected by ADMIN_SECRET env var) ─────────────────────────

admin_router = APIRouter(tags=["admin"])

ADMIN_ALLOWED_DOMAIN = "certik.com"
_SESSION_TTL = 86400  # 24 h

_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_LOCKOUT_SECS = 60
_login_attempts: dict[str, list[float]] = {}


def _check_login_rate_limit(ip: str) -> None:
    """Raise 429 if IP exceeded login attempts within the lockout window."""
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    attempts = [t for t in attempts if now - t < _LOGIN_LOCKOUT_SECS]
    _login_attempts[ip] = attempts
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail={"code": "TOO_MANY_ATTEMPTS", "message": f"Demasiadas tentativas. Aguarde {_LOGIN_LOCKOUT_SECS}s."},
        )


def _record_login_attempt(ip: str) -> None:
    _login_attempts.setdefault(ip, []).append(time.time())


def _admin_sign_session(email: str, name: str = "") -> str:
    """Create an HMAC-signed session token (valid _SESSION_TTL seconds)."""
    import base64
    import hashlib
    import hmac

    secret = os.environ.get("ADMIN_SECRET", "")
    if not secret:
        raise RuntimeError("ADMIN_SECRET not configured")
    payload = json.dumps(
        {"email": email, "name": name, "exp": int(time.time()) + _SESSION_TTL},
        separators=(",", ":"),
    )
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}.{sig}".encode()).decode()


def _admin_verify_session(token: str) -> dict[str, Any]:
    """Verify an HMAC-signed session token. Raises on failure."""
    import base64
    import hashlib
    import hmac as _hmac

    secret = os.environ.get("ADMIN_SECRET", "")
    if not secret:
        raise ValueError("ADMIN_SECRET not configured")
    try:
        decoded = base64.urlsafe_b64decode(token).decode()
    except Exception as exc:
        raise ValueError("Malformed token") from exc
    if "." not in decoded:
        raise ValueError("Malformed token")
    payload_str, sig = decoded.rsplit(".", 1)
    expected = _hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
    if not _hmac.compare_digest(sig, expected):
        raise ValueError("Invalid signature")
    payload = json.loads(payload_str)
    if payload.get("exp", 0) < time.time():
        raise ValueError("Token expired")
    return payload


def _require_admin(request: Request) -> dict[str, Any]:
    """Verify admin session token from Authorization header. Returns session payload."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Missing admin session."})
    token = auth[7:]
    try:
        return _admin_verify_session(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": str(exc)}) from exc


class AdminLoginRequest(BaseModel):
    credential: str = Field(default="", description="Google ID token from Sign-In")
    password: str = Field(default="", description="Fallback password (ADMIN_SECRET)")


@admin_router.get("/admin/config")
def admin_config() -> dict[str, Any]:
    """Public config needed by the admin frontend."""
    cid = os.environ.get("GOOGLE_CLIENT_ID", "")
    return {
        "google_client_id": cid,
        "domain": ADMIN_ALLOWED_DOMAIN,
    }


@admin_router.post("/admin/login")
def admin_login(body: AdminLoginRequest, request: Request) -> dict[str, Any]:
    """Login via Google ID token or fallback password (ADMIN_PASSWORD / ADMIN_SECRET)."""
    admin_secret = os.environ.get("ADMIN_SECRET", "")
    if not admin_secret:
        raise HTTPException(status_code=503, detail={"code": "NOT_CONFIGURED", "message": "ADMIN_SECRET not set."})

    client_ip = request.client.host if request.client else "unknown"
    _check_login_rate_limit(client_ip)

    cid = os.environ.get("GOOGLE_CLIENT_ID", "")

    # --- Password fallback (when Google OAuth is not configured) ---
    if body.password:
        import hmac as _hmac_pw
        admin_password = os.environ.get("ADMIN_PASSWORD", admin_secret)
        if not _hmac_pw.compare_digest(body.password, admin_password):
            _record_login_attempt(client_ip)
            raise HTTPException(status_code=401, detail={"code": "WRONG_PASSWORD", "message": "Senha incorreta."})
        session_token = _admin_sign_session("admin@local", "Administrador")
        try:
            from db import record_audit
            record_audit("login", actor="admin@local", ip=client_ip, detail="password")
        except Exception:
            pass
        return {"session_token": session_token, "email": "admin@local", "name": "Administrador"}

    # --- Google OAuth flow ---
    if not body.credential:
        raise HTTPException(status_code=400, detail={"code": "MISSING_FIELDS", "message": "Credencial ou senha necessária."})
    if not cid:
        raise HTTPException(status_code=503, detail={"code": "NOT_CONFIGURED", "message": "GOOGLE_CLIENT_ID not set."})

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token

        idinfo = google_id_token.verify_oauth2_token(body.credential, google_requests.Request(), cid)
    except Exception as exc:
        logger.warning("Google token verification failed: %s", exc)
        _record_login_attempt(client_ip)
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Google token inválido."}) from exc

    email = (idinfo.get("email") or "").lower().strip()
    if not idinfo.get("email_verified"):
        _record_login_attempt(client_ip)
        raise HTTPException(status_code=403, detail={"code": "EMAIL_NOT_VERIFIED", "message": "Email não verificado pelo Google."})
    if not email.endswith(f"@{ADMIN_ALLOWED_DOMAIN}"):
        logger.warning("Admin login rejected for %s (not @%s)", email, ADMIN_ALLOWED_DOMAIN)
        _record_login_attempt(client_ip)
        raise HTTPException(status_code=403, detail={"code": "DOMAIN_DENIED", "message": f"Apenas contas @{ADMIN_ALLOWED_DOMAIN} podem aceder."})

    name = idinfo.get("name", "")
    session_token = _admin_sign_session(email, name)
    try:
        from db import record_audit
        record_audit("login", actor=email, ip=client_ip, detail="google_oauth")
    except Exception:
        pass
    return {"session_token": session_token, "email": email, "name": name}


@admin_router.get("/admin/stats")
def admin_stats(request: Request) -> dict[str, Any]:
    _require_admin(request)
    from db import db_available, submission_stats

    if not db_available():
        return {"total": 0, "by_track": {}, "db": False}
    stats = submission_stats()
    stats["db"] = True
    return stats


@admin_router.get("/admin/submissions")
def admin_list_submissions(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    track: str = Query(default=""),
    search: str = Query(default=""),
    date_from: str = Query(default="", description="ISO date YYYY-MM-DD"),
    date_to: str = Query(default="", description="ISO date YYYY-MM-DD"),
) -> dict[str, Any]:
    _require_admin(request)
    from db import list_submissions

    rows, total = list_submissions(
        limit=limit,
        offset=offset,
        track=track or None,
        search=search or None,
        date_from=date_from or None,
        date_to=date_to or None,
    )
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@admin_router.get("/admin/submissions/export")
def admin_export_csv(
    request: Request,
    track: str = Query(default=""),
    search: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
) -> Response:
    """Export all matching submissions as CSV."""
    _require_admin(request)
    from db import export_submissions_csv

    csv_data = export_submissions_csv(
        track=track or None, search=search or None,
        date_from=date_from or None, date_to=date_to or None,
    )
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="certik_submissions.csv"',
            "Cache-Control": "no-store",
        },
    )


def _load_submission_for_export(sub_id: str, request: Request) -> dict[str, Any]:
    """Shared helper: load a submission or raise 404."""
    _require_admin(request)
    from db import get_submission

    data = get_submission(sub_id)
    if not data:
        raise HTTPException(status_code=404, detail="Submission not found.")
    return data


@admin_router.get("/admin/submissions/{sub_id}/excel")
def admin_export_submission_excel(sub_id: str, request: Request) -> StreamingResponse:
    """Re-generate Excel export from a stored submission."""
    data = _load_submission_for_export(sub_id, request)
    from excel_export import build_scope_excel

    scope_response = {
        "institution": data.get("institution", ""),
        "track": data.get("track", "intermediaria"),
        "incisos_sujeitos_auditoria": (data.get("scope_snapshot") or {}).get("incisos_sujeitos_auditoria", []),
        "incisos_fora_escopo_auditoria": (data.get("scope_snapshot") or {}).get("incisos_fora_escopo_auditoria", []),
        "resumo": (data.get("scope_snapshot") or {}).get("resumo", {}),
        "corpus_readiness": (data.get("scope_snapshot") or {}).get("corpus_readiness", {}),
    }
    lang = data.get("lang", "pt")
    buf = build_scope_excel(scope_response, lang=lang)

    from datetime import date
    safe_inst = "".join(c if c.isalnum() or c in "-_" else "_" for c in (data.get("institution") or ""))[:40] or "export"
    filename = f"certik_vasp_scope_{safe_inst}_{date.today().isoformat()}.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@admin_router.get("/admin/submissions/{sub_id}/pdf")
def admin_export_submission_pdf(sub_id: str, request: Request) -> Response:
    """Re-generate PDF export from a stored submission."""
    data = _load_submission_for_export(sub_id, request)
    from scope_pdf import build_scope_pdf_bytes

    snap = data.get("scope_snapshot") or {}
    scope_response = {
        "institution": data.get("institution", ""),
        "track": data.get("track", "intermediaria"),
        "incisos_sujeitos_auditoria": snap.get("incisos_sujeitos_auditoria", []),
        "incisos_fora_escopo_auditoria": snap.get("incisos_fora_escopo_auditoria", []),
        "resumo": snap.get("resumo", {}),
        "corpus_readiness": snap.get("corpus_readiness", {}),
    }
    lang = data.get("lang", "pt")

    try:
        from matrix_loader import get_coverage_meta, normalize_track
        t = normalize_track(data.get("track", "intermediaria"))
        matrix_meta = get_coverage_meta(t)
    except Exception:
        matrix_meta = {}

    pdf_bytes = build_scope_pdf_bytes(scope_response, matrix_meta=matrix_meta, lang=lang)

    safe_inst = "".join(c if c.isalnum() or c in "-_" else "_" for c in (data.get("institution") or ""))[:40] or "report"
    filename = f"certik_vasp_scope_{safe_inst}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@admin_router.get("/admin/submissions/{sub_id}")
def admin_get_submission(sub_id: str, request: Request) -> dict[str, Any]:
    return _load_submission_for_export(sub_id, request)


@admin_router.post("/admin/simulate")
def admin_simulate(body: ScopeRequest, request: Request) -> dict[str, Any]:
    """Run compute_scope without persisting — sandbox mode for admin."""
    _require_admin(request)
    from matrix_loader import MatrixLoadError, get_coverage_meta, normalize_track
    from questionnaire_loader import QuestionnaireLoadError
    from rules_engine import compute_scope

    try:
        t = normalize_track(body.track)
    except MatrixLoadError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    lang = body.lang if body.lang in ("pt", "en") else "pt"

    try:
        _, meta = compute_scope(body.answers, track=t, lang=lang, build_df=False)
    except QuestionnaireLoadError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception:
        raise HTTPException(status_code=500, detail="Erro interno na simulação.") from None

    matrix_meta = get_coverage_meta(t)
    return {
        "simulated": True,
        "track": t,
        "institution": body.institution.strip(),
        "api_schema_version": API_SCHEMA_VERSION,
        "matrix_version": matrix_meta.get("matrix_version"),
        "incisos_sujeitos_auditoria": meta["incisos_sujeitos_auditoria"],
        "incisos_fora_escopo_auditoria": meta["incisos_fora_escopo_auditoria"],
        "resumo": {
            "total_sujeitos_auditoria": meta["total_count"],
            "obrigatorios_matriz": meta["mandatory_count"],
            "acionados_por_respostas": meta["conditional_count"],
            "total_fora_escopo_auditoria": meta["total_fora_escopo_auditoria"],
        },
        "corpus_readiness": meta["corpus_readiness"],
    }


@admin_router.get("/admin/audit")
def admin_audit_log(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_admin(request)
    from db import list_audit_log

    items, total = list_audit_log(limit=limit, offset=offset)
    return {"items": items, "total": total}


@admin_router.delete("/admin/submissions/{sub_id}")
def admin_delete_submission(sub_id: str, request: Request) -> dict[str, Any]:
    session = _require_admin(request)
    from db import delete_submission, record_audit

    ok = delete_submission(sub_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Submission not found or already deleted.")
    try:
        actor = session.get("email", "unknown")
        ip = request.client.host if request.client else ""
        record_audit("delete_submission", actor=actor, ip=ip, detail=sub_id)
    except Exception:
        pass
    return {"deleted": True, "id": sub_id}


@api_router.get("/resultado/{sub_id}")
def public_get_result(sub_id: str) -> dict[str, Any]:
    """Public read-only endpoint for clients to revisit their result."""
    from db import db_available, get_submission

    if not db_available():
        raise HTTPException(status_code=503, detail="Database not configured.")
    data = get_submission(sub_id)
    if not data:
        raise HTTPException(status_code=404, detail="Resultado não encontrado.")
    snap = data.get("scope_snapshot") or {}
    return {
        "id": data["id"],
        "institution": data.get("institution", ""),
        "track": data.get("track", ""),
        "lang": data.get("lang", "pt"),
        "created_at": data.get("created_at"),
        "resumo": snap.get("resumo", {}),
        "incisos_sujeitos_auditoria": snap.get("incisos_sujeitos_auditoria", []),
        "incisos_fora_escopo_auditoria": snap.get("incisos_fora_escopo_auditoria", []),
        "corpus_readiness": snap.get("corpus_readiness", {}),
        "journey_2": snap.get("journey_2", {}),
    }


app.include_router(api_router, prefix="/api")
app.include_router(api_router, prefix="/api/v1")

app.include_router(admin_router, prefix="/api")
app.include_router(admin_router, prefix="/api/v1")


# Na Vercel a CDN também pode servir public/; aqui garantimos /static quando o pedido chega à função.
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/resultado/{sub_id}", response_model=None)
async def resultado_page(sub_id: str) -> FileResponse | HTMLResponse:
    f = PUBLIC_DIR / "resultado.html"
    if f.is_file():
        return FileResponse(f, media_type="text/html; charset=utf-8")
    return HTMLResponse(status_code=404, content="<h1>Página não encontrada</h1>")


@app.get("/admin", response_model=None)
async def admin_page() -> FileResponse | HTMLResponse:
    index = PUBLIC_DIR / "admin.html"
    if index.is_file():
        return FileResponse(index, media_type="text/html; charset=utf-8")
    return HTMLResponse(status_code=404, content="<h1>Admin page not found</h1>")


@app.get("/", response_model=None)
async def spa_index() -> FileResponse | HTMLResponse:
    index = PUBLIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(index, media_type="text/html; charset=utf-8")
    return HTMLResponse(
        status_code=503,
        content=(
            "<html><body><h1>Frontend não empacotado</h1>"
            "<p>Na Vercel falta <code>vercel_public/index.html</code> no repositório.</p>"
            "<p>Localmente: <code>python scripts/sync_vercel_public.py</code> e commit.</p>"
            "<p><a href='/api/v1/health'>GET /api/v1/health</a></p></body></html>"
        ),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
