from __future__ import annotations

from app.models.activity import ActivityRecord
from app.repositories.activity_repository import ActivityRepository


class SQLiteActivityLogger:
    def __init__(self, activity_repository: ActivityRepository) -> None:
        self._activity_repository = activity_repository

    def log(self, record: ActivityRecord) -> None:
        self._activity_repository.insert(record)
