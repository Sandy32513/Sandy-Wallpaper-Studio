"""Configuration and live controls for automatic wallpaper rotation."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import Config, RotationPreferences
from app.database.category_repository import CategoryRepository
from app.database.database import Database
from app.services.rotation_scheduler import RotationScheduler
from app.services.rotation_service import RotationResult
from app.ui import design_system as ds


class RotationSettingsView(QWidget):
    """Dark-themed settings page for scheduling local library rotation."""

    status_message = Signal(str)

    def __init__(
        self,
        config: Config,
        db: Database,
        scheduler: RotationScheduler,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._category_repository = CategoryRepository(db)
        self._scheduler = scheduler
        self._preferences = config.rotation_preferences
        self._category_checks: dict[str, QCheckBox] = {}
        self._build_ui()
        self._scheduler.state_changed.connect(self._on_scheduler_state)
        self._scheduler.rotation_finished.connect(self._on_rotation_finished)
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._page_scroll = QScrollArea()
        self._page_scroll.setWidgetResizable(True)
        self._page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._page_scroll.setStyleSheet("background: transparent; border: none;")
        content = QWidget()
        self._page_scroll.setWidget(content)
        root.addWidget(self._page_scroll)

        outer = QVBoxLayout(content)
        outer.setContentsMargins(ds.SPACE_XL, ds.SPACE_XL, ds.SPACE_XL, ds.SPACE_XL)
        outer.setSpacing(ds.SPACE_LG)

        title = QLabel("Automatic Rotation")
        title.setStyleSheet(
            f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_XL + 4}px; font-weight: 700;"
        )
        outer.addWidget(title)

        description = QLabel(
            "Schedule wallpapers from your local library. Rotation never downloads, moves, "
            "or deletes image files. The first change happens after the selected interval."
        )
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_MD}px;")
        outer.addWidget(description)

        status_card = QFrame()
        status_card.setStyleSheet(
            f"QFrame {{ background: {ds.BG_SURFACE}; border: 1px solid {ds.BG_BORDER}; "
            "border-radius: 8px; }"
        )
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(ds.SPACE_LG, ds.SPACE_MD, ds.SPACE_LG, ds.SPACE_MD)
        self._status_label = QLabel()
        self._status_label.setObjectName("rotationStatus")
        self._status_label.setAccessibleName("Automatic rotation status")
        self._status_label.setStyleSheet(
            f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_MD}px; font-weight: 600;"
        )
        self._next_label = QLabel()
        self._next_label.setAccessibleName("Next scheduled rotation")
        self._next_label.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_SM}px;")
        status_layout.addWidget(self._status_label)
        status_layout.addWidget(self._next_label)
        outer.addWidget(status_card)

        self._enabled = QCheckBox("Enable automatic rotation")
        self._enabled.setChecked(self._preferences.enabled)
        self._enabled.setAccessibleName("Enable automatic rotation")
        self._enabled.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-weight: 600;")
        outer.addWidget(self._enabled)

        form = QFormLayout()
        form.setHorizontalSpacing(ds.SPACE_LG)
        form.setVerticalSpacing(ds.SPACE_MD)
        self._interval = QSpinBox()
        self._interval.setRange(1, 10_080)
        self._interval.setValue(self._preferences.interval_minutes)
        self._interval.setSuffix(" minutes")
        self._interval.setAccessibleName("Rotation interval in minutes")
        form.addRow("Rotation interval", self._interval)

        self._random = QCheckBox("Choose randomly (otherwise cycle by library order)")
        self._random.setChecked(self._preferences.random_selection)
        self._random.setAccessibleName("Choose wallpapers randomly")
        form.addRow("Selection", self._random)

        self._min_width = QSpinBox()
        self._min_width.setRange(0, 32_768)
        self._min_width.setSingleStep(100)
        self._min_width.setSpecialValueText("Any width")
        self._min_width.setSuffix(" px")
        self._min_width.setValue(self._preferences.min_width)
        self._min_width.setAccessibleName("Minimum wallpaper width")
        form.addRow("Minimum width", self._min_width)

        self._min_height = QSpinBox()
        self._min_height.setRange(0, 32_768)
        self._min_height.setSingleStep(100)
        self._min_height.setSpecialValueText("Any height")
        self._min_height.setSuffix(" px")
        self._min_height.setValue(self._preferences.min_height)
        self._min_height.setAccessibleName("Minimum wallpaper height")
        form.addRow("Minimum height", self._min_height)
        outer.addLayout(form)

        category_title = QLabel("Categories")
        category_title.setStyleSheet(f"color: {ds.TEXT_PRIMARY}; font-weight: 600;")
        outer.addWidget(category_title)

        category_help = QLabel("Leave every category unchecked to include all categories.")
        category_help.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_SM}px;")
        outer.addWidget(category_help)

        category_scroll = QScrollArea()
        category_scroll.setWidgetResizable(True)
        category_scroll.setFrameShape(QFrame.Shape.StyledPanel)
        category_scroll.setMaximumHeight(180)
        category_scroll.setStyleSheet(
            f"QScrollArea {{ background: {ds.BG_SURFACE}; border: 1px solid {ds.BG_BORDER}; }}"
        )
        category_container = QWidget()
        category_layout = QVBoxLayout(category_container)
        category_layout.setContentsMargins(ds.SPACE_MD, ds.SPACE_SM, ds.SPACE_MD, ds.SPACE_SM)
        for category in self._category_repository.get_all():
            check = QCheckBox(category.name)
            check.setChecked(category.name in self._preferences.categories)
            check.setAccessibleName(f"Rotate wallpapers in {category.name}")
            self._category_checks[category.name] = check
            category_layout.addWidget(check)
        category_layout.addStretch()
        category_scroll.setWidget(category_container)
        outer.addWidget(category_scroll)

        self._validation_label = QLabel()
        self._validation_label.setWordWrap(True)
        self._validation_label.setAccessibleName("Rotation settings validation")
        self._validation_label.setStyleSheet(f"color: {ds.DANGER};")
        self._validation_label.hide()
        outer.addWidget(self._validation_label)

        controls = QHBoxLayout()
        self._apply_button = QPushButton("Start / Apply Settings")
        self._apply_button.setObjectName("accent")
        self._apply_button.setAccessibleName("Save or start automatic rotation")
        self._apply_button.clicked.connect(self._apply_settings)
        self._enabled.toggled.connect(self._update_apply_button_text)
        controls.addWidget(self._apply_button)

        self._pause_button = QPushButton("Pause")
        self._pause_button.setAccessibleName("Pause automatic rotation")
        self._pause_button.clicked.connect(self._scheduler.pause)
        controls.addWidget(self._pause_button)

        self._resume_button = QPushButton("Resume")
        self._resume_button.setAccessibleName("Resume automatic rotation")
        self._resume_button.clicked.connect(self._scheduler.resume)
        controls.addWidget(self._resume_button)

        self._stop_button = QPushButton("Stop")
        self._stop_button.setAccessibleName("Stop automatic rotation")
        self._stop_button.clicked.connect(self._stop_rotation)
        controls.addWidget(self._stop_button)
        controls.addStretch()
        outer.addLayout(controls)
        outer.addStretch()

        self.setStyleSheet(
            f"QWidget {{ color: {ds.TEXT_PRIMARY}; }} QCheckBox {{ spacing: 8px; }} "
            f"QCheckBox:focus {{ color: {ds.ACCENT_LIGHT}; background: {ds.BG_ELEVATED}; }} "
            f"QSpinBox {{ min-height: 30px; padding: 2px 8px; background: {ds.BG_INPUT}; "
            f"color: {ds.TEXT_PRIMARY}; border: 1px solid {ds.BG_BORDER}; border-radius: 4px; }} "
            f"QSpinBox:focus {{ border: 2px solid {ds.ACCENT_LIGHT}; padding: 1px 7px; }} "
            f"QPushButton {{ min-height: 34px; padding: 4px 14px; background: {ds.BG_INPUT}; "
            f"color: {ds.TEXT_PRIMARY}; border: 1px solid {ds.BG_BORDER}; border-radius: 6px; }} "
            f"QPushButton:hover {{ background: {ds.BG_ELEVATED}; }} "
            f"QPushButton:focus {{ border: 2px solid {ds.ACCENT_LIGHT}; padding: 3px 13px; }} "
            f"QPushButton#accent {{ background: {ds.ACCENT_PRIMARY}; border-color: {ds.ACCENT_PRIMARY}; }} "
            f"QPushButton#accent:focus {{ border: 2px solid {ds.ACCENT_LIGHT}; }} "
            f"QPushButton:disabled {{ color: {ds.TEXT_DISABLED}; background: {ds.BG_DEEP}; }}"
        )
        focus_order: list[QWidget] = [
            self._enabled,
            self._interval,
            self._random,
            self._min_width,
            self._min_height,
            *self._category_checks.values(),
            self._apply_button,
            self._pause_button,
            self._resume_button,
            self._stop_button,
        ]
        for current, following in zip(focus_order, focus_order[1:], strict=False):
            self.setTabOrder(current, following)

    def _collect_preferences(self, enabled: bool | None = None) -> RotationPreferences:
        categories = tuple(
            name for name, checkbox in self._category_checks.items() if checkbox.isChecked()
        )
        return RotationPreferences(
            enabled=self._enabled.isChecked() if enabled is None else enabled,
            interval_minutes=self._interval.value(),
            random_selection=self._random.isChecked(),
            categories=categories,
            min_width=self._min_width.value(),
            min_height=self._min_height.value(),
        )

    def _apply_settings(self) -> None:
        try:
            preferences = self._collect_preferences()
        except ValueError as exc:
            self._validation_label.setText(str(exc))
            self._validation_label.show()
            return
        self._validation_label.hide()
        self._config.set_rotation_preferences(preferences)
        self._config.save()
        self._scheduler.configure(preferences, style=str(self._config.get("wallpaper_style", "Fill")))
        self._preferences = preferences
        self.status_message.emit("Automatic rotation settings saved.")
        self.refresh()

    def _stop_rotation(self) -> None:
        preferences = self._collect_preferences(enabled=False)
        self._enabled.setChecked(False)
        self._config.set_rotation_preferences(preferences)
        self._config.save()
        self._scheduler.configure(preferences, style=str(self._config.get("wallpaper_style", "Fill")))
        self._preferences = preferences
        self.status_message.emit("Automatic rotation stopped.")
        self.refresh()

    def _on_scheduler_state(self, state: str, message: str) -> None:
        self._status_label.setText(message)
        next_rotation = self._scheduler.next_rotation_at
        self._next_label.setText(self._format_next_rotation(next_rotation))
        self._pause_button.setEnabled(state == "running")
        self._resume_button.setEnabled(state == "paused")
        self._stop_button.setEnabled(state in {"running", "paused"})
        self._update_apply_button_text()

    def _on_rotation_finished(self, result: RotationResult) -> None:
        if result.error == "CANCELLED":
            return
        if result.success:
            message = f"Automatic rotation applied wallpaper #{result.wallpaper_id}."
        else:
            message = result.message or "Automatic rotation could not find an eligible wallpaper."
        self._status_label.setText(message)
        self.status_message.emit(message)
        self._next_label.setText(self._format_next_rotation(self._scheduler.next_rotation_at))

    def refresh(self) -> None:
        """Update live state and next scheduled time without applying a wallpaper."""
        state = self._scheduler.state
        if state == "disabled":
            self._status_label.setText("Automatic rotation is disabled.")
        elif state == "running":
            self._status_label.setText("Automatic rotation is running.")
        elif state == "paused":
            self._status_label.setText("Automatic rotation is paused.")
        elif state == "stopped":
            self._status_label.setText("Automatic rotation is stopped.")
        self._next_label.setText(self._format_next_rotation(self._scheduler.next_rotation_at))
        self._pause_button.setEnabled(state == "running")
        self._resume_button.setEnabled(state == "paused")
        self._stop_button.setEnabled(state in {"running", "paused"})
        self._update_apply_button_text()

    def _update_apply_button_text(self, _checked: bool | None = None) -> None:
        if not self._enabled.isChecked():
            text = "Save Settings"
        elif self._scheduler.state in {"running", "paused"}:
            text = "Apply Settings"
        else:
            text = "Start Rotation"
        self._apply_button.setText(text)

    @staticmethod
    def _format_next_rotation(next_rotation: datetime | None) -> str:
        if next_rotation is None:
            return "Next rotation: not scheduled"
        return f"Next rotation: {next_rotation.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}"
