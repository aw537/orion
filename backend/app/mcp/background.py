"""Background task manager — tracked task set with graceful drain on shutdown."""
import asyncio
import logging

logger = logging.getLogger(__name__)

_tasks: set[asyncio.Task] = set()


def spawn(coro, *, name: str | None = None):
    """Schedule a coroutine as a tracked background task."""
    task = asyncio.ensure_future(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    if name:
        task.set_name(name)


async def drain(timeout: float = 10.0):
    """Wait for all pending background tasks to complete, with timeout."""
    if not _tasks:
        return
    pending = list(_tasks)
    logger.info(f"Draining {len(pending)} background tasks (timeout={timeout}s)")
    done, still_pending = await asyncio.wait(pending, timeout=timeout)
    if still_pending:
        logger.warning(f"{len(still_pending)} background tasks did not complete in time, cancelling")
        for t in still_pending:
            t.cancel()
        await asyncio.gather(*still_pending, return_exceptions=True)
    logger.info(f"Background task drain complete: {len(done)} finished, {len(still_pending)} cancelled")
