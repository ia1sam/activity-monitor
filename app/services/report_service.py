from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from app.monitoring.config import CollectorSettings
from app.repositories.activity_repository import ActivityRepository
from app.services.statistics_service import StatisticsService


class ReportService:
    _activity_report_columns = [
        "id",
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
        "effective_category",
        "category_name",
    ]

    _training_dataset_columns = [
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
        "label",
    ]

    def __init__(self, activity_repository: ActivityRepository, settings: CollectorSettings | None = None) -> None:
        self._activity_repository = activity_repository
        self._statistics_service = StatisticsService(activity_repository)
        self._settings = settings

    def export_activity_csv(self, start: datetime, end: datetime, output_path: Path, category: str | None = None) -> int:
        rows = self._activity_repository.export_rows_by_period(start, end, category)
        self._add_display_categories(rows)
        self._write_csv(output_path, self._activity_report_columns, rows)
        return len(rows)

    def export_activity_json(self, start: datetime, end: datetime, output_path: Path, category: str | None = None) -> int:
        rows = self._activity_repository.export_rows_by_period(start, end, category)
        self._add_display_categories(rows)
        payload = {
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "records_count": len(rows),
            "records": rows,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        return len(rows)

    def export_statistics_pdf(
        self,
        start: datetime,
        end: datetime,
        output_path: Path,
        category: str | None = None,
    ) -> int:
        rows = self._activity_repository.export_rows_by_period(start, end, category)
        if not rows:
            return 0

        stats = self._statistics_service.get_period_statistics(start, end, category)
        self._add_display_categories(rows)
        self._add_display_categories(stats.categories, category_key="category")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_pdf(output_path, start, end, stats.categories, stats.timeline, rows)
        return len(rows)

    def export_training_dataset_csv(self, output_path: Path) -> int:
        rows = self._activity_repository.export_labeled_training_rows()
        self._write_csv(output_path, self._training_dataset_columns, rows)
        return len(rows)

    def _write_csv(self, output_path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def _write_pdf(
        self,
        output_path: Path,
        start: datetime,
        end: datetime,
        categories: list[dict[str, object]],
        timeline: list[dict[str, object]],
        rows: list[dict[str, object]],
    ) -> None:
        from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument

        writer = QPdfWriter(str(output_path))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setResolution(96)

        document = QTextDocument()
        document.setHtml(self._build_pdf_html(start, end, categories, timeline, rows))
        document.print_(writer)

    def _build_pdf_html(
        self,
        start: datetime,
        end: datetime,
        categories: list[dict[str, object]],
        timeline: list[dict[str, object]],
        rows: list[dict[str, object]],
    ) -> str:
        total_duration = sum(float(row.get("duration_sec") or 0) for row in rows)
        total_minutes = total_duration / 60
        category_rows = self._rows_to_html(
            categories,
            ["category", "duration_sec", "records_count"],
            duration_columns={"duration_sec"},
        )
        timeline_rows = self._rows_to_html(
            timeline,
            ["period", "duration_sec", "records_count"],
            duration_columns={"duration_sec"},
        )
        details_rows = self._rows_to_html(
            rows[:100],
            ["start_time", "end_time", "process", "domain", "category_name", "duration_sec"],
            duration_columns={"duration_sec"},
        )
        bars = self._category_bars(categories, total_duration)

        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; font-size: 10pt; color: #1f2933; }}
                h1 {{ font-size: 18pt; }}
                h2 {{ font-size: 13pt; margin-top: 18px; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
                th, td {{ border: 1px solid #cbd5e1; padding: 4px; }}
                th {{ background: #e5edf6; }}
                .muted {{ color: #64748b; }}
                .bar-row {{ margin: 4px 0; }}
                .bar {{ display: inline-block; height: 10px; background: #0f5c9c; }}
            </style>
        </head>
        <body>
            <h1>Отчет по активности</h1>
            <p class="muted">Период: {start:%Y-%m-%d %H:%M} - {end:%Y-%m-%d %H:%M}</p>
            <p>Записей: {len(rows)}<br/>Общее время: {total_minutes:.1f} мин</p>
            <h2>Распределение времени по категориям</h2>
            {bars}
            <table>{category_rows}</table>
            <h2>Динамика активности</h2>
            <table>{timeline_rows}</table>
            <h2>Детализация записей</h2>
            <p class="muted">В PDF выводятся первые 100 записей периода. Полные данные доступны в CSV/JSON.</p>
            <table>{details_rows}</table>
        </body>
        </html>
        """

    def _category_bars(self, categories: list[dict[str, object]], total_duration: float) -> str:
        if total_duration <= 0:
            return "<p>Нет данных</p>"
        items = []
        for row in categories:
            category = row.get("category", "unknown")
            duration = float(row.get("duration_sec") or 0)
            percent = duration / total_duration * 100
            width = max(percent, 1)
            items.append(
                f"<div class='bar-row'>{category}: {percent:.1f}% "
                f"<span class='bar' style='width:{width * 3}px'></span></div>"
            )
        return "".join(items)

    def _add_display_categories(
        self,
        rows: list[dict[str, object]],
        category_key: str = "effective_category",
    ) -> None:
        for row in rows:
            value = row.get(category_key)
            if value is None:
                continue
            row["category_name"] = self._category_display_name(str(value))
            if category_key == "category":
                row["category"] = row["category_name"]

    def _category_display_name(self, code: str) -> str:
        if self._settings is None:
            return code
        config = self._settings.category_display_settings.get(code, {})
        return str(config.get("display_name") or code)

    def _rows_to_html(
        self,
        rows: list[dict[str, object]],
        columns: list[str],
        duration_columns: set[str] | None = None,
    ) -> str:
        duration_columns = duration_columns or set()
        header = "".join(f"<th>{column}</th>" for column in columns)
        body = []
        for row in rows:
            cells = []
            for column in columns:
                value = row.get(column)
                if column in duration_columns:
                    value = f"{float(value or 0) / 60:.1f} мин"
                cells.append(f"<td>{self._escape(value)}</td>")
            body.append(f"<tr>{''.join(cells)}</tr>")
        return f"<tr>{header}</tr>{''.join(body)}"

    def _escape(self, value: object) -> str:
        text = "" if value is None else str(value)
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
