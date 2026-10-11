"""Fixed-window rate limiting (Redis when configured, in-process fallback)."""
from __future__ import annotations

import threading
import time

from fastapi import HTTPException, Request

from .config import get_settings

_lock = threading.Lock()
_mem: dict[str, tuple[int, float]] = {}
_redis = None


def _client():
    global _redis
    url = get_settings().redis_url
    if not url:
        return None
    if _redis is None:
        import redis

        _redis = redis.Redis.from_url(url, socket_timeout=0.3, socket_connect_timeout=0.3)
    return _redis


def hit(key: str, limit: int, window_s: int) -> tuple[bool, int]:
    """Count a hit; returns (allowed, retry_after_seconds)."""
    r = _client()
    if r is not None:
        try:
            k = f"rl:{key}:{int(time.time() // window_s)}"
            pipe = r.pipeline()
            pipe.incr(k)
            pipe.expire(k, window_s + 1)
            count = int(pipe.execute()[0])
            return count <= limit, window_s - int(time.time() % window_s)
        except Exception:  # fail open to in-memory limiter, never crash the request
            pass
    now = time.time()
    with _lock:
        count, start = _mem.get(key, (0, now))
        if now - start >= window_s:
            count, start = 0, now
        count += 1
        _mem[key] = (count, start)
        if len(_mem) > 100_000:
            for k, (_, st) in list(_mem.items()):
                if now - st > 3600:
                    _mem.pop(k, None)
        return count <= limit, int(window_s - (now - start)) + 1


def client_ip(request: Request) -> str:
    # Behind a trusted proxy configure uvicorn --proxy-headers --forwarded-allow-ips; never trust raw headers here.
    return request.client.host if request.client else "unknown"


def limit(request: Request, bucket: str, limit_: int, window_s: int, key: str | None = None) -> None:
    if get_settings().env == "test" and request.headers.get("x-test-ratelimit") != "on":
        return
    ok, retry = hit(f"{bucket}:{key or client_ip(request)}", limit_, window_s)
    if not ok:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait and try again.", headers={"Retry-After": str(retry)})


def reset() -> None:
    with _lock:
        _mem.clear()
