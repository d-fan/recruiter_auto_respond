import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from .error_handling import is_transient_error

T = TypeVar("T")


class BaseClient:
    """Base client with common functionality for Google API clients."""

    def __init__(self, service: Any, parallel_limit: int = 1) -> None:
        self.service = service
        self.semaphore = asyncio.Semaphore(parallel_limit)
        self._retry_config = AsyncRetrying(
            retry=retry_if_exception(is_transient_error),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=4, max=10),
            reraise=True,
        )

    async def _run_async(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run a blocking function in a thread with retry and semaphore."""

        async def _execute() -> T:
            async with self.semaphore:
                return await asyncio.to_thread(func, *args, **kwargs)

        return await self._retry_config(_execute)
