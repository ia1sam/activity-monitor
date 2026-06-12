from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ActivitySnapshot:
    start_time: datetime
    end_time: datetime
    duration_sec: float
    process_name: str
    window_title: str
    domain: str
    is_idle: bool
    keyboard_count: int
    mouse_moves: int
    mouse_clicks: int
    hour: int
    day_of_week: int


@dataclass(frozen=True)
class ActivityRecord:
    snapshot: ActivitySnapshot
    predicted_category: str | None = None
    model_version: str | None = None
    label: str | None = None

    @property
    def effective_category(self) -> str:
        return self.label or self.predicted_category or "unknown"


@dataclass(frozen=True)
class ActiveWindowInfo:
    title: str
    process_name: str
