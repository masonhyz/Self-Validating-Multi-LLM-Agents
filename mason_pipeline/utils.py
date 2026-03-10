import re
import signal
from contextlib import contextmanager


@contextmanager
def timeout(duration: int):
    """SIGALRM-based timeout context manager (Unix/macOS only)."""
    def _handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {duration} seconds")

    signal.signal(signal.SIGALRM, _handler)
    signal.alarm(duration)
    try:
        yield
    finally:
        signal.alarm(0)


def collapse_newlines(text: str) -> str:
    """Collapse runs of 3+ newlines to 2, then strip leading/trailing whitespace."""
    return re.sub(r"\n{3,}", "\n\n", text).strip()
