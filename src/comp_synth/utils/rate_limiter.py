"""Per-domain rate limiter ensuring minimum interval between requests to the same domain."""

import asyncio
import time


class DomainRateLimiter:
    """Rate-limit concurrent requests so the same domain is hit at most once per *min_interval* seconds."""

    def __init__(self, min_interval: float = 1.0) -> None:
        self._min_interval = min_interval
        self._last_access: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def acquire(self, domain: str) -> None:
        lock = self._locks.setdefault(domain, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            elapsed = now - self._last_access.get(domain, 0.0)
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_access[domain] = time.monotonic()
