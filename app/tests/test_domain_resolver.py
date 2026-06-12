from __future__ import annotations

from datetime import datetime

from app.monitoring.config import CollectorSettings
from app.monitoring.domain_resolver import DomainResolver


class FakeUrlReceiver:
    def __init__(self, current_url: str, title: str = "") -> None:
        self.current_url = current_url
        self.current_title = title
        self.last_url_update = datetime.now()
        self._states = []

    def add_state(self, url: str, title: str):
        state = self._make_state(url, title, datetime.now())
        self._states.append(state)
        self.current_url = url
        self.current_title = title
        self.last_url_update = state.updated_at
        return self

    def state(self):
        return self._make_state(self.current_url, self.current_title, self.last_url_update)

    def recent_states(self):
        if self._states:
            return list(self._states)
        return [self.state()]

    def _make_state(self, url: str, title: str, updated_at: datetime):
        class State:
            pass

        state = State()
        state.url = url
        state.title = title
        state.reason = "test"
        state.updated_at = updated_at
        return state


def test_title_domain_wins_over_conflicting_fresh_url() -> None:
    resolver = DomainResolver(
        CollectorSettings(),
        FakeUrlReceiver("https://www.google.com/search?q=test", title="Google"),
    )
    assert resolver.resolve("chrome.exe", "ChatGPT - OpenAI") == "chatgpt.com"


def test_fresh_url_is_used_when_title_has_no_domain_hint() -> None:
    resolver = DomainResolver(
        CollectorSettings(),
        FakeUrlReceiver("https://github.com/user/repo", title="Some generic browser title"),
    )
    assert resolver.resolve("chrome.exe", "Some generic browser title") == "github.com"


def test_subdomain_does_not_conflict_with_title_domain() -> None:
    resolver = DomainResolver(
        CollectorSettings(),
        FakeUrlReceiver("https://www.youtube.com/watch?v=1", title="(1175) YouTube"),
    )
    assert resolver.resolve("chrome.exe", "(1175) YouTube") == "youtube.com"


def test_mismatched_extension_title_blocks_fresh_url_without_title_hint() -> None:
    resolver = DomainResolver(
        CollectorSettings(),
        FakeUrlReceiver("https://www.google.com/search?q=test", title="Google"),
    )
    assert resolver.resolve("chrome.exe", "Untitled document") == "unknown"


def test_generic_google_url_without_extension_title_is_not_trusted() -> None:
    resolver = DomainResolver(
        CollectorSettings(),
        FakeUrlReceiver("https://www.google.com/search?q=test", title=""),
    )
    assert resolver.resolve("chrome.exe", "Untitled document") == "unknown"


def test_matching_extension_title_allows_old_url() -> None:
    receiver = FakeUrlReceiver("https://chatgpt.com/c/123", title="ChatGPT")
    receiver.last_url_update = datetime.min
    resolver = DomainResolver(CollectorSettings(), receiver)
    assert resolver.resolve("chrome.exe", "ChatGPT - Google Chrome") == "chatgpt.com"


def test_google_chrome_suffix_does_not_become_google_domain() -> None:
    resolver = DomainResolver(
        CollectorSettings(),
        FakeUrlReceiver("https://web.telegram.org/k/#@proofzzz", title="Telegram Web"),
    )
    assert resolver.resolve("chrome.exe", "Telegram Web - Google Chrome") == "web.telegram.org"


def test_rutube_title_wins_when_extension_already_switched() -> None:
    yandex_disk_title = (
        "\u041f\u0440\u0435\u0434\u0434\u0438\u043f\u043b\u043e\u043c\u043d\u0430\u044f "
        "\u043f\u0440\u0430\u043a\u0442\u0438\u043a\u0430 — \u042f\u043d\u0434\u0435\u043a\u0441\u00a0\u0414\u0438\u0441\u043a"
    )
    resolver = DomainResolver(
        CollectorSettings(),
        FakeUrlReceiver("https://disk.yandex.ru/d/x", title=yandex_disk_title),
    )
    title = (
        "\u041f\u0430\u0446\u0430\u043d\u044b (2026) — 5 \u0441\u0435\u0437\u043e\u043d | The Boys "
        "\u0441\u043c\u043e\u0442\u0440\u0435\u0442\u044c \u043f\u043b\u0435\u0439\u043b\u0438\u0441\u0442 "
        "\u043d\u0430 RUTUBE (1585448) - Google Chrome"
    )
    assert resolver.resolve("chrome.exe", title) == "rutube.ru"


def test_github_title_is_not_confused_by_repo_name_youtube() -> None:
    resolver = DomainResolver(
        CollectorSettings(),
        FakeUrlReceiver("chrome://newtab/", title="\u041d\u043e\u0432\u0430\u044f \u0432\u043a\u043b\u0430\u0434\u043a\u0430"),
    )
    title = "GitHub - Flowseal/zapret-discord-youtube - GitHub - Google Chrome"
    assert resolver.resolve("chrome.exe", title) == "github.com"


def test_yandex_disk_title_wins_when_extension_already_switched() -> None:
    resolver = DomainResolver(
        CollectorSettings(),
        FakeUrlReceiver("https://web.telegram.org/k/#@proofzzz", title="Telegram Web"),
    )
    title = (
        "\u041f\u0440\u0435\u0434\u0434\u0438\u043f\u043b\u043e\u043c\u043d\u0430\u044f "
        "\u043f\u0440\u0430\u043a\u0442\u0438\u043a\u0430 — \u042f\u043d\u0434\u0435\u043a\u0441\u00a0\u0414\u0438\u0441\u043a "
        "- Google Chrome"
    )
    assert resolver.resolve("chrome.exe", title) == "disk.yandex.ru"


def test_matching_chatgpt_extension_title_handles_generic_page_title() -> None:
    title = "\u041f\u0440\u0438\u0432\u0435\u0442\u0441\u0442\u0432\u0438\u0435 \u0438 \u043f\u043e\u043c\u043e\u0449\u044c"
    resolver = DomainResolver(
        CollectorSettings(),
        FakeUrlReceiver("https://chatgpt.com/c/123", title=title),
    )
    assert resolver.resolve("chrome.exe", f"{title} - Google Chrome") == "chatgpt.com"


def test_literal_domain_in_title_is_used_for_okko() -> None:
    resolver = DomainResolver(
        CollectorSettings(),
        FakeUrlReceiver("https://okko.tv/", title="Online cinema"),
    )
    assert resolver.resolve("chrome.exe", "okko.tv - Google Chrome") == "okko.tv"


def test_literal_domain_in_permission_title_is_used_for_dns() -> None:
    resolver = DomainResolver(
        CollectorSettings(),
        FakeUrlReceiver("https://www.dns-shop.ru/", title="DNS shop"),
    )
    assert resolver.resolve("chrome.exe", "www.dns-shop.ru asks permission") == "dns-shop.ru"


def test_recent_state_prevents_next_tab_url_from_overwriting_previous_interval() -> None:
    receiver = (
        FakeUrlReceiver("https://web.telegram.org/k/#@proofzzz", "Telegram Web")
        .add_state("https://web.telegram.org/k/#@proofzzz", "Telegram Web")
        .add_state("https://music.yandex.ru/", "\u042f\u043d\u0434\u0435\u043a\u0441 \u041c\u0443\u0437\u044b\u043a\u0430")
    )
    resolver = DomainResolver(CollectorSettings(), receiver)
    assert resolver.resolve("chrome.exe", "Telegram Web - Google Chrome") == "web.telegram.org"


def test_recent_state_matches_literal_domain_after_title_changes() -> None:
    receiver = (
        FakeUrlReceiver("https://okko.tv/", "okko.tv")
        .add_state("https://okko.tv/", "okko.tv")
        .add_state("https://okko.tv/", "Online cinema Okko")
    )
    resolver = DomainResolver(CollectorSettings(), receiver)
    assert resolver.resolve("chrome.exe", "okko.tv - Google Chrome") == "okko.tv"


def main() -> None:
    test_title_domain_wins_over_conflicting_fresh_url()
    test_fresh_url_is_used_when_title_has_no_domain_hint()
    test_subdomain_does_not_conflict_with_title_domain()
    test_mismatched_extension_title_blocks_fresh_url_without_title_hint()
    test_generic_google_url_without_extension_title_is_not_trusted()
    test_matching_extension_title_allows_old_url()
    test_google_chrome_suffix_does_not_become_google_domain()
    test_rutube_title_wins_when_extension_already_switched()
    test_github_title_is_not_confused_by_repo_name_youtube()
    test_yandex_disk_title_wins_when_extension_already_switched()
    test_matching_chatgpt_extension_title_handles_generic_page_title()
    test_literal_domain_in_title_is_used_for_okko()
    test_literal_domain_in_permission_title_is_used_for_dns()
    test_recent_state_prevents_next_tab_url_from_overwriting_previous_interval()
    test_recent_state_matches_literal_domain_after_title_changes()
    print("DomainResolver tests passed")


if __name__ == "__main__":
    main()
