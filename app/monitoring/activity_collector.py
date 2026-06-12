from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Callable

from app.ml.activity_classifier import ActivityClassifier
from app.models.activity import ActiveWindowInfo, ActivityRecord, ActivitySnapshot
from app.monitoring.config import CollectorSettings
from app.monitoring.domain_resolver import DomainResolver
from app.monitoring.input_tracker import InputTracker
from app.monitoring.url_receiver import BrowserUrlReceiver
from app.monitoring.window_tracker import WindowTracker
from app.services.activity_logger import ActivityLogger


class ActivityCollector:
    def __init__(
        self,
        settings: CollectorSettings,
        input_tracker: InputTracker,
        window_tracker: WindowTracker,
        domain_resolver: DomainResolver,
        url_receiver: BrowserUrlReceiver,
        activity_logger: ActivityLogger,
        classifier: ActivityClassifier | None = None,
        procrastination_callback: Callable[[str, str], None] | None = None,
    ) -> None:
        self._settings = settings
        self._input_tracker = input_tracker
        self._window_tracker = window_tracker
        self._domain_resolver = domain_resolver
        self._url_receiver = url_receiver
        self._activity_logger = activity_logger
        self._classifier = classifier
        self._procrastination_callback = procrastination_callback
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._pause_event.clear()
        self._input_tracker.start()
        self._url_receiver.start()
        self._thread = threading.Thread(target=self.run_forever, daemon=True)
        self._thread.start()
        self._write_log("STARTED")

    def set_classifier(self, classifier: ActivityClassifier | None) -> None:
        self._classifier = classifier

    def set_procrastination_callback(self, callback: Callable[[str, str], None] | None) -> None:
        self._procrastination_callback = callback

    def stop(self) -> None:
        self._stop_event.set()
        self._write_log("STOP_REQUESTED")

    def pause(self) -> None:
        self._pause_event.set()
        self._write_log("PAUSED")

    def resume(self) -> None:
        self._pause_event.clear()
        self._input_tracker.reset()
        self._write_log("RESUMED")

    def run_forever(self) -> None:
        current_window = self._wait_for_active_window()
        start_time = datetime.now()
        is_idle = False
        procrastination_checked = False

        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                time.sleep(self._settings.poll_interval_sec)
                continue

            new_window = self._window_tracker.get_active_window_info()
            if new_window is None:
                time.sleep(self._settings.poll_interval_sec)
                continue

            now = datetime.now()
            new_idle = self._input_tracker.is_idle(self._settings.idle_threshold_sec)
            window_changed = self._window_changed(current_window, new_window)

            if is_idle and not new_idle:
                self._input_tracker.reset()

            if window_changed or new_idle != is_idle:
                duration_sec = (now - start_time).total_seconds()
                if self._should_write_record(duration_sec, is_idle, current_window):
                    record = self._build_record(current_window, start_time, now, duration_sec, is_idle)
                    self._activity_logger.log(record)

                self._input_tracker.reset()
                current_window = new_window
                start_time = now
                is_idle = new_idle
                procrastination_checked = False

            current_duration_sec = (now - start_time).total_seconds()
            if not procrastination_checked and self._should_check_procrastination(current_duration_sec):
                record = self._build_record(current_window, start_time, now, current_duration_sec, is_idle)
                self._notify_if_procrastination(record)
                procrastination_checked = True

            time.sleep(self._settings.poll_interval_sec)

        self._write_log("STOPPED")

    def _wait_for_active_window(self) -> ActiveWindowInfo:
        while not self._stop_event.is_set():
            window = self._window_tracker.get_active_window_info()
            if window is not None:
                return window
            time.sleep(0.5)
        return ActiveWindowInfo(title="unknown", process_name="unknown")

    def _build_record(
        self,
        window: ActiveWindowInfo,
        start_time: datetime,
        end_time: datetime,
        duration_sec: float,
        is_idle: bool,
    ) -> ActivityRecord:
        counters = self._input_tracker.counters()
        domain = self._domain_resolver.resolve(window.process_name, window.title)
        clean_title = self._window_tracker.clean_window_title(window.title)
        snapshot = ActivitySnapshot(
            start_time=start_time,
            end_time=end_time,
            duration_sec=duration_sec,
            process_name=window.process_name,
            window_title=clean_title,
            domain=domain,
            is_idle=is_idle,
            keyboard_count=counters.keyboard_count,
            mouse_moves=counters.mouse_moves,
            mouse_clicks=counters.mouse_clicks,
            hour=start_time.hour,
            day_of_week=start_time.weekday(),
        )
        predicted_category, model_version = self._predict_category(snapshot)
        return ActivityRecord(snapshot=snapshot, predicted_category=predicted_category, model_version=model_version)

    def _predict_category(self, snapshot: ActivitySnapshot) -> tuple[str, str]:
        if not self._settings.classification_enabled:
            return "unknown", "classification_disabled"

        if self._classifier is not None:
            try:
                return self._classifier.predict(snapshot), self._classifier.model_version
            except Exception as exc:
                self._write_log(f"CLASSIFIER_FALLBACK | {exc}")

        return self._resolve_temporary_category(snapshot), "rule_based_v0"

    def _resolve_temporary_category(self, snapshot: ActivitySnapshot) -> str:
        process_key = snapshot.process_name.lower()
        domain = snapshot.domain.lower()
        if snapshot.is_idle:
            return "idle"
        if process_key in self._settings.system_processes:
            return "system"
        if self._domain_resolver.is_browser(snapshot.process_name):
            if self._is_educational(snapshot.window_title):
                return "learning"
            if self._is_communication_domain(domain):
                return "communication"
            if self._is_entertainment_domain(domain):
                return "entertainment"
            return "work"
        if process_key in {"discord.exe", "telegram.exe"}:
            return "communication"
        if process_key in {"steam.exe", "steamwebhelper.exe"}:
            return "entertainment"
        return "work"

    def _is_communication_domain(self, domain: str) -> bool:
        return any(keyword in domain for keyword in ["telegram", "discord", "vk.com", "mail."])

    def _is_entertainment_domain(self, domain: str) -> bool:
        return any(keyword in domain for keyword in ["youtube", "twitch", "netflix", "rutube", "dzen"])

    def _is_educational(self, title: str) -> bool:
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in self._settings.educational_keywords)

    def _should_write_record(self, duration_sec: float, is_idle: bool, window: ActiveWindowInfo) -> bool:
        if is_idle:
            return duration_sec >= self._settings.min_idle_duration_sec
        if self._domain_resolver.is_browser(window.process_name):
            return duration_sec >= self._settings.browser_min_duration_sec
        return duration_sec >= self._settings.min_duration_sec

    def _window_changed(self, old: ActiveWindowInfo, new: ActiveWindowInfo) -> bool:
        return old.title != new.title or old.process_name != new.process_name

    def _should_check_procrastination(self, duration_sec: float) -> bool:
        if not self._settings.procrastination_notifications_enabled:
            return False
        return duration_sec >= self._settings.procrastination_threshold_min * 60

    def _notify_if_procrastination(self, record: ActivityRecord) -> None:
        if self._procrastination_callback is None:
            return
        category = record.label or record.predicted_category
        if category not in {"entertainment", "idle"}:
            return

        minutes = round(record.snapshot.duration_sec / 60)
        title = "Уведомление о прокрастинации"
        message = (
            f"Категория '{category}' длится около {minutes} мин. "
            "Стоит вернуться к рабочей активности."
        )
        self._procrastination_callback(title, message)

    def _write_log(self, message: str) -> None:
        try:
            with self._settings.log_path.open("a", encoding="utf-8") as file:
                file.write(f"{datetime.now().isoformat()} | {message}\n")
        except Exception:
            pass
