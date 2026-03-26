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
     CORS_ALLOWED_ORIGINS (lista CSV; omissão = *), CERTIK_ENABLE_CUSTODIANTE_TRACK

Local: uvicorn main:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from logging_config import configure_logging  # noqa: E402
from rate_limit import build_rate_limit_middleware  # noqa: E402

configure_logging()

_ON_VERCEL = bool(os.environ.get("VERCEL"))


def custodiante_track_enabled() -> bool:
    """Trilha custodiante na API/UI. Desative com CERTIK_ENABLE_CUSTODIANTE_TRACK=0|false|off."""
    v = (os.environ.get("CERTIK_ENABLE_CUSTODIANTE_TRACK") or "").strip().lower()
    return v not in ("0", "false", "no", "off")


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

# CORS por último no add_middleware = camada mais externa (primeira a ver o pedido).
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    track: str = Field(default="intermediaria", description="intermediaria | custodiante")


api_router = APIRouter(tags=["scope"])


@api_router.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "phase": "E",
        "api_schema_version": API_SCHEMA_VERSION,
        "api_rest_version": API_REST_VERSION,
        "features": {"custodiante_track": custodiante_track_enabled()},
    }


@api_router.get("/questions")
def get_questions(
    response: Response,
    track: str = Query(default="intermediaria", description="intermediaria | custodiante"),
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

    if t == "custodiante" and not custodiante_track_enabled():
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TRACK_DISABLED",
                "message": "Trilha custodiante desativada neste ambiente (CERTIK_ENABLE_CUSTODIANTE_TRACK).",
            },
        )

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
    from rules_engine import compute_scope

    try:
        t = normalize_track(body.track)
    except MatrixLoadError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_TRACK", "message": str(e)},
        ) from e

    if t == "custodiante" and not custodiante_track_enabled():
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TRACK_DISABLED",
                "message": "Trilha custodiante desativada neste ambiente (CERTIK_ENABLE_CUSTODIANTE_TRACK).",
            },
        )

    try:
        _, meta = compute_scope(body.answers, track=t)
    except Exception:
        logger.exception("compute_scope failed")
        raise HTTPException(
            status_code=400,
            detail={
                "code": "SCOPE_COMPUTE_ERROR",
                "message": "Não foi possível calcular o escopo com as respostas enviadas. Revise o questionário ou tente novamente.",
            },
        ) from None

    inst = body.institution.strip()
    return {
        "api_schema_version": API_SCHEMA_VERSION,
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
        "journey_2": meta.get("journey_2") or {},
    }


app.include_router(api_router, prefix="/api")
app.include_router(api_router, prefix="/api/v1")


# Na Vercel a CDN também pode servir public/; aqui garantimos /static quando o pedido chega à função.
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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
