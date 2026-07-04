from asyncio import sleep
from collections.abc import Awaitable, Callable
from logging import Logger, getLogger
from typing import TypeVar

from pyrogram.errors import BadRequest, RPCError

try:
    from pyrogram.errors import FloodPremiumWait, FloodWait
except ImportError:  # pragma: no cover - compatibility
    from pyrogram.errors import FloodWait

    FloodPremiumWait = FloodWait

T = TypeVar("T")

# Exponential backoff defaults (seconds).
_BACKOFF_BASE: float = 2.0
_BACKOFF_CAP: float = 30.0
_DEFAULT_LOG = getLogger(__name__)


def _backoff_delay(attempt: int) -> float:
    """Return exponential delay: 2, 4, 8, 16, … capped at ``_BACKOFF_CAP``."""
    return min(_BACKOFF_BASE * (2 ** (attempt - 1)), _BACKOFF_CAP)


def _emit_retry(
    log_retry: Callable[[str], object] | Logger | None,
    message: str,
) -> None:
    if isinstance(log_retry, Logger):
        log_retry.info(message)
    elif log_retry is not None:
        log_retry(message)
    else:
        _DEFAULT_LOG.info(message)


async def run_with_retry(
    action: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 5,
    log_retry: Callable[[str], object] | Logger | None = None,
) -> T:
    """Execute *action* with automatic retry on Telegram errors.

    Retry strategy:
    * **FloodWait / FloodPremiumWait** — sleep for the duration
      Telegram specifies, then retry.
    * **RPCError** (excluding *BadRequest*) — exponential backoff
      starting at 2 s, doubling each attempt, capped at 30 s.
    * **TimeoutError / OSError** — exponential backoff (network blips).
    * **BadRequest** — always propagated immediately.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return await action()
        except BadRequest:
            raise
        except (FloodWait, FloodPremiumWait) as wait_exc:
            if attempt >= max_attempts:
                raise
            wait_for = max(int(getattr(wait_exc, "value", 0)), 1)
            _emit_retry(
                log_retry,
                f"[retry] FloodWait: sleeping {wait_for}s "
                f"(attempt {attempt}/{max_attempts})",
            )
            await sleep(wait_for)
        except (TimeoutError, OSError) as exc:
            if attempt >= max_attempts:
                raise
            delay = _backoff_delay(attempt)
            _emit_retry(
                log_retry,
                f"[retry] {type(exc).__name__}: backoff {delay:.1f}s "
                f"(attempt {attempt}/{max_attempts})",
            )
            await sleep(delay)
        except RPCError as exc:
            if attempt >= max_attempts:
                raise
            delay = _backoff_delay(attempt)
            _emit_retry(
                log_retry,
                f"[retry] {type(exc).__name__}: backoff {delay:.1f}s "
                f"(attempt {attempt}/{max_attempts})",
            )
            await sleep(delay)


# Backward-compatible alias.
run_with_floodwait_retry = run_with_retry
