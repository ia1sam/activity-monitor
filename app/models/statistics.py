from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StatisticsData:
    start: datetime
    end: datetime
    records_count: int
    labeled_count: int
    total_duration_sec: float
    categories: list[dict[str, object]]
    top_processes: list[dict[str, object]]
    top_domains: list[dict[str, object]]
    timeline: list[dict[str, object]]
