"""Tests for the shared DomainRateLimiter (Phase 1.2)."""

import asyncio
import time

from comp_synth.utils.rate_limiter import DomainRateLimiter


class TestDomainRateLimiter:
    def test_no_delay_on_first_access(self):
        async def run():
            limiter = DomainRateLimiter(min_interval=0.5)
            start = time.monotonic()
            await limiter.acquire("example.com")
            elapsed = time.monotonic() - start
            assert elapsed < 0.1

        asyncio.run(run())

    def test_delays_second_access_same_domain(self):
        async def run():
            limiter = DomainRateLimiter(min_interval=0.2)
            await limiter.acquire("example.com")
            start = time.monotonic()
            await limiter.acquire("example.com")
            elapsed = time.monotonic() - start
            assert elapsed >= 0.15

        asyncio.run(run())

    def test_no_delay_for_different_domains(self):
        async def run():
            limiter = DomainRateLimiter(min_interval=1.0)
            await limiter.acquire("a.com")
            start = time.monotonic()
            await limiter.acquire("b.com")
            elapsed = time.monotonic() - start
            assert elapsed < 0.1

        asyncio.run(run())

    def test_lock_contention_serializes_concurrent_access(self):
        async def run():
            limiter = DomainRateLimiter(min_interval=0.15)
            order: list[int] = []

            async def task(idx: int) -> None:
                await limiter.acquire("example.com")
                order.append(idx)

            await asyncio.gather(task(0), task(1), task(2))
            assert order == [0, 1, 2]

        asyncio.run(run())

    def test_different_domains_parallel(self):
        async def run():
            limiter = DomainRateLimiter(min_interval=0.3)
            order: list[str] = []

            async def task(domain: str) -> None:
                await limiter.acquire(domain)
                order.append(domain)

            start = time.monotonic()
            await asyncio.gather(
                task("a.com"),
                task("b.com"),
                task("c.com"),
            )
            elapsed = time.monotonic() - start
            assert len(order) == 3
            assert elapsed < 0.2  # All parallel, no serial delays

        asyncio.run(run())
