from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request

from settings import get_settings

WINDOW_SECONDS = 60


class FixedWindowLimiter:
    """Per-process request counter per (client, bucket) and one-minute window.

    Enough for a single API instance. Multiple instances need a shared store
    such as Redis, added when the deployment scales out.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[tuple[str, str, int], int] = defaultdict(int)

    def hit(self, client: str, bucket: str, limit: int, now: float | None = None) -> int | None:
        """Count a request. Returns seconds to wait when over the limit, else None."""
        now = time.time() if now is None else now
        window = int(now // WINDOW_SECONDS)
        with self._lock:
            if len(self._counts) > 50_000:
                self._counts = defaultdict(int, {k: v for k, v in self._counts.items() if k[2] == window})
            key = (client, bucket, window)
            self._counts[key] += 1
            if self._counts[key] > limit:
                return max(1, int((window + 1) * WINDOW_SECONDS - now))
        return None


limiter = FixedWindowLimiter()


def rate_limited(bucket: str):
    """FastAPI dependency enforcing SIAMSIL_RATE_LIMIT_PER_MINUTE for one bucket of routes."""

    def dependency(request: Request) -> None:
        limit = get_settings().rate_limit_per_minute
        if limit <= 0:
            return
        client = request.client.host if request.client else "unknown"
        retry_after = limiter.hit(client, bucket, limit)
        if retry_after is not None:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait and try again.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
