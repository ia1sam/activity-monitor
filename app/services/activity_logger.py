from __future__ import annotations

from typing import Protocol

from app.models.activity import ActivityRecord


class ActivityLogger(Protocol):
    def log(self, record: ActivityRecord) -> None:
        pass
