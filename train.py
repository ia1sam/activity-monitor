# import pandas as pd
# from sklearn.model_selection import train_test_split
# from sklearn.ensemble import RandomForestClassifier
# from sklearn.metrics import classification_report
# import joblib
# from datetime import datetime
#
# from features import build_features, get_feature_columns
#
# print("Загружаем данные...")
# df = pd.read_csv("activity_dataset101.csv")
#
# print(f"Записей: {len(df)}")
# print("\nРаспределение классов:")
# print(df['label'].value_counts())
#
# # Применяем feature engineering
# df = build_features(df)
#
# features = get_feature_columns()
# X = df[features]
# y = df['label']
#
# X_train, X_test, y_train, y_test = train_test_split(
#     X, y, test_size=0.25, random_state=42, stratify=y
# )
#
# print("\nОбучаем модель...")
# model = RandomForestClassifier(
#     n_estimators=500,
#     max_depth=14,
#     min_samples_leaf=2,
#     class_weight='balanced',
#     random_state=42
# )
#
# model.fit(X_train, y_train)
# pred = model.predict(X_test)
#
# print("\n=== РЕЗУЛЬТАТ ОБУЧЕНИЯ ===")
# print(classification_report(y_test, pred, zero_division=0))
#
# # ====================== СОХРАНЕНИЕ ======================
# model_package = {
#     "model": model,
#     "feature_names": features,           # Очень важно!
#     "version": "1.1",
#     "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
#     "n_features": len(features)
# }
#
# joblib.dump(model_package, 'activity_modelSTEP2.pkl')
#
# print("\nМодель успешно сохранена!")
# print(f"Файл: activity_model.pkl (версия {model_package['version']})")
# print(f"Признаков использовано: {model_package['n_features']}")

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib
from datetime import datetime

from features import build_features, get_feature_columns

print("Загружаем данные...")
df = pd.read_csv("activity_dataset101.csv")

print(f"Записей: {len(df)}")
print("\nРаспределение классов:")
print(df['label'].value_counts())

# Применяем feature engineering
df = build_features(df)

features = get_feature_columns()
X = df[features]
y = df['label']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)

print("\nОбучаем улучшенную модель...")

model = RandomForestClassifier(
    n_estimators=450,           # не 800, а золотая середина
    max_depth=13,
    min_samples_leaf=2,
    class_weight='balanced',    # обычный balanced
    random_state=42,
    n_jobs=-1
)

model.fit(X_train, y_train)
pred = model.predict(X_test)

print("\n=== РЕЗУЛЬТАТ ОБУЧЕНИЯ ===")
print(classification_report(y_test, pred, zero_division=0))

# ====================== СОХРАНЕНИЕ ======================
model_package = {
    "model": model,
    "feature_names": features,
    "version": "1.2",
    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "n_features": len(features)
}

joblib.dump(model_package, 'activity_modelSTEP5.pkl')

print("\nМодель успешно сохранена!")
print(f"Версия: {model_package['version']}")
print(f"Признаков: {model_package['n_features']}")