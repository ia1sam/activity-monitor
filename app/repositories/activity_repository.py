from __future__ import annotations

import sqlite3
from datetime import datetime

from app.models.activity import ActivityRecord, ActivitySnapshot
from app.repositories.sqlite_data_access import SQLiteDataAccess


class ActivityRepository:
    def __init__(self, data_access: SQLiteDataAccess) -> None:
        self._data_access = data_access

    def insert(self, record: ActivityRecord) -> int:
        snapshot = record.snapshot
        with self._data_access.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO activity_records (
                    start_time, end_time, duration_sec, process, window_title,
                    domain, idle, keyboard_count, mouse_moves, mouse_clicks,
                    hour, day_of_week, predicted_category, model_version, label
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.start_time.isoformat(),
                    snapshot.end_time.isoformat(),
                    snapshot.duration_sec,
                    snapshot.process_name,
                    snapshot.window_title,
                    snapshot.domain,
                    int(snapshot.is_idle),
                    snapshot.keyboard_count,
                    snapshot.mouse_moves,
                    snapshot.mouse_clicks,
                    snapshot.hour,
                    snapshot.day_of_week,
                    record.predicted_category,
                    record.model_version,
                    record.label,
                ),
            )
            return int(cursor.lastrowid)

    def query_by_period(self, start: datetime, end: datetime) -> list[ActivityRecord]:
        with self._data_access.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM activity_records
                WHERE start_time >= ? AND start_time < ?
                ORDER BY start_time
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def update_label(self, record_id: int, label: str | None) -> None:
        with self._data_access.connect() as connection:
            connection.execute(
                """
                UPDATE activity_records
                SET label = ?
                WHERE id = ?
                """,
                (label, record_id),
            )

    def count_by_label(self, label: str) -> int:
        with self._data_access.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS records_count
                FROM activity_records
                WHERE label = ?
                """,
                (label,),
            ).fetchone()
        return int(row["records_count"])

    def clear_label_value(self, label: str) -> int:
        with self._data_access.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE activity_records
                SET label = NULL
                WHERE label = ?
                """,
                (label,),
            )
            return int(cursor.rowcount)

    def aggregate_by_category(
        self,
        start: datetime,
        end: datetime,
        category: str | None = None,
    ) -> list[dict[str, object]]:
        category_filter, params = self._category_filter(category)
        with self._data_access.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    COALESCE(label, predicted_category, 'unknown') AS category,
                    COUNT(*) AS records_count,
                    SUM(duration_sec) AS duration_sec
                FROM activity_records
                WHERE start_time >= ? AND start_time < ?
                {category_filter}
                GROUP BY COALESCE(label, predicted_category, 'unknown')
                ORDER BY duration_sec DESC
                """,
                (start.isoformat(), end.isoformat(), *params),
            ).fetchall()
        return [dict(row) for row in rows]

    def aggregate_by_process(
        self,
        start: datetime,
        end: datetime,
        limit: int = 10,
        category: str | None = None,
    ) -> list[dict[str, object]]:
        category_filter, params = self._category_filter(category)
        with self._data_access.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    process AS process_name,
                    COUNT(*) AS records_count,
                    SUM(duration_sec) AS duration_sec
                FROM activity_records
                WHERE start_time >= ? AND start_time < ?
                {category_filter}
                GROUP BY process
                ORDER BY duration_sec DESC
                LIMIT ?
                """,
                (start.isoformat(), end.isoformat(), *params, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def aggregate_by_domain(
        self,
        start: datetime,
        end: datetime,
        limit: int = 10,
        category: str | None = None,
    ) -> list[dict[str, object]]:
        category_filter, params = self._category_filter(category)
        with self._data_access.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    COALESCE(NULLIF(domain, ''), 'unknown') AS domain,
                    COUNT(*) AS records_count,
                    SUM(duration_sec) AS duration_sec
                FROM activity_records
                WHERE start_time >= ? AND start_time < ?
                {category_filter}
                GROUP BY COALESCE(NULLIF(domain, ''), 'unknown')
                ORDER BY duration_sec DESC
                LIMIT ?
                """,
                (start.isoformat(), end.isoformat(), *params, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def aggregate_timeline(
        self,
        start: datetime,
        end: datetime,
        bucket: str,
        category: str | None = None,
    ) -> list[dict[str, object]]:
        category_filter, params = self._category_filter(category)
        expression = "substr(start_time, 1, 10)" if bucket == "day" else "substr(start_time, 1, 13) || ':00'"
        with self._data_access.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    {expression} AS period,
                    COUNT(*) AS records_count,
                    SUM(duration_sec) AS duration_sec
                FROM activity_records
                WHERE start_time >= ? AND start_time < ?
                {category_filter}
                GROUP BY {expression}
                ORDER BY period
                """,
                (start.isoformat(), end.isoformat(), *params),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_summary(self, start: datetime, end: datetime, category: str | None = None) -> dict[str, object]:
        category_filter, params = self._category_filter(category)
        with self._data_access.connect() as connection:
            row = connection.execute(
                f"""
                SELECT
                    COUNT(*) AS records_count,
                    COALESCE(SUM(duration_sec), 0) AS duration_sec,
                    COUNT(label) AS labeled_count
                FROM activity_records
                WHERE start_time >= ? AND start_time < ?
                {category_filter}
                """,
                (start.isoformat(), end.isoformat(), *params),
            ).fetchone()
        return dict(row)

    def export_rows_by_period(
        self,
        start: datetime,
        end: datetime,
        category: str | None = None,
    ) -> list[dict[str, object]]:
        category_filter, params = self._category_filter(category)
        with self._data_access.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    id, start_time, end_time, duration_sec, process,
                    window_title, domain, idle, keyboard_count, mouse_moves,
                    mouse_clicks, hour, day_of_week, predicted_category,
                    model_version, label,
                    COALESCE(label, predicted_category, 'unknown') AS effective_category
                FROM activity_records
                WHERE start_time >= ? AND start_time < ?
                {category_filter}
                ORDER BY start_time
                """,
                (start.isoformat(), end.isoformat(), *params),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_recent_rows(
        self,
        limit: int = 100,
        category: str | None = None,
        unlabeled_only: bool = False,
    ) -> list[dict[str, object]]:
        category_filter, params = self._category_filter(category)
        unlabeled_filter = "AND (label IS NULL OR label = '')" if unlabeled_only else ""
        with self._data_access.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    id, start_time, end_time, duration_sec, process,
                    window_title, domain, idle, keyboard_count, mouse_moves,
                    mouse_clicks, hour, day_of_week, predicted_category,
                    model_version, label,
                    COALESCE(label, predicted_category, 'unknown') AS effective_category
                FROM activity_records
                WHERE 1 = 1
                {category_filter}
                {unlabeled_filter}
                ORDER BY start_time DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def export_labeled_training_rows(self) -> list[dict[str, object]]:
        with self._data_access.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    start_time, end_time, duration_sec, process, window_title,
                    domain, idle, keyboard_count, mouse_moves, mouse_clicks,
                    hour, day_of_week, label
                FROM activity_records
                WHERE label IS NOT NULL AND label != ''
                ORDER BY start_time
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> ActivityRecord:
        snapshot = ActivitySnapshot(
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]),
            duration_sec=float(row["duration_sec"]),
            process_name=row["process"],
            window_title=row["window_title"] or "",
            domain=row["domain"] or "unknown",
            is_idle=bool(row["idle"]),
            keyboard_count=int(row["keyboard_count"]),
            mouse_moves=int(row["mouse_moves"]),
            mouse_clicks=int(row["mouse_clicks"]),
            hour=int(row["hour"]),
            day_of_week=int(row["day_of_week"]),
        )
        return ActivityRecord(
            snapshot=snapshot,
            predicted_category=row["predicted_category"],
            model_version=row["model_version"],
            label=row["label"],
        )

    def _category_filter(self, category: str | None) -> tuple[str, tuple[str, ...]]:
        if not category or category == "all":
            return "", ()
        return "AND COALESCE(label, predicted_category, 'unknown') = ?", (category,)
