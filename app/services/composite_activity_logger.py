from __future__ import annotations

from app.models.activity import ActivityRecord
from app.services.activity_logger import ActivityLogger


class CompositeActivityLogger:
    def __init__(self, loggers: list[ActivityLogger]) -> None:
        self._loggers = loggers

    def log(self, record: ActivityRecord) -> None:
        for logger in self._loggers:
            logger.log(record)
