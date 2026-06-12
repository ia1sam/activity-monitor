from datetime import datetime

import joblib
import pandas as pd
import xgboost as xgb
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from app.ml.model_info import ModelInfo
from features import build_features, get_feature_columns


DATASET_PATH = "activity_dataset101.csv"
MODEL_PATH = "model_xgboost_v2.pkl"
ENCODER_PATH = "label_encoder_xgboost_v2.pkl"
MODEL_INFO_PATH = "model_info_xgboost_v2.json"
MODEL_VERSION = "xgboost_v2"


def main() -> None:
    df = pd.read_csv(DATASET_PATH)
    df = build_features(df)

    feature_columns = get_feature_columns()
    x = df[feature_columns]
    y = df["label"]

    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y_encoded,
        test_size=0.25,
        random_state=42,
        stratify=y_encoded,
    )

    model = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=8,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="mlogloss",
    )

    model.fit(x_train, y_train)
    predictions = model.predict(x_test)

    print("=== XGBoost v2 ===")
    print(f"Features: {len(feature_columns)}")
    print(f"Trained at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(classification_report(y_test, predictions, target_names=label_encoder.classes_, zero_division=0))

    joblib.dump(model, MODEL_PATH)
    joblib.dump(label_encoder, ENCODER_PATH)
    ModelInfo(
        version=MODEL_VERSION,
        model_type="XGBClassifier",
        feature_columns=feature_columns,
        classes=[str(class_name) for class_name in label_encoder.classes_],
    ).save(MODEL_INFO_PATH)
    print(f"Saved: {MODEL_PATH}")
    print(f"Saved: {ENCODER_PATH}")
    print(f"Saved: {MODEL_INFO_PATH}")


if __name__ == "__main__":
    main()
