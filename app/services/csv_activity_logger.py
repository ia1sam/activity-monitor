from __future__ import annotations

import csv
from pathlib import Path

from app.models.activity import ActivityRecord


class CsvActivityLogger:
    _header = [
        "start_time",
        "end_time",
        "duration_sec",
        "process",
        "window_title",
        "domain",
        "idle",
        "keyboard_count",
        "mouse_moves",
        "mouse_clicks",
        "hour",
        "day_of_week",
        "predicted_category",
        "model_version",
        "label",
    ]

    def __init__(self, output_path: Path) -> None:
        self._output_path = output_path

    def log(self, record: ActivityRecord) -> None:
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = self._output_path.exists()
        with self._output_path.open("a", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            if not file_exists or file.tell() == 0:
                writer.writerow(self._header)
            writer.writerow(self._to_row(record))

    def _to_row(self, record: ActivityRecord) -> list[object]:
        snapshot = record.snapshot
        return [
            snapshot.start_time.isoformat(),
            snapshot.end_time.isoformat(),
            round(snapshot.duration_sec, 3),
            snapshot.process_name,
            snapshot.window_title,
            snapshot.domain,
            snapshot.is_idle,
            snapshot.keyboard_count,
            snapshot.mouse_moves,
            snapshot.mouse_clicks,
            snapshot.hour,
            snapshot.day_of_week,
            record.predicted_category or "",
            record.model_version or "",
            record.label or "",
        ]
