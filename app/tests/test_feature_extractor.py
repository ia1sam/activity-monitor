from __future__ import annotations

from datetime import datetime

from app.ml.feature_extractor import FeatureExtractor
from app.models.activity import ActivitySnapshot
from features import get_feature_columns


def build_sample_snapshot() -> ActivitySnapshot:
    now = datetime(2026, 5, 17, 12, 0, 0)
    return ActivitySnapshot(
        start_time=now,
        end_time=now,
        duration_sec=30.0,
        process_name="chrome.exe",
        window_title="Python tutorial",
        domain="youtube.com",
        is_idle=False,
        keyboard_count=10,
        mouse_moves=40,
        mouse_clicks=3,
        hour=12,
        day_of_week=6,
    )


def test_feature_order() -> None:
    feature_frame = FeatureExtractor().build_feature_frame(build_sample_snapshot())
    expected_columns = get_feature_columns()
    actual_columns = list(feature_frame.columns)
    assert actual_columns == expected_columns, f"Feature order mismatch: {actual_columns}"


def test_label_is_not_used_as_feature() -> None:
    feature_columns = get_feature_columns()
    assert "label" not in feature_columns
    assert "predicted_category" not in feature_columns
    assert "model_version" not in feature_columns


def test_feature_frame_shape() -> None:
    feature_frame = FeatureExtractor().build_feature_frame(build_sample_snapshot())
    assert feature_frame.shape == (1, len(get_feature_columns()))


def main() -> None:
    test_feature_order()
    test_label_is_not_used_as_feature()
    test_feature_frame_shape()
    print("FeatureExtractor tests passed")


if __name__ == "__main__":
    main()
