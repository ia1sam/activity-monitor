from __future__ import annotations

from collections import deque
from threading import Lock

from app.models.activity import ActivityRecord


class SessionActivityStore:
    def __init__(self, max_records: int = 500) -> None:
        self._records: deque[ActivityRecord] = deque(maxlen=max_records)
        self._lock = Lock()

    def log(self, record: ActivityRecord) -> None:
        with self._lock:
            self._records.appendleft(record)

    def get_recent_rows(
        self,
        limit: int = 100,
        category: str | None = None,
        unlabeled_only: bool = False,
    ) -> list[dict[str, object]]:
        with self._lock:
            records = list(self._records)

        rows = [self._record_to_row(index, record) for index, record in enumerate(records, start=1)]
        if category and category != "all":
            rows = [row for row in rows if row["effective_category"] == category]
        if unlabeled_only:
            rows = [row for row in rows if not row["label"]]
        return rows[:limit]

    def _record_to_row(self, index: int, record: ActivityRecord) -> dict[str, object]:
        snapshot = record.snapshot
        return {
            "id": f"session-{index}",
            "start_time": snapshot.start_time.isoformat(),
            "end_time": snapshot.end_time.isoformat(),
            "duration_sec": snapshot.duration_sec,
            "process": snapshot.process_name,
            "window_title": snapshot.window_title,
            "domain": snapshot.domain,
            "idle": int(snapshot.is_idle),
            "keyboard_count": snapshot.keyboard_count,
            "mouse_moves": snapshot.mouse_moves,
            "mouse_clicks": snapshot.mouse_clicks,
            "hour": snapshot.hour,
            "day_of_week": snapshot.day_of_week,
            "predicted_category": record.predicted_category,
            "model_version": record.model_version,
            "label": record.label,
            "effective_category": record.effective_category,
        }
