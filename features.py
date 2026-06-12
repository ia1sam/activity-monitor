import pandas as pd


SYSTEM_PROCESSES = {
    "explorer.exe",
    "searchhost.exe",
    "searchapp.exe",
    "shellexperiencehost.exe",
    "lockapp.exe",
    "dwm.exe",
    "cmd.exe",
    "happ.exe",
    "winws.exe",
}

WORK_PROCESSES = {
    "pycharm64.exe",
    "code.exe",
    "winword.exe",
    "excel.exe",
    "powerpnt.exe",
    "notepad.exe",
    "notepad++.exe",
}

COMMUNICATION_PROCESSES = {
    "discord.exe",
    "telegram.exe",
}

ENTERTAINMENT_PROCESSES = {
    "steam.exe",
    "steamwebhelper.exe",
    "hoi4.exe",
    "phasmophobia.exe",
    "deadlock.exe",
    "tslgame.exe",
    "tslgame_be.exe",
    "javaw.exe",
    "paradox launcher.exe",
    "curseforge.exe",
}


def is_educational(title):
    if not isinstance(title, str) or not title:
        return False
    text = title.lower()
    keywords = [
        "tutorial",
        "lesson",
        "how to",
        "course",
        "workshop",
        "coding",
        "python",
        "machine learning",
        "deep learning",
        "data science",
        "explained",
        "\u0443\u0440\u043e\u043a",
        "\u0443\u0440\u043e\u043a\u0438",
        "\u043a\u0443\u0440\u0441",
        "\u043a\u0430\u043a",
        "\u043b\u0435\u043a\u0446\u0438\u044f",
        "\u043e\u0431\u0443\u0447\u0435\u043d\u0438\u0435",
        "\u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435",
        "\u043d\u0435\u0439\u0440\u043e\u0441\u0435\u0442\u044c",
        "\u0434\u043b\u044f \u043d\u0430\u0447\u0438\u043d\u0430\u044e\u0449\u0438\u0445",
        "\u0440\u0430\u0437\u0431\u043e\u0440",
        "\u0433\u0430\u0439\u0434",
        "СѓСЂРѕРє",
        "РєСѓСЂСЃ",
        "РіР°Р№Рґ",
        "СЂР°Р·Р±РѕСЂ",
        "РѕР±СѓС‡РµРЅРёРµ",
        "РЅРµР№СЂРѕСЃРµС‚СЊ",
    ]
    return any(keyword in text for keyword in keywords)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    process_text = df["process"].fillna("").astype(str).str.lower()
    domain_text = df["domain"].fillna("").astype(str).str.lower()
    title_text = df["window_title"].fillna("").astype(str).str.lower()

    df["keyboard_per_min"] = df["keyboard_count"] / (df["duration_sec"] / 60 + 0.001)
    df["mouse_per_min"] = df["mouse_moves"] / (df["duration_sec"] / 60 + 0.001)
    df["is_browser"] = process_text.str.contains(
        "chrome|msedge|firefox|brave|opera",
        case=False,
        na=False,
        regex=True,
    ).astype(int)

    df["is_system_process"] = process_text.isin(SYSTEM_PROCESSES).astype(int)
    df["is_work_process"] = process_text.isin(WORK_PROCESSES).astype(int)
    df["is_communication_process"] = process_text.isin(COMMUNICATION_PROCESSES).astype(int)
    df["is_entertainment_process"] = process_text.isin(ENTERTAINMENT_PROCESSES).astype(int)

    df["title_length"] = title_text.str.len().fillna(0)
    df["educational_title"] = df["window_title"].apply(is_educational).astype(int)
    df["has_python"] = title_text.str.contains(
        r"python|\u043f\u0438\u0442\u043e\u043d|\u043f\u0430\u0439\u0442\u043e\u043d|РїРёС‚РѕРЅ|РїР°Р№С‚РѕРЅ",
        regex=True,
        na=False,
    ).astype(int)
    df["has_ml"] = title_text.str.contains(
        r"machine learning|deep learning|\u043d\u0435\u0439\u0440\u043e\u0441\u0435\u0442\u044c|data science|РЅРµР№СЂРѕСЃРµС‚СЊ",
        regex=True,
        na=False,
    ).astype(int)
    df["has_tutorial"] = title_text.str.contains(
        r"tutorial|\u0443\u0440\u043e\u043a|\u043a\u0443\u0440\u0441|lesson|how to|\u0433\u0430\u0439\u0434|СѓСЂРѕРє|РєСѓСЂСЃ|РіР°Р№Рґ",
        regex=True,
        na=False,
    ).astype(int)

    df["is_youtube"] = domain_text.str.contains("youtube", na=False).astype(int)
    df["youtube_educational"] = df["is_youtube"] * df["educational_title"]
    df["is_communication_domain"] = domain_text.str.contains(
        r"telegram|discord|vk\.com|mail\.ru",
        regex=True,
        na=False,
    ).astype(int)
    df["is_entertainment_domain"] = domain_text.str.contains(
        r"youtube|twitch|netflix|rutube|dzen|music\.yandex",
        regex=True,
        na=False,
    ).astype(int)
    df["is_work_domain"] = domain_text.str.contains(
        r"github|stackoverflow|habr|medium|edu\.|deepseek|chatgpt|qplus",
        regex=True,
        na=False,
    ).astype(int)
    df["title_has_work_file"] = title_text.str.contains(
        r"\.py|\.csv|\.docx|\.doc|\.xlsx|\.xls|\.pptx|\.ppt|\.pdf|\.txt|\.json|\.sql",
        regex=True,
        na=False,
    ).astype(int)

    return df


def get_feature_columns():
    return [
        "duration_sec",
        "keyboard_count",
        "mouse_moves",
        "mouse_clicks",
        "keyboard_per_min",
        "mouse_per_min",
        "hour",
        "day_of_week",
        "idle",
        "is_browser",
        "title_length",
        "educational_title",
        "has_python",
        "has_ml",
        "has_tutorial",
        "is_youtube",
        "youtube_educational",
        "is_system_process",
        "is_work_process",
        "is_communication_process",
        "is_entertainment_process",
        "is_communication_domain",
        "is_entertainment_domain",
        "is_work_domain",
        "title_has_work_file",
    ]
