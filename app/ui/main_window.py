from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

from PySide6.QtCharts import QBarCategoryAxis, QChart, QChartView, QLineSeries, QPieSeries, QValueAxis
from PySide6.QtCore import QDate, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QStyle,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.bootstrap import AppContext
from app.ml.activity_classifier import ActivityClassifier
from app.ml.feature_extractor import FeatureExtractor
from app.ml.model_info import ModelInfo
from app.monitoring.config import DEFAULT_CATEGORY_DISPLAY_SETTINGS


DEFAULT_ACTIVITY_LABELS = ["work", "communication", "learning", "entertainment", "system", "idle"]


class MainWindow(QMainWindow):
    procrastination_notification_requested = Signal(str, str)

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self._context = context
        self._selected_record_id: int | None = None
        self._activity_labels = self._load_activity_labels()
        self._ensure_category_display_settings()
        self._force_exit = False
        self._tray_minimize_message_shown = False
        self._monitoring_active = False

        self.setWindowTitle("Activity Monitor")
        self.resize(1280, 780)
        self.setMinimumSize(1050, 650)

        self._status_label = QLabel("Мониторинг остановлен")
        self._start_button = QPushButton("Запустить")
        self._stop_button = QPushButton("Остановить")
        self._stop_button.setEnabled(False)

        self._tabs = QTabWidget()

        self._activity_table = QTableWidget()
        self._activity_category_filter = QComboBox()
        self._activity_unlabeled_only = QCheckBox("Только без ручной метки")
        self._activity_limit = QComboBox()
        self._record_id_input = QLineEdit()
        self._record_id_input.setReadOnly(True)
        self._label_combo = QComboBox()
        self._save_label_button = QPushButton("Сохранить ручную метку")
        self._clear_label_button = QPushButton("Очистить ручную метку")
        self._refresh_activity_button = QPushButton("Обновить")

        self._stats_period = QComboBox()
        self._stats_category_filter = QComboBox()
        self._stats_start_date = QDateEdit()
        self._stats_end_date = QDateEdit()
        self._refresh_statistics_button = QPushButton("Показать")
        self._summary_records = QLabel("0")
        self._summary_duration = QLabel("0 мин")
        self._summary_labeled = QLabel("0")
        self._pie_chart_view = QChartView()
        self._line_chart_view = QChartView()
        self._details_table = QTableWidget()
        self._top_processes_table = QTableWidget()
        self._top_domains_table = QTableWidget()

        self._report_start_date = QDateEdit()
        self._report_end_date = QDateEdit()
        self._report_format = QComboBox()
        self._report_category_filter = QComboBox()
        self._export_report_button = QPushButton("Экспортировать отчет")
        self._export_training_button = QPushButton("Экспорт датасета для обучения CSV")
        self._settings_idle_threshold = QSpinBox()
        self._settings_browser_min_duration = QDoubleSpinBox()
        self._settings_poll_interval = QDoubleSpinBox()
        self._classification_enabled = QCheckBox("Классифицировать активность ML-моделью")
        self._storage_enabled = QCheckBox("Сохранять историю активности в базе данных")
        self._settings_domain_debug = QCheckBox("Вести диагностический лог доменов")
        self._procrastination_enabled = QCheckBox("Показывать уведомления о прокрастинации")
        self._procrastination_threshold = QSpinBox()
        self._settings_apply_button = QPushButton("Применить параметры сбора")
        self._model_info_label = QLabel()
        self._model_path_input = QLineEdit()
        self._encoder_path_input = QLineEdit()
        self._model_info_path_input = QLineEdit()
        self._model_version_input = QLineEdit()
        self._model_load_package_button = QPushButton("Загрузить пакет модели")
        self._model_apply_button = QPushButton("Применить служебные параметры")
        self._model_check_button = QPushButton("Проверить текущую модель")
        self._category_settings_table = QTableWidget()
        self._save_categories_button = QPushButton("Сохранить категории")
        self._reset_categories_button = QPushButton("Сбросить по умолчанию")
        self._category_info_button = QPushButton("О расширении категорий")
        self._custom_categories_table = QTableWidget()
        self._custom_category_name_input = QLineEdit()
        self._custom_category_description_input = QLineEdit()
        self._add_custom_category_button = QPushButton("Добавить категорию")
        self._delete_custom_category_button = QPushButton("Удалить категорию")

        self._build_layout()
        self._connect_signals()
        self._apply_style()
        self._on_stats_period_changed()
        self._setup_tray()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(10000)
        self._refresh_timer.timeout.connect(self._refresh_activity_if_visible)
        self._refresh_timer.start()

        self.refresh_activity()
        self.refresh_statistics()

    def start_monitoring(self) -> None:
        self._context.collector.start()
        self._monitoring_active = True
        self._status_label.setText("Мониторинг запущен")
        self._start_button.setEnabled(False)
        self._stop_button.setEnabled(True)
        self._update_tray_state()
        self._show_tray_message("Activity Monitor", "Мониторинг запущен")

    def stop_monitoring(self) -> None:
        self._context.collector.stop()
        self._monitoring_active = False
        self._status_label.setText("Мониторинг останавливается")
        self._start_button.setEnabled(True)
        self._stop_button.setEnabled(False)
        self._update_tray_state()
        self._show_tray_message("Activity Monitor", "Мониторинг остановлен")

    def refresh_activity(self) -> None:
        if self._context.settings.storage_enabled:
            rows = self._context.activity_repository.get_recent_rows(
                limit=int(self._activity_limit.currentText()),
                category=self._activity_category(),
                unlabeled_only=self._activity_unlabeled_only.isChecked(),
            )
        else:
            rows = self._context.session_activity_store.get_recent_rows(
                limit=int(self._activity_limit.currentText()),
                category=self._activity_category(),
                unlabeled_only=self._activity_unlabeled_only.isChecked(),
            )
        columns = [
            "id",
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
            "predicted_category",
            "model_version",
            "label",
            "effective_category",
        ]
        self._fill_table(self._activity_table, rows, columns)

    def refresh_statistics(self) -> None:
        if not self._context.settings.storage_enabled:
            self.statusBar().showMessage(
                "Сохранение истории отключено: статистика строится только по ранее сохраненным данным.",
                7000,
            )
        start, end = self._statistics_period()
        category = self._statistics_category()
        stats = self._context.statistics_service.get_period_statistics(start, end, category)
        details = self._context.activity_repository.export_rows_by_period(start, end, category)

        self._summary_records.setText(str(stats.records_count))
        self._summary_duration.setText(self._format_duration(stats.total_duration_sec))
        self._summary_labeled.setText(str(stats.labeled_count))

        self._update_pie_chart(stats.categories)
        self._update_line_chart(stats.timeline)
        self._fill_table(self._details_table, details, ["start_time", "end_time", "process", "domain", "effective_category", "duration_sec"])
        self._fill_table(self._top_processes_table, stats.top_processes, ["process_name", "duration_sec", "records_count"])
        self._fill_table(self._top_domains_table, stats.top_domains, ["domain", "duration_sec", "records_count"])

    def save_label(self) -> None:
        record_id = self._get_selected_record_id()
        if record_id is None:
            return
        self._context.activity_repository.update_label(record_id, self._label_combo.currentText())
        self.refresh_activity()
        self.refresh_statistics()

    def clear_label(self) -> None:
        record_id = self._get_selected_record_id()
        if record_id is None:
            return
        self._context.activity_repository.update_label(record_id, None)
        self.refresh_activity()
        self.refresh_statistics()

    def export_report(self) -> None:
        if not self._context.settings.storage_enabled:
            QMessageBox.information(
                self,
                "Отчет",
                "Сохранение истории отключено. Отчет будет построен только по ранее сохраненным данным.",
            )
        start, end = self._selected_report_period()
        category = self._selected_report_category()
        summary = self._context.activity_repository.get_summary(start, end, category)
        if int(summary["records_count"]) == 0:
            QMessageBox.information(self, "Отчет", "За выбранный период нет данных для экспорта.")
            return

        report_format = self._report_format.currentText().lower()
        default_name = f"activity_report.{report_format}"
        file_filter = {
            "pdf": "PDF files (*.pdf)",
            "csv": "CSV files (*.csv)",
            "json": "JSON files (*.json)",
        }[report_format]
        output_path = self._select_save_path("Экспорт отчета", default_name, file_filter)
        if output_path is None:
            return

        if report_format == "pdf":
            rows_count = self._context.report_service.export_statistics_pdf(start, end, output_path, category)
        elif report_format == "json":
            rows_count = self._context.report_service.export_activity_json(start, end, output_path, category)
        else:
            rows_count = self._context.report_service.export_activity_csv(start, end, output_path, category)

        QMessageBox.information(self, "Экспорт завершен", f"Выгружено записей: {rows_count}")

    def export_training(self) -> None:
        output_path = self._select_save_path("Экспорт датасета для обучения", "training_dataset.csv", "CSV files (*.csv)")
        if output_path is None:
            return
        rows_count = self._context.report_service.export_training_dataset_csv(output_path)
        QMessageBox.information(self, "Экспорт завершен", f"Выгружено строк: {rows_count}")

    def on_activity_row_selected(self) -> None:
        row = self._activity_table.currentRow()
        if row < 0:
            return
        id_item = self._activity_table.item(row, 0)
        label_item = self._activity_table.item(row, 13)
        if id_item is None:
            return
        try:
            self._selected_record_id = int(id_item.text())
            self._record_id_input.setText(str(self._selected_record_id))
        except ValueError:
            self._selected_record_id = None
            self._record_id_input.setText(id_item.text())
        label = label_item.data(Qt.ItemDataRole.UserRole) if label_item is not None else ""
        label = str(label or "")
        if label in self._label_choices():
            self._label_combo.setCurrentText(label)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._force_exit or not QSystemTrayIcon.isSystemTrayAvailable():
            if self._context.collector.is_running:
                self._context.collector.stop()
            if hasattr(self, "_tray_icon"):
                self._tray_icon.hide()
            super().closeEvent(event)
            return

        event.ignore()
        self.hide()
        if not self._tray_minimize_message_shown:
            self._show_tray_message("Activity Monitor", "Приложение продолжает работу в системном трее")
            self._tray_minimize_message_shown = True

    def _build_layout(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        root_layout.addWidget(self._build_header())
        self._tabs.addTab(self._build_activity_tab(), "Активность")
        self._tabs.addTab(self._build_statistics_tab(), "Статистика")
        self._tabs.addTab(self._build_reports_tab(), "Отчеты")
        self._tabs.addTab(self._build_settings_tab(), "Настройки")
        root_layout.addWidget(self._tabs)
        self.setCentralWidget(root)

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("panel")
        layout = QHBoxLayout(header)
        title = QLabel("Мониторинг пользовательской активности")
        title.setObjectName("title")
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self._status_label)
        layout.addWidget(self._start_button)
        layout.addWidget(self._stop_button)
        return header

    def _build_activity_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        filters = QHBoxLayout()
        self._populate_category_combo(self._activity_category_filter, include_hidden=True)
        self._activity_limit.addItems(["50", "100", "250", "500"])
        self._activity_limit.setCurrentText("50")
        filters.addWidget(QLabel("Категория:"))
        filters.addWidget(self._activity_category_filter)
        filters.addWidget(self._activity_unlabeled_only)
        filters.addWidget(QLabel("Записей:"))
        filters.addWidget(self._activity_limit)
        filters.addStretch()
        filters.addWidget(self._refresh_activity_button)
        layout.addLayout(filters)

        self._setup_table(self._activity_table)
        layout.addWidget(self._activity_table)

        editor = QFrame()
        editor.setObjectName("panel")
        editor_layout = QHBoxLayout(editor)
        self._label_combo.addItems(self._label_choices())
        self._record_id_input.setMaximumWidth(90)
        editor_layout.addWidget(QLabel("Выбранная запись:"))
        editor_layout.addWidget(self._record_id_input)
        editor_layout.addWidget(QLabel("Ручная метка для обучения:"))
        editor_layout.addWidget(self._label_combo)
        editor_layout.addWidget(self._save_label_button)
        editor_layout.addWidget(self._clear_label_button)
        editor_layout.addStretch()
        layout.addWidget(editor)
        return tab

    def _build_statistics_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        controls = QHBoxLayout()
        self._stats_period.addItems(["День", "Неделя", "Месяц", "Интервал"])
        self._populate_category_combo(self._stats_category_filter)
        today = QDate.currentDate()
        self._stats_start_date.setCalendarPopup(True)
        self._stats_end_date.setCalendarPopup(True)
        self._stats_start_date.setDate(today)
        self._stats_end_date.setDate(today)
        controls.addWidget(QLabel("Период:"))
        controls.addWidget(self._stats_period)
        controls.addWidget(QLabel("с"))
        controls.addWidget(self._stats_start_date)
        controls.addWidget(QLabel("по"))
        controls.addWidget(self._stats_end_date)
        controls.addWidget(QLabel("Категория:"))
        controls.addWidget(self._stats_category_filter)
        controls.addStretch()
        controls.addWidget(self._refresh_statistics_button)
        layout.addLayout(controls)

        summary = QHBoxLayout()
        summary.addWidget(self._summary_card("Записей", self._summary_records))
        summary.addWidget(self._summary_card("Общее время", self._summary_duration))
        summary.addWidget(self._summary_card("Размечено вручную", self._summary_labeled))
        layout.addLayout(summary)

        charts = QSplitter(Qt.Orientation.Horizontal)
        self._pie_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._line_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        charts.addWidget(self._pie_chart_view)
        charts.addWidget(self._line_chart_view)
        charts.setSizes([520, 680])
        layout.addWidget(charts, 2)

        tables = QSplitter(Qt.Orientation.Horizontal)
        self._setup_table(self._details_table)
        self._setup_table(self._top_processes_table)
        self._setup_table(self._top_domains_table)
        tables.addWidget(self._table_panel("Детализация", self._details_table))
        tables.addWidget(self._table_panel("Топ процессов", self._top_processes_table))
        tables.addWidget(self._table_panel("Топ доменов", self._top_domains_table))
        tables.setSizes([650, 300, 300])
        layout.addWidget(tables, 2)
        return tab

    def _build_reports_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        today = QDate.currentDate()
        self._report_start_date.setCalendarPopup(True)
        self._report_end_date.setCalendarPopup(True)
        self._report_start_date.setDate(today)
        self._report_end_date.setDate(today)
        self._report_format.addItems(["PDF", "CSV", "JSON"])
        self._populate_category_combo(self._report_category_filter)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Период отчета: с"))
        date_row.addWidget(self._report_start_date)
        date_row.addWidget(QLabel("по"))
        date_row.addWidget(self._report_end_date)
        date_row.addWidget(QLabel("Категория:"))
        date_row.addWidget(self._report_category_filter)
        date_row.addWidget(QLabel("Формат:"))
        date_row.addWidget(self._report_format)
        date_row.addStretch()
        panel_layout.addLayout(date_row)
        panel_layout.addWidget(self._export_report_button)
        panel_layout.addWidget(self._export_training_button)
        layout.addWidget(panel)
        layout.addStretch()
        return tab

    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        settings_tabs = QTabWidget()

        collection_panel = QFrame()
        collection_panel.setObjectName("panel")
        collection_layout = QFormLayout(collection_panel)
        collection_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        collection_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._settings_idle_threshold.setRange(10, 3600)
        self._settings_idle_threshold.setValue(self._context.settings.idle_threshold_sec)
        self._settings_browser_min_duration.setRange(0.5, 30.0)
        self._settings_browser_min_duration.setDecimals(1)
        self._settings_browser_min_duration.setSingleStep(0.5)
        self._settings_browser_min_duration.setValue(self._context.settings.browser_min_duration_sec)
        self._settings_poll_interval.setRange(0.5, 10.0)
        self._settings_poll_interval.setDecimals(1)
        self._settings_poll_interval.setSingleStep(0.5)
        self._settings_poll_interval.setValue(self._context.settings.poll_interval_sec)
        self._classification_enabled.setChecked(self._context.settings.classification_enabled)
        self._storage_enabled.setChecked(self._context.settings.storage_enabled)
        self._settings_domain_debug.setChecked(self._context.settings.domain_debug_enabled)
        self._procrastination_enabled.setChecked(self._context.settings.procrastination_notifications_enabled)
        self._procrastination_threshold.setRange(1, 240)
        self._procrastination_threshold.setValue(self._context.settings.procrastination_threshold_min)
        collection_layout.addRow("Порог бездействия, сек:", self._settings_idle_threshold)
        collection_layout.addRow("Мин. длительность browser-записи, сек:", self._settings_browser_min_duration)
        collection_layout.addRow("Интервал опроса активного окна, сек:", self._settings_poll_interval)
        collection_layout.addRow("", self._classification_enabled)
        collection_layout.addRow("", self._storage_enabled)
        collection_layout.addRow("", self._settings_domain_debug)
        collection_layout.addRow("", self._procrastination_enabled)
        collection_layout.addRow("Порог уведомления, мин:", self._procrastination_threshold)
        collection_layout.addRow("", self._settings_apply_button)

        collection_page = QWidget()
        collection_page_layout = QVBoxLayout(collection_page)
        collection_page_layout.setSpacing(12)
        collection_page_layout.addWidget(collection_panel)
        collection_page_layout.addStretch()

        model_panel = QFrame()
        model_panel.setObjectName("panel")
        model_layout = QVBoxLayout(model_panel)
        model_form = QFormLayout()
        model_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        model_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._model_info_label.setWordWrap(True)
        for input_widget in (
            self._model_path_input,
            self._encoder_path_input,
            self._model_info_path_input,
            self._model_version_input,
        ):
            input_widget.setMinimumWidth(420)
        self._model_path_input.setText(str(self._context.settings.model_path))
        self._encoder_path_input.setText(str(self._context.settings.label_encoder_path))
        self._model_info_path_input.setText(str(self._context.settings.model_info_path))
        self._model_version_input.setText(self._context.settings.model_version)
        self._update_model_info_text()
        model_note = QLabel(
            "Новая модель загружается как пакет: папка должна содержать обученную модель, "
            "LabelEncoder и model_info. Для переобучения экспортируйте размеченный датасет "
            "во вкладке «Отчеты» и используйте отдельную утилиту: "
            "python -m app.tools.retrain_model --dataset training_dataset.csv --output-dir models/new_model"
        )
        model_note.setWordWrap(True)
        model_form.addRow("Файл модели:", self._model_path_input)
        model_form.addRow("Файл LabelEncoder:", self._encoder_path_input)
        model_form.addRow("Файл model_info:", self._model_info_path_input)
        model_form.addRow("Версия модели:", self._model_version_input)
        model_layout.addWidget(self._model_info_label)
        model_layout.addWidget(model_note)
        model_actions = QHBoxLayout()
        model_actions.addWidget(self._model_check_button)
        model_actions.addWidget(self._model_load_package_button)
        model_actions.addStretch()
        model_layout.addLayout(model_actions)
        service_label = QLabel("Служебные параметры")
        service_label.setObjectName("sectionTitle")
        model_layout.addWidget(service_label)
        model_layout.addLayout(model_form)
        model_layout.addWidget(self._model_apply_button)

        model_page = QWidget()
        model_page_layout = QVBoxLayout(model_page)
        model_page_layout.setSpacing(12)
        model_page_layout.addWidget(model_panel)
        model_page_layout.addStretch()

        categories_panel = QFrame()
        categories_panel.setObjectName("panel")
        categories_layout = QVBoxLayout(categories_panel)
        note = QLabel(
            "Категории являются фиксированными классами ML-модели. "
            "Добавление или удаление категории требует переобучения модели; "
            "в интерфейсе сейчас можно использовать их как фильтры и ручные метки."
        )
        note.setWordWrap(True)
        categories_layout.addWidget(note)
        self._setup_table(self._category_settings_table)
        self._category_settings_table.setMinimumHeight(230)
        self._fill_category_settings_table()
        categories_layout.addWidget(self._category_settings_table)
        category_buttons = QHBoxLayout()
        category_buttons.addWidget(self._save_categories_button)
        category_buttons.addWidget(self._reset_categories_button)
        category_buttons.addWidget(self._category_info_button)
        category_buttons.addStretch()
        categories_layout.addLayout(category_buttons)

        custom_categories_panel = QFrame()
        custom_categories_panel.setObjectName("panel")
        custom_categories_layout = QVBoxLayout(custom_categories_panel)
        custom_note = QLabel(
            "Пользовательские категории используются только для ручной разметки записей "
            "и попадут в обучающий датасет при экспорте. Текущая модель не будет "
            "предсказывать такие категории до переобучения."
        )
        custom_note.setWordWrap(True)
        custom_categories_layout.addWidget(custom_note)
        self._setup_table(self._custom_categories_table)
        self._custom_categories_table.setMinimumHeight(180)
        self._fill_custom_categories_table()
        custom_categories_layout.addWidget(self._custom_categories_table)
        custom_form = QFormLayout()
        custom_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        custom_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._custom_category_name_input.setMinimumWidth(320)
        self._custom_category_description_input.setMinimumWidth(420)
        self._custom_category_name_input.setPlaceholderText("например: games")
        self._custom_category_description_input.setPlaceholderText("например: Игровая активность")
        custom_form.addRow("Название:", self._custom_category_name_input)
        custom_form.addRow("Описание:", self._custom_category_description_input)
        custom_categories_layout.addLayout(custom_form)
        custom_buttons = QHBoxLayout()
        custom_buttons.addWidget(self._add_custom_category_button)
        custom_buttons.addWidget(self._delete_custom_category_button)
        custom_buttons.addStretch()
        custom_categories_layout.addLayout(custom_buttons)

        categories_page = QWidget()
        categories_page_layout = QVBoxLayout(categories_page)
        categories_page_layout.setSpacing(12)
        categories_page_layout.addWidget(categories_panel)
        categories_page_layout.addWidget(custom_categories_panel)
        categories_page_layout.addStretch()

        settings_tabs.addTab(self._wrap_settings_page(collection_page), "Сбор и уведомления")
        settings_tabs.addTab(self._wrap_settings_page(categories_page), "Категории")
        settings_tabs.addTab(self._wrap_settings_page(model_page), "ML-модель")
        layout.addWidget(settings_tabs)
        return tab

    def _wrap_settings_page(self, content: QWidget) -> QScrollArea:
        scroll_area = QScrollArea()
        scroll_area.setWidget(content)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        return scroll_area

    def _connect_signals(self) -> None:
        self._start_button.clicked.connect(self.start_monitoring)
        self._stop_button.clicked.connect(self.stop_monitoring)
        self._refresh_activity_button.clicked.connect(self.refresh_activity)
        self._activity_category_filter.currentIndexChanged.connect(lambda *_: self.refresh_activity())
        self._activity_unlabeled_only.stateChanged.connect(lambda *_: self.refresh_activity())
        self._activity_limit.currentIndexChanged.connect(lambda *_: self.refresh_activity())
        self._refresh_statistics_button.clicked.connect(self.refresh_statistics)
        self._stats_period.currentIndexChanged.connect(lambda *_: self._on_stats_period_changed())
        self._save_label_button.clicked.connect(self.save_label)
        self._clear_label_button.clicked.connect(self.clear_label)
        self._export_report_button.clicked.connect(self.export_report)
        self._export_training_button.clicked.connect(self.export_training)
        self._settings_apply_button.clicked.connect(self.apply_collection_settings)
        self._model_load_package_button.clicked.connect(self.load_model_package)
        self._model_apply_button.clicked.connect(self.apply_model_settings)
        self._model_check_button.clicked.connect(self.check_model)
        self._save_categories_button.clicked.connect(self.save_category_settings)
        self._reset_categories_button.clicked.connect(self.reset_category_settings)
        self._category_info_button.clicked.connect(self.show_category_expansion_info)
        self._add_custom_category_button.clicked.connect(self.add_custom_training_category)
        self._delete_custom_category_button.clicked.connect(self.delete_custom_training_category)
        self._activity_table.itemSelectionChanged.connect(self.on_activity_row_selected)

    def _refresh_activity_if_visible(self) -> None:
        if self._tabs.currentWidget() is not None and self._tabs.currentIndex() == 0:
            self.refresh_activity()

    def _populate_category_combo(self, combo: QComboBox, include_hidden: bool = False) -> None:
        combo.clear()
        for label, value, description in self._category_filters(include_hidden):
            combo.addItem(label, value)
            combo.setItemData(combo.count() - 1, description, Qt.ItemDataRole.ToolTipRole)

    def _category_filters(self, include_hidden: bool = False) -> list[tuple[str, str, str]]:
        filters = [("Все категории", "all", "Показать все категории")]
        for code in self._activity_labels:
            if include_hidden or self._category_visible(code):
                filters.append((self._category_display_name(code), code, self._category_description(code)))
        for category in self._custom_training_categories():
            filters.append((category["name"], category["name"], category["description"]))
        return filters

    def _load_activity_labels(self) -> list[str]:
        try:
            return ModelInfo.load(self._context.settings.model_info_path).classes
        except Exception:
            return list(DEFAULT_ACTIVITY_LABELS)

    def _ensure_category_display_settings(self) -> None:
        settings = self._context.settings.category_display_settings
        for code in self._activity_labels:
            if code in settings:
                continue
            default = DEFAULT_CATEGORY_DISPLAY_SETTINGS.get(
                code,
                {
                    "display_name": code,
                    "color": "#64748b",
                    "description": "Категория активности",
                    "visible": True,
                },
            )
            settings[code] = dict(default)

    def _reload_category_controls(self) -> None:
        self._activity_labels = self._load_activity_labels()
        self._ensure_category_display_settings()
        widgets = [self._activity_category_filter, self._stats_category_filter, self._report_category_filter, self._label_combo]
        previous_values = [widget.currentData() if widget is not self._label_combo else widget.currentText() for widget in widgets]
        for widget in widgets:
            widget.blockSignals(True)

        self._populate_category_combo(self._activity_category_filter, include_hidden=True)
        self._populate_category_combo(self._stats_category_filter)
        self._populate_category_combo(self._report_category_filter)
        self._label_combo.clear()
        self._label_combo.addItems(self._label_choices())

        for widget, previous_value in zip(widgets, previous_values, strict=False):
            index = widget.findText(str(previous_value)) if widget is self._label_combo else widget.findData(previous_value)
            if index >= 0:
                widget.setCurrentIndex(index)
            widget.blockSignals(False)

        self._fill_category_settings_table()
        self._fill_custom_categories_table()

    def _label_choices(self) -> list[str]:
        choices = list(self._activity_labels)
        for category in self._custom_training_categories():
            name = category["name"]
            if name not in choices:
                choices.append(name)
        return choices

    def _custom_training_categories(self) -> list[dict[str, str]]:
        normalized = []
        seen: set[str] = set()
        for item in self._context.settings.custom_training_categories:
            name = str(item.get("name", "")).strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            normalized.append(
                {
                    "name": name,
                    "description": str(item.get("description", "")).strip(),
                }
            )
        self._context.settings.custom_training_categories = normalized
        return normalized

    def _category_display_name(self, code: str) -> str:
        category = self._context.settings.category_display_settings.get(code, {})
        return str(category.get("display_name") or code)

    def _category_description(self, code: str) -> str:
        category = self._context.settings.category_display_settings.get(code, {})
        if not category:
            for custom_category in self._custom_training_categories():
                if custom_category["name"] == code:
                    return custom_category["description"]
        return str(category.get("description") or "")

    def _category_color(self, code: str) -> str:
        category = self._context.settings.category_display_settings.get(code, {})
        return str(category.get("color") or "#64748b")

    def _category_visible(self, code: str) -> bool:
        category = self._context.settings.category_display_settings.get(code, {})
        return bool(category.get("visible", True))

    def _display_category_value(self, value: object) -> str:
        if value is None:
            return ""
        code = str(value)
        if not code:
            return ""
        if code in self._context.settings.category_display_settings:
            return self._category_display_name(code)
        return code

    def _activity_category(self) -> str | None:
        return self._activity_category_filter.currentData()

    def _statistics_category(self) -> str | None:
        return self._stats_category_filter.currentData()

    def _selected_report_category(self) -> str | None:
        return self._report_category_filter.currentData()

    def _statistics_period(self) -> tuple[datetime, datetime]:
        today = date.today()
        selected = self._stats_period.currentText()
        if selected == "День":
            start_date = today
            end_date = today
        elif selected == "Неделя":
            start_date = today - timedelta(days=6)
            end_date = today
        elif selected == "Месяц":
            start_date = today.replace(day=1)
            end_date = today
        else:
            start_date = self._stats_start_date.date().toPython()
            end_date = self._stats_end_date.date().toPython()
        return datetime.combine(start_date, time.min), datetime.combine(end_date + timedelta(days=1), time.min)

    def _on_stats_period_changed(self) -> None:
        custom = self._stats_period.currentText() == "Интервал"
        self._stats_start_date.setEnabled(custom)
        self._stats_end_date.setEnabled(custom)

    def _selected_report_period(self) -> tuple[datetime, datetime]:
        start_date = self._report_start_date.date().toPython()
        end_date = self._report_end_date.date().toPython()
        return datetime.combine(start_date, time.min), datetime.combine(end_date + timedelta(days=1), time.min)

    def _update_pie_chart(self, categories: list[dict[str, object]]) -> None:
        series = QPieSeries()
        for row in categories:
            category_code = str(row.get("category", "unknown"))
            if not self._category_visible(category_code):
                continue
            duration = float(row.get("duration_sec") or 0)
            if duration <= 0:
                continue
            slice_item = series.append(self._category_display_name(category_code), duration / 60)
            slice_item.setBrush(QColor(self._category_color(category_code)))
        for slice_item in series.slices():
            slice_item.setLabelVisible(False)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Распределение времени по категориям")
        chart.setTitleFont(QFont("Segoe UI", 10))
        chart.legend().setFont(QFont("Segoe UI", 8))
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)
        self._pie_chart_view.setChart(chart)

    def _update_line_chart(self, timeline: list[dict[str, object]]) -> None:
        series = QLineSeries()
        series.setPointsVisible(True)
        max_value = 0.0
        labels = []
        for index, row in enumerate(timeline):
            minutes = float(row.get("duration_sec") or 0) / 60
            max_value = max(max_value, minutes)
            series.append(index, minutes)
            labels.append(self._format_period_label(row.get("period", index)))

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Динамика активности")
        chart.setTitleFont(QFont("Segoe UI", 10))
        chart.legend().hide()
        axis_x = QBarCategoryAxis()
        axis_x.append(labels or [""])
        axis_x.setTitleText("Период")
        axis_x.setLabelsAngle(-45)
        axis_y = QValueAxis()
        axis_y.setTitleText("Минуты")
        axis_y.setRange(0, max(max_value * 1.2, 1))
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        self._line_chart_view.setChart(chart)

    def _summary_card(self, title: str, value_label: QLabel) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        title_label = QLabel(title)
        title_label.setObjectName("muted")
        value_label.setObjectName("metric")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card

    def _table_panel(self, title: str, table: QTableWidget) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        layout.addWidget(label)
        layout.addWidget(table)
        return panel

    def _setup_table(self, table: QTableWidget) -> None:
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setSortingEnabled(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _fill_table(self, table: QTableWidget, rows: list[dict[str, object]], columns: list[str]) -> None:
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            table.setSortingEnabled(False)
            table.setColumnCount(len(columns))
            table.setHorizontalHeaderLabels(columns)
            table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for column_index, column in enumerate(columns):
                    value = row.get(column)
                    if column == "duration_sec":
                        text = str(round(float(value or 0), 2))
                    elif self._is_category_column(column):
                        text = self._display_category_value(value)
                    else:
                        text = "" if value is None else str(value)
                    item = QTableWidgetItem(text)
                    if self._is_category_column(column):
                        item.setData(Qt.ItemDataRole.UserRole, "" if value is None else str(value))
                        tooltip = self._category_description(str(value or ""))
                        if tooltip:
                            item.setToolTip(tooltip)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    table.setItem(row_index, column_index, item)
        finally:
            table.blockSignals(False)
            table.setUpdatesEnabled(True)

    def _is_category_column(self, column: str) -> bool:
        return column in {"category", "predicted_category", "label", "effective_category", "category_name"}

    def _fill_category_settings_table(self) -> None:
        columns = ["Код модели", "Название", "Цвет", "Описание", "Показывать"]
        self._category_settings_table.setUpdatesEnabled(False)
        self._category_settings_table.blockSignals(True)
        try:
            self._category_settings_table.setColumnCount(len(columns))
            self._category_settings_table.setHorizontalHeaderLabels(columns)
            self._category_settings_table.setRowCount(len(self._activity_labels))
            header = self._category_settings_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            header.setStretchLastSection(True)
            self._category_settings_table.setColumnWidth(0, 130)
            self._category_settings_table.setColumnWidth(1, 150)
            self._category_settings_table.setColumnWidth(2, 90)
            self._category_settings_table.setColumnWidth(3, 360)
            self._category_settings_table.setColumnWidth(4, 110)
            for row_index, code in enumerate(self._activity_labels):
                code_item = QTableWidgetItem(code)
                code_item.setFlags(code_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._category_settings_table.setItem(row_index, 0, code_item)

                name_item = QTableWidgetItem(self._category_display_name(code))
                self._category_settings_table.setItem(row_index, 1, name_item)

                color_item = QTableWidgetItem(self._category_color(code))
                color_item.setBackground(QColor(self._category_color(code)))
                self._category_settings_table.setItem(row_index, 2, color_item)

                description_item = QTableWidgetItem(self._category_description(code))
                self._category_settings_table.setItem(row_index, 3, description_item)

                visible_item = QTableWidgetItem("")
                visible_item.setFlags((visible_item.flags() | Qt.ItemFlag.ItemIsUserCheckable) & ~Qt.ItemFlag.ItemIsEditable)
                visible_item.setCheckState(Qt.CheckState.Checked if self._category_visible(code) else Qt.CheckState.Unchecked)
                self._category_settings_table.setItem(row_index, 4, visible_item)
        finally:
            self._category_settings_table.blockSignals(False)
            self._category_settings_table.setUpdatesEnabled(True)

    def _fill_custom_categories_table(self) -> None:
        columns = ["Название", "Описание", "Использовано в label"]
        categories = self._custom_training_categories()
        self._custom_categories_table.setUpdatesEnabled(False)
        self._custom_categories_table.blockSignals(True)
        try:
            self._custom_categories_table.setColumnCount(len(columns))
            self._custom_categories_table.setHorizontalHeaderLabels(columns)
            self._custom_categories_table.setRowCount(len(categories))
            header = self._custom_categories_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            header.setStretchLastSection(True)
            self._custom_categories_table.setColumnWidth(0, 160)
            self._custom_categories_table.setColumnWidth(1, 420)
            self._custom_categories_table.setColumnWidth(2, 150)
            for row_index, category in enumerate(categories):
                name = category["name"]
                used_count = self._context.activity_repository.count_by_label(name)

                name_item = QTableWidgetItem(name)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._custom_categories_table.setItem(row_index, 0, name_item)

                description_item = QTableWidgetItem(category["description"])
                description_item.setFlags(description_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._custom_categories_table.setItem(row_index, 1, description_item)

                used_item = QTableWidgetItem(str(used_count))
                used_item.setFlags(used_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._custom_categories_table.setItem(row_index, 2, used_item)
        finally:
            self._custom_categories_table.blockSignals(False)
            self._custom_categories_table.setUpdatesEnabled(True)

    def apply_collection_settings(self) -> None:
        self._context.settings.idle_threshold_sec = self._settings_idle_threshold.value()
        self._context.settings.browser_min_duration_sec = self._settings_browser_min_duration.value()
        self._context.settings.poll_interval_sec = self._settings_poll_interval.value()
        self._context.settings.classification_enabled = self._classification_enabled.isChecked()
        self._context.settings.storage_enabled = self._storage_enabled.isChecked()
        self._context.settings.domain_debug_enabled = self._settings_domain_debug.isChecked()
        self._context.settings.procrastination_notifications_enabled = self._procrastination_enabled.isChecked()
        self._context.settings.procrastination_threshold_min = self._procrastination_threshold.value()
        self._context.settings_repository.save(self._context.settings)
        self.refresh_activity()
        QMessageBox.information(self, "Настройки", "Параметры сбора применены и сохранены.")

    def save_category_settings(self) -> None:
        updated: dict[str, dict[str, object]] = {}
        display_names: set[str] = set()
        for row_index in range(self._category_settings_table.rowCount()):
            code_item = self._category_settings_table.item(row_index, 0)
            name_item = self._category_settings_table.item(row_index, 1)
            color_item = self._category_settings_table.item(row_index, 2)
            description_item = self._category_settings_table.item(row_index, 3)
            visible_item = self._category_settings_table.item(row_index, 4)
            if code_item is None:
                continue

            code = code_item.text().strip()
            display_name = name_item.text().strip() if name_item is not None else code
            color = color_item.text().strip() if color_item is not None else "#64748b"
            description = description_item.text().strip() if description_item is not None else ""
            visible = visible_item.checkState() == Qt.CheckState.Checked if visible_item is not None else True

            if not display_name:
                QMessageBox.warning(self, "Категории", f"Название категории '{code}' не может быть пустым.")
                return
            if display_name.lower() in display_names:
                QMessageBox.warning(self, "Категории", f"Название '{display_name}' используется повторно.")
                return
            if not self._is_valid_hex_color(color):
                QMessageBox.warning(self, "Категории", f"Цвет категории '{code}' должен быть в формате #RRGGBB.")
                return

            display_names.add(display_name.lower())
            updated[code] = {
                "display_name": display_name,
                "color": color,
                "description": description,
                "visible": visible,
            }

        self._context.settings.category_display_settings.update(updated)
        self._context.settings_repository.save(self._context.settings)
        self._reload_category_controls()
        self.refresh_activity()
        self.refresh_statistics()
        QMessageBox.information(self, "Категории", "Настройки категорий сохранены.")

    def reset_category_settings(self) -> None:
        answer = QMessageBox.question(
            self,
            "Сброс категорий",
            "Вернуть стандартные названия, цвета и описания категорий?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._context.settings.category_display_settings = {
            code: dict(DEFAULT_CATEGORY_DISPLAY_SETTINGS.get(
                code,
                {
                    "display_name": code,
                    "color": "#64748b",
                    "description": "Категория активности",
                    "visible": True,
                },
            ))
            for code in self._activity_labels
        }
        self._context.settings_repository.save(self._context.settings)
        self._reload_category_controls()
        self.refresh_activity()
        self.refresh_statistics()

    def show_category_expansion_info(self) -> None:
        QMessageBox.information(
            self,
            "Расширение категорий",
            "Набор системных категорий определяется текущей ML-моделью. "
            "Добавление новой категории требует расширения обучающего датасета, "
            "переобучения модели, обновления LabelEncoder и model_info.",
        )

    def add_custom_training_category(self) -> None:
        name = self._custom_category_name_input.text().strip()
        description = self._custom_category_description_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Пользовательские категории", "Название категории не может быть пустым.")
            return
        if len(name) > 50:
            QMessageBox.warning(self, "Пользовательские категории", "Название категории не должно быть длиннее 50 символов.")
            return
        if "," in name:
            QMessageBox.warning(self, "Пользовательские категории", "Название категории не должно содержать запятую.")
            return
        if name.lower() in {label.lower() for label in self._activity_labels}:
            QMessageBox.warning(
                self,
                "Пользовательские категории",
                "Такая категория уже является системным классом текущей ML-модели.",
            )
            return
        if name.lower() in {category["name"].lower() for category in self._custom_training_categories()}:
            QMessageBox.warning(self, "Пользовательские категории", "Такая пользовательская категория уже существует.")
            return

        answer = QMessageBox.question(
            self,
            "Добавление категории",
            "Новая категория не будет предсказываться текущей моделью. "
            "Она будет доступна только для ручной разметки и может быть учтена "
            "после переобучения модели. Добавить категорию?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._context.settings.custom_training_categories.append(
            {
                "name": name,
                "description": description,
            }
        )
        self._context.settings_repository.save(self._context.settings)
        self._custom_category_name_input.clear()
        self._custom_category_description_input.clear()
        self._reload_category_controls()
        QMessageBox.information(self, "Пользовательские категории", "Категория добавлена.")

    def delete_custom_training_category(self) -> None:
        row = self._custom_categories_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Пользовательские категории", "Сначала выберите пользовательскую категорию.")
            return
        name_item = self._custom_categories_table.item(row, 0)
        if name_item is None:
            return
        name = name_item.text().strip()
        used_count = self._context.activity_repository.count_by_label(name)

        if used_count > 0:
            message_box = QMessageBox(self)
            message_box.setWindowTitle("Удаление категории")
            message_box.setText(
                f"Категория '{name}' уже использовалась в {used_count} записях. "
                "Удалить категорию из списка доступных ручных меток?"
            )
            keep_labels_button = message_box.addButton("Удалить, метки оставить", QMessageBox.ButtonRole.AcceptRole)
            clear_labels_button = message_box.addButton("Удалить и очистить метки", QMessageBox.ButtonRole.DestructiveRole)
            cancel_button = message_box.addButton(QMessageBox.StandardButton.Cancel)
            message_box.exec()
            clicked_button = message_box.clickedButton()
            if clicked_button == cancel_button:
                return
            if clicked_button == clear_labels_button:
                self._context.activity_repository.clear_label_value(name)
            elif clicked_button != keep_labels_button:
                return
        else:
            answer = QMessageBox.question(
                self,
                "Удаление категории",
                f"Удалить пользовательскую категорию '{name}'?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self._context.settings.custom_training_categories = [
            category
            for category in self._custom_training_categories()
            if category["name"].lower() != name.lower()
        ]
        self._context.settings_repository.save(self._context.settings)
        self._reload_category_controls()
        self.refresh_activity()
        self.refresh_statistics()
        QMessageBox.information(self, "Пользовательские категории", "Категория удалена.")

    def apply_model_settings(self) -> None:
        model_path = Path(self._model_path_input.text().strip())
        encoder_path = Path(self._encoder_path_input.text().strip())
        model_info_path = Path(self._model_info_path_input.text().strip())
        model_version = self._model_version_input.text().strip() or "custom_model"
        self._apply_model_paths(model_path, encoder_path, model_info_path, model_version)

    def load_model_package(self) -> None:
        package_path = QFileDialog.getExistingDirectory(self, "Выберите папку пакета модели")
        if not package_path:
            return

        try:
            model_path, encoder_path, model_info_path = self._find_model_package_files(Path(package_path))
            model_info = ModelInfo.load(model_info_path)
        except Exception as exc:
            QMessageBox.warning(self, "Пакет модели", f"Пакет модели не загружен: {exc}")
            return

        self._model_path_input.setText(str(model_path))
        self._encoder_path_input.setText(str(encoder_path))
        self._model_info_path_input.setText(str(model_info_path))
        self._model_version_input.setText(model_info.version)
        self._apply_model_paths(model_path, encoder_path, model_info_path, model_info.version)

    def _apply_model_paths(
        self,
        model_path: Path,
        encoder_path: Path,
        model_info_path: Path,
        model_version: str,
    ) -> None:
        classifier = ActivityClassifier(model_path, encoder_path, FeatureExtractor(), model_version, model_info_path)
        if not classifier.is_available():
            QMessageBox.warning(self, "ML модель", f"Модель не применена: {classifier.load_error}")
            return
        if not classifier.is_compatible():
            QMessageBox.warning(self, "ML модель", f"Модель не применена: {classifier.compatibility_error}")
            return

        self._context.settings.model_path = model_path
        self._context.settings.label_encoder_path = encoder_path
        self._context.settings.model_info_path = model_info_path
        self._context.settings.model_version = model_version
        self._context.collector.set_classifier(classifier)
        self._context.settings_repository.save(self._context.settings)
        self._reload_category_controls()
        self._update_model_info_text()
        QMessageBox.information(self, "ML модель", "Модель применена и сохранена.")

    def _find_model_package_files(self, package_path: Path) -> tuple[Path, Path, Path]:
        if not package_path.exists() or not package_path.is_dir():
            raise FileNotFoundError("выбранная папка не существует")

        model_info_path = self._first_existing(
            package_path,
            ["model_info.json", "model_info_*.json", "*model_info*.json"],
        )
        model_info = ModelInfo.load(model_info_path)
        encoder_path = self._first_existing(
            package_path,
            [f"label_encoder_{model_info.version}.pkl", "label_encoder.pkl", "label_encoder_*.pkl", "*label_encoder*.pkl"],
        )
        model_path = self._first_existing(
            package_path,
            [f"model_{model_info.version}.pkl", "model.pkl", "model_*.pkl", "*.pkl"],
            exclude_keywords={"label_encoder", "encoder"},
        )
        return model_path, encoder_path, model_info_path

    def _first_existing(
        self,
        folder: Path,
        patterns: list[str],
        exclude_keywords: set[str] | None = None,
    ) -> Path:
        exclude_keywords = exclude_keywords or set()
        for pattern in patterns:
            candidates = sorted(folder.glob(pattern))
            for candidate in candidates:
                name = candidate.name.lower()
                if any(keyword in name for keyword in exclude_keywords):
                    continue
                if candidate.is_file():
                    return candidate
        raise FileNotFoundError(f"в папке {folder} не найден файл: {', '.join(patterns)}")

    def _is_valid_hex_color(self, value: str) -> bool:
        if len(value) != 7 or not value.startswith("#"):
            return False
        return all(char in "0123456789abcdefABCDEF" for char in value[1:])

    def check_model(self) -> None:
        classifier = ActivityClassifier(
            Path(self._model_path_input.text().strip()),
            Path(self._encoder_path_input.text().strip()),
            FeatureExtractor(),
            self._model_version_input.text().strip() or self._context.settings.model_version,
            Path(self._model_info_path_input.text().strip()),
        )
        if classifier.is_compatible():
            self._update_model_info_text()
            QMessageBox.information(self, "ML модель", "Модель успешно загружена и совместима с текущими признаками.")
        else:
            error = classifier.load_error or classifier.compatibility_error
            self._update_model_info_text()
            QMessageBox.warning(self, "ML модель", f"Ошибка проверки: {error}")

    def _update_model_info_text(self) -> None:
        status = "не проверена"
        model_type = "unknown"
        classes_text = "не удалось прочитать"
        feature_count = "не удалось прочитать"
        try:
            model_info = ModelInfo.load(self._context.settings.model_info_path)
            model_type = model_info.model_type
            feature_count = str(len(model_info.feature_columns))
            classes_text = ", ".join(self._category_display_name(class_name) for class_name in model_info.classes)
            classifier = ActivityClassifier(
                self._context.settings.model_path,
                self._context.settings.label_encoder_path,
                FeatureExtractor(),
                self._context.settings.model_version,
                self._context.settings.model_info_path,
            )
            status = "совместима" if classifier.is_compatible() else f"ошибка: {classifier.load_error or classifier.compatibility_error}"
        except Exception as exc:
            status = f"ошибка: {exc}"

        self._model_info_label.setText(
            "Текущая ML-модель\n"
            f"Версия: {self._context.settings.model_version}\n"
            f"Тип: {model_type}\n"
            f"Статус: {status}\n"
            f"Классы: {classes_text}\n"
            f"Количество признаков: {feature_count}\n"
            f"Файл модели: {self._context.settings.model_path}\n"
            f"LabelEncoder: {self._context.settings.label_encoder_path}\n"
            f"Model info: {self._context.settings.model_info_path}"
        )

    def _get_selected_record_id(self) -> int | None:
        if self._selected_record_id is None:
            if not self._context.settings.storage_enabled:
                QMessageBox.warning(
                    self,
                    "Временная запись",
                    "Ручная разметка доступна только для записей, сохраненных в базе данных. "
                    "Включите сохранение истории, чтобы размечать записи для переобучения.",
                )
            else:
                QMessageBox.warning(self, "Запись не выбрана", "Сначала выберите запись в таблице активности.")
            return None
        return self._selected_record_id

    def _setup_tray(self) -> None:
        self.procrastination_notification_requested.connect(self._show_procrastination_notification)
        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        self._tray_icon.setToolTip("Activity Monitor")
        self._tray_icon.activated.connect(self._on_tray_activated)

        self._tray_status_action = QAction("Статус: мониторинг остановлен", self)
        self._tray_status_action.setEnabled(False)
        self._tray_show_action = QAction("Показать окно", self)
        self._tray_start_action = QAction("Запустить мониторинг", self)
        self._tray_stop_action = QAction("Остановить мониторинг", self)
        self._tray_statistics_action = QAction("Открыть статистику", self)
        self._tray_exit_action = QAction("Выход", self)

        self._tray_show_action.triggered.connect(self.show_main_window)
        self._tray_start_action.triggered.connect(self.start_monitoring)
        self._tray_stop_action.triggered.connect(self.stop_monitoring)
        self._tray_statistics_action.triggered.connect(self.show_statistics_tab)
        self._tray_exit_action.triggered.connect(self.exit_application)

        tray_menu = QMenu(self)
        tray_menu.addAction(self._tray_status_action)
        tray_menu.addSeparator()
        tray_menu.addAction(self._tray_show_action)
        tray_menu.addAction(self._tray_start_action)
        tray_menu.addAction(self._tray_stop_action)
        tray_menu.addAction(self._tray_statistics_action)
        tray_menu.addSeparator()
        tray_menu.addAction(self._tray_exit_action)
        self._tray_icon.setContextMenu(tray_menu)
        self._update_tray_state()

        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon.show()
        self._context.collector.set_procrastination_callback(
            lambda title, message: self.procrastination_notification_requested.emit(title, message)
        )

    def show_main_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def show_statistics_tab(self) -> None:
        self.show_main_window()
        self._tabs.setCurrentIndex(1)
        self.refresh_statistics()

    def exit_application(self) -> None:
        self._force_exit = True
        if self._context.collector.is_running:
            self._context.collector.stop()
        self._tray_icon.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.show_main_window()

    def _update_tray_state(self) -> None:
        if not hasattr(self, "_tray_status_action"):
            return
        is_running = self._monitoring_active
        status = "запущен" if is_running else "остановлен"
        self._tray_status_action.setText(f"Статус: мониторинг {status}")
        self._tray_start_action.setEnabled(not is_running)
        self._tray_stop_action.setEnabled(is_running)
        self._tray_icon.setToolTip(f"Activity Monitor\nСтатус: мониторинг {status}")

    def _show_procrastination_notification(self, title: str, message: str) -> None:
        self._show_tray_message(title, message)

    def _show_tray_message(self, title: str, message: str) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 7000)
        else:
            self.statusBar().showMessage(f"{title}: {message}", 7000)

    def _select_save_path(self, title: str, default_name: str, file_filter: str) -> Path | None:
        file_path, _ = QFileDialog.getSaveFileName(self, title, default_name, file_filter)
        if not file_path:
            return None
        return Path(file_path)

    def _format_duration(self, seconds: float) -> str:
        minutes = seconds / 60
        if minutes < 60:
            return f"{minutes:.1f} мин"
        return f"{minutes / 60:.1f} ч"

    def _format_period_label(self, value: object) -> str:
        text = str(value)
        try:
            if len(text) == 13:
                return datetime.fromisoformat(f"{text}:00:00").strftime("%H:00")
            if len(text) == 10:
                return datetime.fromisoformat(text).strftime("%d.%m")
        except ValueError:
            pass
        return text

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f4f6f8;
                color: #1f2933;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 1px solid #d8dee6;
                background: #ffffff;
                border-radius: 6px;
            }
            QTabBar::tab {
                padding: 8px 14px;
                background: #e9edf2;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0f5c9c;
            }
            QFrame#panel, QFrame#card {
                background: #ffffff;
                border: 1px solid #d8dee6;
                border-radius: 6px;
            }
            QLabel#title {
                font-size: 18px;
                font-weight: 600;
            }
            QLabel#sectionTitle {
                font-weight: 600;
            }
            QLabel#muted {
                color: #64748b;
            }
            QLabel#metric {
                font-size: 22px;
                font-weight: 700;
                color: #0f5c9c;
            }
            QPushButton {
                background: #0f5c9c;
                color: #ffffff;
                border: none;
                padding: 7px 12px;
                border-radius: 5px;
            }
            QPushButton:disabled {
                background: #9aa8b5;
            }
            QPushButton:hover {
                background: #0b4f86;
            }
            QComboBox, QDateEdit, QLineEdit {
                background: #ffffff;
                border: 1px solid #c8d1dc;
                border-radius: 5px;
                padding: 5px;
            }
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #f7f9fb;
                border: 1px solid #d8dee6;
                gridline-color: #e5e9ef;
            }
            QHeaderView::section {
                background: #edf2f7;
                padding: 6px;
                border: none;
                border-right: 1px solid #d8dee6;
                font-weight: 600;
            }
            """
        )
