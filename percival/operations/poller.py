"""Explicitly invoked read-only polling; no background daemon or auto-repair."""
from __future__ import annotations
import time
from collections.abc import Callable
from .health import Check, report


def poll(interval_seconds: float = 60, *, iterations: int = 1, probe: Callable[[], list[Check]] = report, emit: Callable[[list[Check]], None] | None = None, sleep: Callable[[float], None] = time.sleep) -> None:
    if not 5 <= interval_seconds <= 86400 or iterations < 1:
        raise ValueError("Polling interval must be 5-86400 seconds and iterations >= 1")
    for index in range(iterations):
        checks = probe()
        if emit:
            emit(checks)
        if index + 1 < iterations:
            sleep(interval_seconds)
