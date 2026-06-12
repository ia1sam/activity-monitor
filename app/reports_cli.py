from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta
from pathlib import Path

from app.monitoring.config import CollectorSettings
from app.repositories.activity_repository import ActivityRepository
from app.repositories.sqlite_data_access import SQLiteDataAccess
from app.services.report_service import ReportService
from app.services.statistics_service import StatisticsService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Activity statistics and reports")
    parser.add_argument("--today", action="store_true", help="Show statistics for today")
    parser.add_argument("--from", dest="date_from", help="Start date in YYYY-MM-DD format")
    parser.add_argument("--to", dest="date_to", help="End date in YYYY-MM-DD format, inclusive")
    parser.add_argument("--export-csv", dest="activity_csv", help="Export full activity report to CSV")
    parser.add_argument("--export-training-csv", dest="training_csv", help="Export labeled records for retraining")
    return parser.parse_args()


def build_repository() -> ActivityRepository:
    settings = CollectorSettings()
    data_access = SQLiteDataAccess(settings.database_path)
    data_access.init()
    return ActivityRepository(data_access)


def resolve_period(args: argparse.Namespace) -> tuple[datetime, datetime]:
    if args.today or not args.date_from:
        start_date = date.today()
    else:
        start_date = date.fromisoformat(args.date_from)

    if args.date_to:
        end_date = date.fromisoformat(args.date_to) + timedelta(days=1)
    else:
        end_date = start_date + timedelta(days=1)

    return datetime.combine(start_date, time.min), datetime.combine(end_date, time.min)


def print_statistics(statistics_service: StatisticsService, start: datetime, end: datetime) -> None:
    stats = statistics_service.get_period_statistics(start, end)
    print(f"Period: {stats.start.isoformat()} - {stats.end.isoformat()}")
    print(f"Records: {stats.records_count}")
    print(f"Labeled records: {stats.labeled_count}")
    print(f"Total duration, sec: {round(stats.total_duration_sec, 2)}")
    print()
    print("Categories:")
    for row in stats.categories:
        print(f"  {row['category']}: {round(float(row['duration_sec'] or 0), 2)} sec ({row['records_count']})")
    print()
    print("Top processes:")
    for row in stats.top_processes:
        print(f"  {row['process_name']}: {round(float(row['duration_sec'] or 0), 2)} sec ({row['records_count']})")
    print()
    print("Top domains:")
    for row in stats.top_domains:
        print(f"  {row['domain']}: {round(float(row['duration_sec'] or 0), 2)} sec ({row['records_count']})")


def main() -> None:
    args = parse_args()
    repository = build_repository()
    statistics_service = StatisticsService(repository)
    report_service = ReportService(repository)
    start, end = resolve_period(args)

    print_statistics(statistics_service, start, end)

    if args.activity_csv:
        rows_count = report_service.export_activity_csv(start, end, Path(args.activity_csv))
        print(f"Activity CSV exported: {args.activity_csv} ({rows_count} rows)")

    if args.training_csv:
        rows_count = report_service.export_training_dataset_csv(Path(args.training_csv))
        print(f"Training CSV exported: {args.training_csv} ({rows_count} rows)")


if __name__ == "__main__":
    main()
