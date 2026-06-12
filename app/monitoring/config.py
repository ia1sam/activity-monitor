from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
}

DEFAULT_IGNORED_PROCESSES = {
    "razer synapse service process.exe",
    "razer synapse 3.exe",
    "nahimicsvc.exe",
    "nvidia container.exe",
    "audiodg.exe",
    "csrss.exe",
    "winlogon.exe",
    "dwm.exe",
    "shellexperiencehost.exe",
    "searchapp.exe",
    "lockapp.exe",
}

DEFAULT_SYSTEM_PROCESSES = {
    "explorer.exe",
    "shellexperiencehost.exe",
    "searchapp.exe",
    "lockapp.exe",
    "dwm.exe",
}

DEFAULT_TITLE_DOMAIN_MAP = {
    "deepseek": "chat.deepseek.com",
    "chatgpt": "chatgpt.com",
    "chat gpt": "chatgpt.com",
    "openai": "chatgpt.com",
    "grok": "grok.com",
    "claude": "claude.ai",
    "gemini": "gemini.google.com",
    "perplexity": "perplexity.ai",
    "qplus": "qplus.ru",
    "youtube": "youtube.com",
    "github": "github.com",
    "stackoverflow": "stackoverflow.com",
    "telegram": "telegram.org",
    "discord": "discord.com",
    "netflix": "netflix.com",
    "twitch": "twitch.tv",
    "reddit": "reddit.com",
    "civitai": "civitai.com",
    "habr": "habr.com",
    "medium": "medium.com",
    "yandex music": "music.yandex.ru",
    "music.yandex": "music.yandex.ru",
    "\u044f\u043d\u0434\u0435\u043a\u0441 \u043c\u0443\u0437\u044b\u043a\u0430": "music.yandex.ru",
    "\u043c\u0443\u0437\u044b\u043a\u0430": "music.yandex.ru",
    "translate.yandex": "translate.yandex.ru",
    "yandex translate": "translate.yandex.ru",
    "\u044f\u043d\u0434\u0435\u043a\u0441 \u043f\u0435\u0440\u0435\u0432\u043e\u0434\u0447\u0438\u043a": "translate.yandex.ru",
    "\u043f\u0435\u0440\u0435\u0432\u043e\u0434\u0447\u0438\u043a": "translate.yandex.ru",
    "yandex": "yandex.ru",
    "mail": "mail.ru",
    "vk": "vk.com",
    "dzen": "dzen.ru",
    "rutube": "rutube.ru",
}

DEFAULT_EDUCATIONAL_KEYWORDS = {
    "tutorial",
    "lesson",
    "how to",
    "course",
    "workshop",
    "coding",
    "code",
    "python",
    "machine learning",
    "deep learning",
    "data science",
    "explained",
    "urok",
    "kurs",
    "obuchenie",
    "programmirovanie",
    "neyroset",
    "analiz",
    "praktika",
    "teoriya",
    "osnovy",
    "gaid",
    "\u0443\u0440\u043e\u043a",
    "\u0443\u0440\u043e\u043a\u0438",
    "\u043a\u0443\u0440\u0441",
    "\u043a\u0430\u043a",
    "\u043b\u0435\u043a\u0446\u0438\u044f",
    "\u043e\u0431\u0443\u0447\u0435\u043d\u0438\u0435",
    "\u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435",
    "\u043d\u0435\u0439\u0440\u043e\u0441\u0435\u0442\u044c",
    "\u0430\u043d\u0430\u043b\u0438\u0437",
    "\u043c\u0430\u0442\u0435\u043c\u0430\u0442\u0438\u043a\u0430",
    "\u0434\u043b\u044f \u043d\u0430\u0447\u0438\u043d\u0430\u044e\u0449\u0438\u0445",
    "\u0440\u0430\u0437\u0431\u043e\u0440",
    "\u043e\u0431\u044a\u044f\u0441\u043d\u0435\u043d\u0438\u0435",
    "\u043f\u0440\u0430\u043a\u0442\u0438\u043a\u0430",
    "\u0442\u0435\u043e\u0440\u0438\u044f",
    "\u043e\u0441\u043d\u043e\u0432\u044b",
    "\u0433\u0430\u0439\u0434",
}

DEFAULT_CATEGORY_DISPLAY_SETTINGS = {
    "work": {
        "display_name": "Работа",
        "color": "#2563eb",
        "description": "Работа с IDE, документами, файлами и офисными приложениями",
        "visible": True,
    },
    "communication": {
        "display_name": "Общение",
        "color": "#16a34a",
        "description": "Мессенджеры, почта, чаты и звонки",
        "visible": True,
    },
    "learning": {
        "display_name": "Обучение",
        "color": "#7c3aed",
        "description": "Учебные материалы, курсы, статьи и документация",
        "visible": True,
    },
    "entertainment": {
        "display_name": "Развлечения",
        "color": "#f97316",
        "description": "Видео, музыка, игры и развлекательные сайты",
        "visible": True,
    },
    "system": {
        "display_name": "Система",
        "color": "#64748b",
        "description": "Проводник, рабочий стол и системные окна",
        "visible": True,
    },
    "idle": {
        "display_name": "Бездействие",
        "color": "#334155",
        "description": "Периоды без активности клавиатуры и мыши",
        "visible": True,
    },
}


@dataclass
class CollectorSettings:
    output_path: Path = Path("activity_dataset_live.csv")
    database_path: Path = Path("activity_monitor.db")
    log_path: Path = Path("log.txt")
    model_path: Path = Path("model_xgboost_v2.pkl")
    label_encoder_path: Path = Path("label_encoder_xgboost_v2.pkl")
    model_info_path: Path = Path("model_info_xgboost_v2.json")
    model_version: str = "xgboost_v2"
    idle_threshold_sec: int = 60
    poll_interval_sec: float = 1.0
    min_duration_sec: float = 1.0
    browser_min_duration_sec: float = 2.0
    min_idle_duration_sec: float = 0.5
    url_receiver_port: int = 5000
    url_freshness_sec: int = 1
    domain_debug_enabled: bool = True
    classification_enabled: bool = True
    storage_enabled: bool = True
    procrastination_notifications_enabled: bool = False
    procrastination_threshold_min: int = 15
    category_display_settings: dict[str, dict[str, object]] = field(
        default_factory=lambda: {
            code: dict(settings)
            for code, settings in DEFAULT_CATEGORY_DISPLAY_SETTINGS.items()
        }
    )
    custom_training_categories: list[dict[str, str]] = field(default_factory=list)
    move_threshold_px: int = 25
    browser_processes: set[str] = field(default_factory=lambda: set(DEFAULT_BROWSER_PROCESSES))
    ignored_processes: set[str] = field(default_factory=lambda: set(DEFAULT_IGNORED_PROCESSES))
    system_processes: set[str] = field(default_factory=lambda: set(DEFAULT_SYSTEM_PROCESSES))
    title_domain_map: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_TITLE_DOMAIN_MAP))
    educational_keywords: set[str] = field(default_factory=lambda: set(DEFAULT_EDUCATIONAL_KEYWORDS))
