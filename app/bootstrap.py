from __future__ import annotations

from dataclasses import dataclass

from app.ml.activity_classifier import ActivityClassifier
from app.ml.feature_extractor import FeatureExtractor
from app.monitoring.activity_collector import ActivityCollector
from app.monitoring.config import CollectorSettings
from app.monitoring.domain_resolver import DomainResolver
from app.monitoring.input_tracker import InputTracker
from app.monitoring.url_receiver import BrowserUrlReceiver
from app.monitoring.window_tracker import WindowTracker
from app.repositories.activity_repository import ActivityRepository
from app.repositories.settings_repository import SettingsRepository
from app.repositories.sqlite_data_access import SQLiteDataAccess
from app.services.activity_logger import ActivityLogger
from app.services.conditional_activity_logger import ConditionalActivityLogger
from app.services.composite_activity_logger import CompositeActivityLogger
from app.services.csv_activity_logger import CsvActivityLogger
from app.services.report_service import ReportService
from app.services.session_activity_store import SessionActivityStore
from app.services.sqlite_activity_logger import SQLiteActivityLogger
from app.services.statistics_service import StatisticsService


@dataclass(frozen=True)
class AppContext:
    settings: CollectorSettings
    settings_repository: SettingsRepository
    activity_repository: ActivityRepository
    session_activity_store: SessionActivityStore
    statistics_service: StatisticsService
    report_service: ReportService
    collector: ActivityCollector


def build_activity_logger(
    settings: CollectorSettings,
    activity_repository: ActivityRepository,
    session_activity_store: SessionActivityStore,
    storage: str,
) -> ActivityLogger:
    loggers: list[ActivityLogger] = [session_activity_store]

    if storage == "csv":
        loggers.append(ConditionalActivityLogger(CsvActivityLogger(settings.output_path), lambda: settings.storage_enabled))
        return CompositeActivityLogger(loggers)

    sqlite_logger = ConditionalActivityLogger(
        SQLiteActivityLogger(activity_repository),
        lambda: settings.storage_enabled,
    )

    if storage == "both":
        loggers.extend(
            [
                sqlite_logger,
                ConditionalActivityLogger(CsvActivityLogger(settings.output_path), lambda: settings.storage_enabled),
            ]
        )
        return CompositeActivityLogger(loggers)

    loggers.append(sqlite_logger)
    return CompositeActivityLogger(loggers)


def build_app_context(storage: str = "sqlite") -> AppContext:
    settings_repository = SettingsRepository()
    settings = settings_repository.load(CollectorSettings())
    data_access = SQLiteDataAccess(settings.database_path)
    data_access.init()
    activity_repository = ActivityRepository(data_access)
    session_activity_store = SessionActivityStore()
    url_receiver = BrowserUrlReceiver(
        port=settings.url_receiver_port,
        log_path=settings.log_path,
        debug_enabled=settings.domain_debug_enabled,
    )
    classifier = ActivityClassifier(
        model_path=settings.model_path,
        label_encoder_path=settings.label_encoder_path,
        feature_extractor=FeatureExtractor(),
        model_version=settings.model_version,
        model_info_path=settings.model_info_path,
    )
    collector = ActivityCollector(
        settings=settings,
        input_tracker=InputTracker(move_threshold_px=settings.move_threshold_px),
        window_tracker=WindowTracker(settings),
        domain_resolver=DomainResolver(settings, url_receiver),
        url_receiver=url_receiver,
        activity_logger=build_activity_logger(settings, activity_repository, session_activity_store, storage),
        classifier=classifier,
    )
    return AppContext(
        settings=settings,
        settings_repository=settings_repository,
        activity_repository=activity_repository,
        session_activity_store=session_activity_store,
        statistics_service=StatisticsService(activity_repository),
        report_service=ReportService(activity_repository, settings),
        collector=collector,
    )
