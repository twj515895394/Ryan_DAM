"""Small filesystem helpers shared by asset services."""

from __future__ import annotations

import os
import time
from pathlib import Path

from backend.app.core.errors import ApiError


def replace_with_retry(source: Path, destination: Path, *, error_code: str, error_prefix: str,
                       attempts: int = 4, delay: float = 0.15) -> None:
    """os.replace with a bounded retry for Windows sharing violations.

    A concurrent reader (e.g. the thumbnail worker) can briefly hold the file
    open; instead of failing the user's action we retry for ~0.5s.
    """
    last_error: OSError | None = None
    for _ in range(attempts):
        try:
            os.replace(source, destination)
            return
        except OSError as error:
            last_error = error
            time.sleep(delay)
    raise ApiError(error_code, f"{error_prefix}：{last_error}", 400) from last_error
