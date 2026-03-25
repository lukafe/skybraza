"""
Rate limiting best-effort por IP (ou X-Forwarded-For) — útil em instância única; em serverless
cada invocação pode ser isolada. Desligar: RATE_LIMIT_DISABLED=1
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response


def _client_key(request: Request) -> str:
    fwd = (request.headers.get("x-forwarded-for") or "").strip()
    if fwd:
        return fwd.split(",")[0].strip() or "unknown"
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


def build_rate_limit_middleware() -> Callable:
    async def middleware(request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if rate_limit_exempt_path(path):
            return await call_next(request)
        lim = _get_limiter()
        if lim is None:
            return await call_next(request)
        key = _client_key(request)
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
