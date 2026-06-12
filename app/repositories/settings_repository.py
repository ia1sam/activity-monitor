from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.monitoring.config import CollectorSettings


class SettingsRepository:
    def __init__(self, path: Path = Path("app_settings.json")) -> None:
        self._path = path

    def load(self, defaults: CollectorSettings | None = None) -> CollectorSettings:
        settings = defaults or CollectorSettings()
        if not self._path.exists():
            return settings

        with self._path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        for field_name in self._serializable_fields():
            if field_name not in data:
                continue
            value = data[field_name]
            current_value = getattr(settings, field_name)
            if isinstance(current_value, Path):
                value = Path(value)
            setattr(settings, field_name, value)
        return settings

    def save(self, settings: CollectorSettings) -> None:
        data: dict[str, Any] = {}
        for field_name in self._serializable_fields():
            value = getattr(settings, field_name)
            data[field_name] = str(value) if isinstance(value, Path) else value

        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def _serializable_fields(self) -> tuple[str, ...]:
        return (
            "output_path",
            "database_path",
            "log_path",
            "model_path",
            "label_encoder_path",
            "model_info_path",
            "model_version",
            "idle_threshold_sec",
            "poll_interval_sec",
            "min_duration_sec",
            "browser_min_duration_sec",
            "min_idle_duration_sec",
            "url_receiver_port",
            "url_freshness_sec",
            "domain_debug_enabled",
            "classification_enabled",
            "storage_enabled",
            "procrastination_notifications_enabled",
            "procrastination_threshold_min",
            "category_display_settings",
            "custom_training_categories",
            "move_threshold_px",
        )
