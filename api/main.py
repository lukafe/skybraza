"""
API web para o questionário de escopo IN 701 (clientes).

Executar a partir da raiz do projeto:
  uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
Abrir: http://127.0.0.1:8000

Opcional (rede interna / staging): variável de ambiente CERTIK_API_KEY — exige cabeçalho
X-Certik-Api-Key em todos os pedidos /api/* exceto GET /api/health.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# Raiz do projeto (pai de /api)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from questionnaire_loader import get_blocks  # noqa: E402
from rules_engine import compute_scope, questions_by_block  # noqa: E402

WEB_DIR = ROOT / "web"

API_SCHEMA_VERSION = "2"

app = FastAPI(title="CertiK VASP Scoping API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def optional_api_key_guard(request: Request, call_next):
    key = os.environ.get("CERTIK_API_KEY")
    if not key:
        return await call_next(request)
    path = request.url.path
    if path == "/api/health" or not path.startswith("/api/"):
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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "E", "api_schema_version": API_SCHEMA_VERSION}


@app.get("/api/questions")
def get_questions() -> dict[str, Any]:
    by_block = questions_by_block()
    blocks_out: list[dict[str, Any]] = []
    for mb in get_blocks():
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
    return {"blocks": blocks_out, "api_schema_version": API_SCHEMA_VERSION}


@app.post("/api/scope")
def post_scope(body: ScopeRequest) -> dict[str, Any]:
    try:
        _, meta = compute_scope(body.answers)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    inst = body.institution.strip()
    return {
        "api_schema_version": API_SCHEMA_VERSION,
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


if WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
async def spa_index() -> FileResponse:
    """Servido depois do mount /static para não sombrear ficheiros estáticos."""
    index = WEB_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Frontend não encontrado (web/index.html).")
    return FileResponse(index, media_type="text/html; charset=utf-8")
