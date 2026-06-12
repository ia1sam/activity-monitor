from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from flask import Flask, request


@dataclass(frozen=True)
class BrowserUrlState:
    url: str
    title: str
    tab_id: int | None
    window_id: int | None
    reason: str
    updated_at: datetime


class BrowserUrlReceiver:
    def __init__(self, port: int = 5000, log_path: Path = Path("log.txt"), debug_enabled: bool = False) -> None:
        self._port = port
        self._log_path = log_path
        self._debug_enabled = debug_enabled
        self._app = Flask(__name__)
        self._current_url = "unknown"
        self._current_title = ""
        self._tab_id: int | None = None
        self._window_id: int | None = None
        self._reason = ""
        self._last_url_update = datetime.min
        self._recent_states: deque[BrowserUrlState] = deque(maxlen=100)
        self._lock = threading.Lock()
        self._started = False
        self._register_routes()

    @property
    def current_url(self) -> str:
        with self._lock:
            return self._current_url

    @property
    def last_url_update(self) -> datetime:
        with self._lock:
            return self._last_url_update

    @property
    def current_title(self) -> str:
        with self._lock:
            return self._current_title

    def state(self) -> BrowserUrlState:
        with self._lock:
            return BrowserUrlState(
                url=self._current_url,
                title=self._current_title,
                tab_id=self._tab_id,
                window_id=self._window_id,
                reason=self._reason,
                updated_at=self._last_url_update,
            )

    def recent_states(self) -> list[BrowserUrlState]:
        with self._lock:
            return list(self._recent_states)

    def reset(self) -> None:
        with self._lock:
            self._current_url = "unknown"
            self._current_title = ""
            self._tab_id = None
            self._window_id = None
            self._reason = ""
            self._last_url_update = datetime.min

    def start(self) -> None:
        if self._started:
            return
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        self._started = True

    def _register_routes(self) -> None:
        @self._app.route("/url", methods=["POST"])
        def receive_url() -> tuple[str, int]:
            data = request.get_json()
            if data and "url" in data:
                with self._lock:
                    self._current_url = data["url"]
                    self._current_title = data.get("title") or ""
                    self._tab_id = data.get("tabId")
                    self._window_id = data.get("windowId")
                    self._reason = data.get("reason") or ""
                    self._last_url_update = datetime.now()
                    self._recent_states.append(
                        BrowserUrlState(
                            url=self._current_url,
                            title=self._current_title,
                            tab_id=self._tab_id,
                            window_id=self._window_id,
                            reason=self._reason,
                            updated_at=self._last_url_update,
                        )
                    )
                    self._write_debug_log(
                        "URL_RECEIVED "
                        f"reason={self._reason!r} tab={self._tab_id} window={self._window_id} "
                        f"title={self._current_title!r} url={self._current_url!r}"
                    )
            return "ok", 200

    def _run(self) -> None:
        self._app.run(port=self._port, debug=False, use_reloader=False)

    def _write_debug_log(self, message: str) -> None:
        if not self._debug_enabled:
            return
        try:
            with self._log_path.open("a", encoding="utf-8") as file:
                file.write(f"{datetime.now().isoformat()} | {message}\n")
        except Exception:
            pass
