from __future__ import annotations

from collections.abc import Callable

from app.models.activity import ActivityRecord
from app.services.activity_logger import ActivityLogger


class ConditionalActivityLogger:
    def __init__(self, logger: ActivityLogger, enabled: Callable[[], bool]) -> None:
        self._logger = logger
        self._enabled = enabled

    def log(self, record: ActivityRecord) -> None:
        if self._enabled():
            self._logger.log(record)
