from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteDataAccess:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def connect(self) -> sqlite3.Connection:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    duration_sec REAL NOT NULL,
                    process TEXT NOT NULL,
                    window_title TEXT,
                    domain TEXT,
                    idle INTEGER NOT NULL,
                    keyboard_count INTEGER NOT NULL,
                    mouse_moves INTEGER NOT NULL,
                    mouse_clicks INTEGER NOT NULL,
                    hour INTEGER NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    predicted_category TEXT,
                    model_version TEXT,
                    label TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_activity_records_start_time
                ON activity_records(start_time)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_activity_records_effective_category
                ON activity_records(COALESCE(label, predicted_category))
                """
            )
