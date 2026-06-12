from __future__ import annotations

import pandas as pd

from app.models.activity import ActivitySnapshot
from features import build_features, get_feature_columns


class FeatureExtractor:
    def build_feature_frame(self, snapshot: ActivitySnapshot) -> pd.DataFrame:
        source_frame = pd.DataFrame(
            [
                {
                    "duration_sec": snapshot.duration_sec,
                    "keyboard_count": snapshot.keyboard_count,
                    "mouse_moves": snapshot.mouse_moves,
                    "mouse_clicks": snapshot.mouse_clicks,
                    "hour": snapshot.hour,
                    "day_of_week": snapshot.day_of_week,
                    "idle": snapshot.is_idle,
                    "process": snapshot.process_name,
                    "window_title": snapshot.window_title,
                    "domain": snapshot.domain,
                }
            ]
        )
        feature_frame = build_features(source_frame)
        return feature_frame[get_feature_columns()]

    def get_feature_columns(self) -> list[str]:
        return get_feature_columns()
