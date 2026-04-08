"""
Rate limiting best-effort por IP (ou X-Forwarded-For). Desligar: RATE_LIMIT_DISABLED=1

Com REDIS_URL definido e o pacote ``redis`` instalado, usa contagem distribuída (janela fixa de 60s por minuto
de relógio); caso contrário, memória por instância (serverless = limitação parcial).

TRUST_PROXY_DEPTH: 0 = ignorar X-Forwarded-For (IP da ligação apenas; útil em dev).
  >= 1 = usar o primeiro hop de X-Forwarded-For (omissão 1, p.ex. atrás da Vercel).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_logger = logging.getLogger(__name__)


def _client_key(request: Request) -> str:
    """
    TRUST_PROXY_DEPTH=0 — ignora X-Forwarded-For (útil em dev sem proxy; evita spoofing).
    TRUST_PROXY_DEPTH>=1 — usa o primeiro hop da cadeia (cliente visto pelo proxy de confiança).
    Omisão: 1 (comportamento anterior; Vercel/proxy costuma preencher XFF corretamente).
    """
    if _int_env("TRUST_PROXY_DEPTH", 1) > 0:
        fwd = (request.headers.get("x-forwarded-for") or "").strip()
        if fwd:
            first = fwd.split(",")[0].strip()
            if first:
                return first
    if request.client:
        return request.client.host
    return "unknown"


def _int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1.0, float(raw))
    except ValueError:
        return default


class _SlidingWindowLimiter:
    __slots__ = ("_window_sec", "_max_hits", "_by_key", "_lock", "_max_keys")

    def __init__(self, window_sec: float, max_hits: int, max_keys: int = 50_000) -> None:
        self._window_sec = window_sec
        self._max_hits = max_hits
        self._by_key: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()
        self._max_keys = max_keys

    async def allow(self, key: str) -> bool:
        async with self._lock:
            now = time.monotonic()
            lst = self._by_key.setdefault(key, [])
            lst[:] = [t for t in lst if now - t < self._window_sec]
            if len(lst) >= self._max_hits:
                return False
            lst.append(now)
            while len(self._by_key) > self._max_keys:
                self._by_key.pop(next(iter(self._by_key)))
            return True


_limiter: _SlidingWindowLimiter | None = None


def reset_limiter_for_tests() -> None:
    """Zera estado global (apenas testes)."""
    global _limiter
    _limiter = None


def _get_limiter() -> _SlidingWindowLimiter | None:
    global _limiter
    if (os.environ.get("RATE_LIMIT_DISABLED") or "").strip().lower() in ("1", "true", "yes"):
        return None
    if _limiter is None:
        _limiter = _SlidingWindowLimiter(
            window_sec=_float_env("RATE_LIMIT_WINDOW_SEC", 60.0),
            max_hits=_int_env("RATE_LIMIT_MAX_REQUESTS", 120),
        )
    return _limiter


def rate_limit_exempt_path(path: str) -> bool:
    if path in ("/api/health", "/api/v1/health"):
        return True
    if path == "/" or path.startswith("/static"):
        return True
    return not path.startswith("/api")


def _redis_allow_sync(client_key: str) -> bool | None:
    """
    Fixed 60s window per wall-clock minute, shared across instances.
    Returns True/False when Redis is used; None to fall back to in-memory limiter.
    """
    url = (os.environ.get("REDIS_URL") or "").strip()
    if not url:
        return None
    try:
        import redis  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        r = redis.from_url(url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        max_hits = _int_env("RATE_LIMIT_MAX_REQUESTS", 120)
        bucket = int(time.time() // 60)
        safe = client_key.replace(":", "_")[:200]
        k = f"rl:{safe}:{bucket}"
        n = int(r.incr(k))
        if n == 1:
            r.expire(k, 120)
        return n <= max_hits
    except Exception:
        _logger.debug("Redis rate limit failed; falling back to memory", exc_info=True)
        return None


def build_rate_limit_middleware() -> Callable:
    async def middleware(request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if rate_limit_exempt_path(path):
            return await call_next(request)
        key = _client_key(request)
        redis_ok = await asyncio.to_thread(_redis_allow_sync, key)
        if redis_ok is not None:
            if not redis_ok:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Demasiados pedidos. Aguarde um momento e tente novamente.",
                        }
                    },
                )
            return await call_next(request)
        lim = _get_limiter()
        if lim is None:
            return await call_next(request)
        if not await lim.allow(key):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Demasiados pedidos. Aguarde um momento e tente novamente.",
                    }
                },
            )
        return await call_next(request)

    return middleware
