# train_xgboost.py
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.preprocessing import LabelEncoder
import joblib
from datetime import datetime

from features import build_features, get_feature_columns

# pip install xgboost  ← сначала установи это!

import xgboost as xgb

df = pd.read_csv("activity_dataset101.csv")
df = build_features(df)

features = get_feature_columns()
X = df[features]
y = df['label']

# XGBoost требует числовые метки
le = LabelEncoder()
y_encoded = le.fit_transform(y)

X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.25, random_state=42, stratify=y_encoded)

model = xgb.XGBClassifier(
    n_estimators=400,
    max_depth=8,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    eval_metric='mlogloss'
)

model.fit(X_train, y_train)
pred = model.predict(X_test)

print("=== XGBoost ===")
print(classification_report(y_test, pred, target_names=le.classes_, zero_division=0))

joblib.dump(model, 'model_xgboost.pkl')
joblib.dump(le, 'label_encoder_xgboost.pkl')

print("XGBoost сохранён")