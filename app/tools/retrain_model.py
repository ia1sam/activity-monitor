from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from app.ml.model_info import ModelInfo
from features import build_features, get_feature_columns


REQUIRED_COLUMNS = [
    "start_time",
    "end_time",
    "duration_sec",
    "process",
    "window_title",
    "domain",
    "idle",
    "keyboard_count",
    "mouse_moves",
    "mouse_clicks",
    "hour",
    "day_of_week",
    "label",
]


@dataclass(frozen=True)
class TrainingArtifacts:
    model_path: Path
    label_encoder_path: Path
    model_info_path: Path
    report_path: Path
    rows_count: int
    classes: list[str]
    accuracy: float | None
    f1_macro: float | None


def load_training_dataset(dataset_path: Path) -> pd.DataFrame:
    df = pd.read_csv(dataset_path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {missing_columns}")

    df = df[REQUIRED_COLUMNS].copy()
    df["label"] = df["label"].fillna("").astype(str).str.strip()
    df = df[df["label"] != ""]
    if df.empty:
        raise ValueError("Dataset does not contain labeled rows")

    numeric_columns = [
        "duration_sec",
        "keyboard_count",
        "mouse_moves",
        "mouse_clicks",
        "hour",
        "day_of_week",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["idle"] = df["idle"].map(_parse_bool)
    if df[numeric_columns + ["idle"]].isnull().any().any():
        raise ValueError("Dataset contains invalid numeric or idle values")

    return df


def train_model(
    dataset_path: Path,
    output_dir: Path,
    model_version: str | None = None,
    test_size: float = 0.25,
    random_state: int = 42,
) -> TrainingArtifacts:
    df = load_training_dataset(dataset_path)
    version = model_version or f"xgboost_retrained_{datetime.now():%Y%m%d_%H%M%S}"

    feature_columns = get_feature_columns()
    feature_frame = build_features(df)
    x_data = feature_frame[feature_columns]
    y_labels = df["label"]

    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y_labels)
    classes = [str(class_name) for class_name in label_encoder.classes_]
    if len(classes) < 2:
        raise ValueError("Dataset must contain at least two label classes")

    if not 0 <= test_size < 1:
        raise ValueError("test_size must be greater than or equal to 0 and less than 1")

    use_holdout = test_size > 0 and _can_stratify(y_encoded)
    if use_holdout:
        x_train, x_test, y_train, y_test = train_test_split(
            x_data,
            y_encoded,
            test_size=test_size,
            random_state=random_state,
            stratify=y_encoded,
        )
    else:
        x_train = x_data
        y_train = y_encoded
        x_test = None
        y_test = None

    model = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=8,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=random_state,
        eval_metric="mlogloss",
    )
    model.fit(x_train, y_train)

    accuracy = None
    f1_macro = None
    text_report = "Holdout metrics are not calculated because the dataset is too small for stratified split."
    if x_test is not None and y_test is not None:
        predictions = model.predict(x_test)
        accuracy = float(accuracy_score(y_test, predictions))
        f1_macro = float(f1_score(y_test, predictions, average="macro", zero_division=0))
        text_report = classification_report(
            y_test,
            predictions,
            target_names=classes,
            labels=list(range(len(classes))),
            zero_division=0,
            output_dict=False,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / f"model_{version}.pkl"
    label_encoder_path = output_dir / f"label_encoder_{version}.pkl"
    model_info_path = output_dir / f"model_info_{version}.json"
    report_path = output_dir / f"training_report_{version}.json"

    joblib.dump(model, model_path)
    joblib.dump(label_encoder, label_encoder_path)
    ModelInfo(
        version=version,
        model_type="XGBClassifier",
        feature_columns=feature_columns,
        classes=classes,
    ).save(model_info_path)
    _write_training_report(
        report_path=report_path,
        dataset_path=dataset_path,
        model_version=version,
        rows_count=len(df),
        classes=classes,
        feature_columns=feature_columns,
        accuracy=accuracy,
        f1_macro=f1_macro,
        text_report=text_report,
        test_size=test_size,
        random_state=random_state,
    )

    return TrainingArtifacts(
        model_path=model_path,
        label_encoder_path=label_encoder_path,
        model_info_path=model_info_path,
        report_path=report_path,
        rows_count=len(df),
        classes=classes,
        accuracy=accuracy,
        f1_macro=f1_macro,
    )


def _parse_bool(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if value is None:
        return 0
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "idle"}:
        return 1
    if text in {"0", "false", "no", "n", ""}:
        return 0
    raise ValueError(f"Invalid boolean value: {value}")


def _can_stratify(y_encoded) -> bool:
    counts = pd.Series(y_encoded).value_counts()
    return len(counts) > 1 and int(counts.min()) >= 2


def _write_training_report(
    report_path: Path,
    dataset_path: Path,
    model_version: str,
    rows_count: int,
    classes: list[str],
    feature_columns: list[str],
    accuracy: float | None,
    f1_macro: float | None,
    text_report: str,
    test_size: float,
    random_state: int,
) -> None:
    payload = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_path": str(dataset_path),
        "model_version": model_version,
        "model_type": "XGBClassifier",
        "rows_count": rows_count,
        "classes": classes,
        "feature_columns": feature_columns,
        "metrics": {
            "accuracy": accuracy,
            "f1_macro": f1_macro,
            "classification_report": text_report,
        },
        "params": {
            "test_size": test_size,
            "random_state": random_state,
        },
    }
    with report_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrain activity classification model from a labeled CSV dataset."
    )
    parser.add_argument("--dataset", required=True, help="Path to CSV dataset with labeled activity rows")
    parser.add_argument("--output-dir", required=True, help="Directory where model package will be saved")
    parser.add_argument("--model-version", help="Model version, for example xgboost_v3")
    parser.add_argument("--test-size", type=float, default=0.25, help="Test split size, default: 0.25")
    parser.add_argument("--random-state", type=int, default=42, help="Random state, default: 42")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifacts = train_model(
        dataset_path=Path(args.dataset),
        output_dir=Path(args.output_dir),
        model_version=args.model_version,
        test_size=args.test_size,
        random_state=args.random_state,
    )
    print("Model package saved")
    print(f"Rows: {artifacts.rows_count}")
    print(f"Classes: {', '.join(artifacts.classes)}")
    if artifacts.accuracy is None or artifacts.f1_macro is None:
        print("Accuracy: not calculated")
        print("F1 macro: not calculated")
    else:
        print(f"Accuracy: {artifacts.accuracy:.4f}")
        print(f"F1 macro: {artifacts.f1_macro:.4f}")
    print(f"Model: {artifacts.model_path}")
    print(f"LabelEncoder: {artifacts.label_encoder_path}")
    print(f"Model info: {artifacts.model_info_path}")
    print(f"Training report: {artifacts.report_path}")


if __name__ == "__main__":
    main()
