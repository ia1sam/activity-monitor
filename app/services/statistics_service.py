from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.models.statistics import StatisticsData
from app.repositories.activity_repository import ActivityRepository


class StatisticsService:
    def __init__(self, activity_repository: ActivityRepository) -> None:
        self._activity_repository = activity_repository

    def get_daily_statistics(self, target_date: date, category: str | None = None) -> StatisticsData:
        start = datetime.combine(target_date, time.min)
        end = start + timedelta(days=1)
        return self.get_period_statistics(start, end, category)

    def get_period_statistics(self, start: datetime, end: datetime, category: str | None = None) -> StatisticsData:
        summary = self._activity_repository.get_summary(start, end, category)
        bucket = "hour" if (end - start) <= timedelta(days=2) else "day"
        return StatisticsData(
            start=start,
            end=end,
            records_count=int(summary["records_count"]),
            labeled_count=int(summary["labeled_count"]),
            total_duration_sec=float(summary["duration_sec"]),
            categories=self._activity_repository.aggregate_by_category(start, end, category),
            top_processes=self._activity_repository.aggregate_by_process(start, end, category=category),
            top_domains=self._activity_repository.aggregate_by_domain(start, end, category=category),
            timeline=self._activity_repository.aggregate_timeline(start, end, bucket, category),
        )
