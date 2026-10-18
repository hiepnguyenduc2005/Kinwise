import time

from app.core.errors import AppError


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}

    def reset(self) -> None:
        self._hits.clear()

    def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        recent = [stamp for stamp in self._hits.get(key, []) if now - stamp < window_seconds]
        if len(recent) >= limit:
            raise AppError(429, "rate_limited", "Too many attempts. Please wait and try again.")
        recent.append(now)
        self._hits[key] = recent
