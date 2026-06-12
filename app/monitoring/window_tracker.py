from __future__ import annotations

import psutil
import win32gui
import win32process

from app.models.activity import ActiveWindowInfo
from app.monitoring.config import CollectorSettings


class WindowTracker:
    def __init__(self, settings: CollectorSettings) -> None:
        self._settings = settings

    def get_active_window_info(self) -> ActiveWindowInfo | None:
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return None

            title = win32gui.GetWindowText(hwnd).strip()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_name = psutil.Process(pid).name()
            process_key = process_name.lower()

            if process_key == "explorer.exe" and not title:
                return ActiveWindowInfo(title="Desktop", process_name=process_name)

            if self._is_ignored_process(process_name):
                return None

            if not title and process_key in self._settings.system_processes:
                return None

            return ActiveWindowInfo(title=title, process_name=process_name)
        except Exception:
            return None

    def clean_window_title(self, title: str) -> str:
        if not title:
            return ""
        if " - " in title:
            return title.split(" - ")[0].strip()[:100]
        if "\\" in title or "/" in title:
            return title.split("\\")[-1].split("/")[-1].strip()[:100]
        return title[:100]

    def _is_ignored_process(self, process_name: str | None) -> bool:
        if not process_name:
            return True
        return process_name.lower() in self._settings.ignored_processes
