from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

from app.monitoring.config import CollectorSettings
from app.monitoring.url_receiver import BrowserUrlReceiver, BrowserUrlState


class DomainResolver:
    def __init__(self, settings: CollectorSettings, url_receiver: BrowserUrlReceiver) -> None:
        self._settings = settings
        self._url_receiver = url_receiver

    def is_browser(self, process_name: str) -> bool:
        return bool(process_name) and process_name.lower() in self._settings.browser_processes

    def resolve(self, process_name: str, window_title: str) -> str:
        if not self.is_browser(process_name):
            return "unknown"

        title_domain = self._get_domain_from_title(window_title)
        best_state = self._find_best_state(window_title, title_domain)
        if best_state is not None:
            best_domain = self._get_domain_from_url(best_state.url)
            return self._finish(
                best_domain,
                "recent_state_match",
                window_title,
                title_domain,
                best_domain,
                best_state,
            )

        state = self._url_receiver.state()
        current_domain = self._get_domain_from_url(state.url)
        if current_domain != "unknown":
            if not state.title and title_domain == "unknown" and current_domain in {"google.com", "yandex.ru"}:
                return self._finish(
                    "unknown",
                    "generic_url_without_extension_title",
                    window_title,
                    title_domain,
                    current_domain,
                    state,
                )
            if state.title and not self._title_matches(window_title, state.title):
                return self._finish(
                    title_domain,
                    "extension_title_mismatch",
                    window_title,
                    title_domain,
                    current_domain,
                    state,
                )
            if self._title_matches(window_title, state.title) or self._is_fresh(state.updated_at):
                return self._finish(
                    current_domain,
                    "url_title_match_or_fresh",
                    window_title,
                    title_domain,
                    current_domain,
                    state,
                )

        return self._finish(
            title_domain,
            "title_fallback",
            window_title,
            title_domain,
            current_domain,
            state,
        )

    def _find_best_state(self, window_title: str, title_domain: str) -> BrowserUrlState | None:
        recent_states = getattr(self._url_receiver, "recent_states", lambda: [])()
        for state in reversed(recent_states):
            domain = self._get_domain_from_url(state.url)
            if domain == "unknown":
                continue
            if self._title_matches(window_title, state.title):
                return state
            if title_domain != "unknown" and self._same_site(title_domain, domain):
                return state
        return None

    def _get_domain_from_url(self, current_url: str) -> str:
        if not current_url or current_url == "unknown":
            return "unknown"
        try:
            parsed = urlparse(current_url)
            domain = parsed.netloc
            if not domain:
                return "unknown"
            if domain in {"extensions", "newtab", "settings", "history", "downloads", "bookmarks"}:
                return "unknown"
            return self._clean_domain(domain)
        except Exception:
            return "unknown"

    def _get_domain_from_title(self, title: str) -> str:
        if not title:
            return "unknown"
        title_lower = self._normalize_title(title)
        literal_domain = self._extract_literal_domain(title_lower)
        if literal_domain != "unknown":
            return literal_domain
        explicit_domain = self._get_explicit_domain_from_title(title_lower)
        if explicit_domain != "unknown":
            return explicit_domain
        for keyword, domain in self._settings.title_domain_map.items():
            if keyword in title_lower:
                return domain
        return "unknown"

    def _extract_literal_domain(self, title_lower: str) -> str:
        matches = re.findall(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", title_lower)
        for match in matches:
            domain = self._clean_domain(match)
            if domain not in {"google.com"}:
                return domain
        return "unknown"

    def _get_explicit_domain_from_title(self, title_lower: str) -> str:
        if "telegram web" in title_lower:
            return "web.telegram.org"
        if "github" in title_lower:
            return "github.com"
        if "rutube" in title_lower:
            return "rutube.ru"
        if "youtube" in title_lower:
            return "youtube.com"
        if "chatgpt" in title_lower or "openai" in title_lower:
            return "chatgpt.com"
        if "deepseek" in title_lower:
            return "chat.deepseek.com"
        if "\u044f\u043d\u0434\u0435\u043a\u0441\u00a0\u0434\u0438\u0441\u043a" in title_lower:
            return "disk.yandex.ru"
        if "\u044f\u043d\u0434\u0435\u043a\u0441 \u0434\u0438\u0441\u043a" in title_lower or "yandex disk" in title_lower:
            return "disk.yandex.ru"
        if "\u044f\u043d\u0434\u0435\u043a\u0441 \u043c\u0443\u0437\u044b\u043a\u0430" in title_lower or "yandex music" in title_lower:
            return "music.yandex.ru"
        if "\u044f\u043d\u0434\u0435\u043a\u0441 \u043f\u0435\u0440\u0435\u0432\u043e\u0434\u0447\u0438\u043a" in title_lower:
            return "translate.yandex.ru"
        if "yandex translate" in title_lower:
            return "translate.yandex.ru"
        return "unknown"

    def _clean_domain(self, domain: str) -> str:
        domain = domain.lower()
        for prefix in ["www.", "m.", "mobile.", "touch."]:
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        return domain

    def _same_site(self, left: str, right: str) -> bool:
        return self._registrable_domain(left) == self._registrable_domain(right)

    def _registrable_domain(self, domain: str) -> str:
        domain = self._clean_domain(domain)
        parts = [part for part in domain.split(".") if part]
        if len(parts) <= 2:
            return domain
        return ".".join(parts[-2:])

    def _is_fresh(self, updated_at: datetime) -> bool:
        return (datetime.now() - updated_at).total_seconds() < self._settings.url_freshness_sec

    def _title_matches(self, window_title: str, browser_title: str) -> bool:
        if not window_title or not browser_title:
            return False
        left = self._normalize_title(window_title)
        right = self._normalize_title(browser_title)
        if not left or not right:
            return False
        return left in right or right in left

    def _normalize_title(self, title: str) -> str:
        title = title.lower().strip()
        for suffix in [
            " - google chrome",
            " - chrome",
            " - microsoft edge",
            " - mozilla firefox",
            " - opera",
        ]:
            if title.endswith(suffix):
                title = title[: -len(suffix)]
        return " ".join(title.split())

    def _finish(
        self,
        selected_domain: str,
        reason: str,
        window_title: str,
        title_domain: str,
        url_domain: str,
        state,
    ) -> str:
        self._write_debug_log(
            "DOMAIN_RESOLVE "
            f"selected={selected_domain!r} reason={reason} "
            f"window_title={window_title!r} title_domain={title_domain!r} "
            f"url_domain={url_domain!r} ext_title={getattr(state, 'title', '')!r} "
            f"ext_reason={getattr(state, 'reason', '')!r}"
        )
        return selected_domain

    def _write_debug_log(self, message: str) -> None:
        if not self._settings.domain_debug_enabled:
            return
        try:
            with self._settings.log_path.open("a", encoding="utf-8") as file:
                file.write(f"{datetime.now().isoformat()} | {message}\n")
        except Exception:
            pass
