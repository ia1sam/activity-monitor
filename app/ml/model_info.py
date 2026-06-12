from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelInfo:
    version: str
    model_type: str
    feature_columns: list[str]
    classes: list[str]

    @classmethod
    def load(cls, path: Path) -> "ModelInfo":
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return cls(
            version=str(data["version"]),
            model_type=str(data.get("model_type", "unknown")),
            feature_columns=[str(column) for column in data["feature_columns"]],
            classes=[str(class_name) for class_name in data["classes"]],
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(
                {
                    "version": self.version,
                    "model_type": self.model_type,
                    "feature_columns": self.feature_columns,
                    "classes": self.classes,
                },
                file,
                ensure_ascii=False,
                indent=2,
            )
