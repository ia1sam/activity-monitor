from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ml.feature_extractor import FeatureExtractor
from app.ml.model_info import ModelInfo
from app.models.activity import ActivitySnapshot


class ActivityClassifier:
    def __init__(
        self,
        model_path: Path,
        label_encoder_path: Path,
        feature_extractor: FeatureExtractor,
        model_version: str,
        model_info_path: Path | None = None,
    ) -> None:
        self._model_path = model_path
        self._label_encoder_path = label_encoder_path
        self._feature_extractor = feature_extractor
        self._model_version = model_version
        self._model_info_path = model_info_path
        self._model: Any | None = None
        self._label_encoder: Any | None = None
        self._load_error: str | None = None
        self._compatibility_error: str | None = None

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def load_error(self) -> str | None:
        return self._load_error

    @property
    def compatibility_error(self) -> str | None:
        return self._compatibility_error

    def is_available(self) -> bool:
        return self._ensure_loaded()

    def is_compatible(self) -> bool:
        if not self._ensure_loaded():
            return False
        return self._compatibility_error is None

    def predict(self, snapshot: ActivitySnapshot) -> str:
        if not self.is_compatible():
            raise RuntimeError(self._load_error or "Classifier is not available")

        feature_frame = self._feature_extractor.build_feature_frame(snapshot)
        raw_prediction = self._model.predict(feature_frame)[0]
        return self._decode_prediction(raw_prediction)

    def _ensure_loaded(self) -> bool:
        if self._model is not None and self._label_encoder is not None:
            return True

        try:
            import joblib

            if not self._model_path.exists():
                raise FileNotFoundError(f"Model file not found: {self._model_path}")
            if not self._label_encoder_path.exists():
                raise FileNotFoundError(f"Label encoder file not found: {self._label_encoder_path}")

            self._model = joblib.load(self._model_path)
            self._label_encoder = joblib.load(self._label_encoder_path)
            self._validate_compatibility()
            self._load_error = None
            return True
        except Exception as exc:
            self._load_error = str(exc)
            self._compatibility_error = str(exc)
            self._model = None
            self._label_encoder = None
            return False

    def _validate_compatibility(self) -> None:
        self._compatibility_error = None

        if self._model_info_path is None:
            self._compatibility_error = "Model info file is not configured"
            return
        if not self._model_info_path.exists():
            self._compatibility_error = f"Model info file not found: {self._model_info_path}"
            return

        model_info = ModelInfo.load(self._model_info_path)
        expected_features = self._feature_extractor.get_feature_columns()
        if model_info.feature_columns != expected_features:
            self._compatibility_error = (
                "Feature columns mismatch. "
                f"Application expects {expected_features}, model info contains {model_info.feature_columns}"
            )
            return

        encoder_classes = [str(class_name) for class_name in getattr(self._label_encoder, "classes_", [])]
        if model_info.classes != encoder_classes:
            self._compatibility_error = (
                "LabelEncoder classes mismatch. "
                f"Encoder contains {encoder_classes}, model info contains {model_info.classes}"
            )
            return

        if model_info.version != self._model_version:
            self._compatibility_error = (
                f"Model version mismatch. Settings use {self._model_version}, "
                f"model info contains {model_info.version}"
            )

    def _decode_prediction(self, raw_prediction: object) -> str:
        if self._label_encoder is None:
            return str(raw_prediction)
        decoded = self._label_encoder.inverse_transform([int(raw_prediction)])
        return str(decoded[0])
