"""Accessible category management view."""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.category_service import (
    CategoryService,
    CategorySummary,
)
from app.ui import design_system as ds

DeleteConfirmation = Callable[[str, int], bool]


class _ReorderableList(QListWidget):
    order_changed = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("categoryList")
        self.setAccessibleName("Wallpaper categories")
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    def dropEvent(self, event) -> None:  # noqa: N802
        super().dropEvent(event)
        ordered_ids = [
            int(self.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.count())
        ]
        self.order_changed.emit(ordered_ids)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.fit_rows()

    def fit_rows(self) -> None:
        row_width = self.viewport().width()
        for index in range(self.count()):
            row = self.itemWidget(self.item(index))
            if row is not None:
                row.setFixedWidth(row_width)


class _CategoryRow(QFrame):
    def __init__(
        self,
        summary: CategorySummary,
        row_index: int,
        row_count: int,
        *,
        open_requested: Callable[[], None],
        move_requested: Callable[[int], None],
        rename_requested: Callable[[], None],
        delete_requested: Callable[[], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        category = summary.category
        self.setObjectName("categoryRow")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"QFrame#categoryRow {{ background: {ds.BG_SURFACE}; "
            f"border: 1px solid {ds.BG_BORDER}; border-radius: 8px; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(ds.SPACE_MD, ds.SPACE_SM, ds.SPACE_MD, ds.SPACE_SM)
        layout.setSpacing(ds.SPACE_SM)

        text_column = QVBoxLayout()
        text_column.setSpacing(ds.SPACE_XS)
        name_label = QLabel(category.name)
        name_label.setAccessibleName(f"Category: {category.name}")
        name_label.setStyleSheet(
            f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_MD}px; font-weight: 600;"
        )
        details = "Built-in" if category.is_default else "Custom"
        details += f" · {summary.wallpaper_count} wallpaper"
        if summary.wallpaper_count != 1:
            details += "s"
        details_label = QLabel(details)
        details_label.setAccessibleName(
            f"{'Built-in' if category.is_default else 'Custom'} category, "
            f"{summary.wallpaper_count} wallpapers"
        )
        details_label.setStyleSheet(
            f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_SM}px;"
        )
        text_column.addWidget(name_label)
        text_column.addWidget(details_label)
        layout.addLayout(text_column, stretch=1)

        self.open_button = self._button(
            "Open",
            f"Open {category.name} in Library",
            open_requested,
        )
        self.open_button.setToolTip(f"Open {category.name} in Library")
        layout.addWidget(self.open_button)

        self.up_button = self._button(
            "↑",
            f"Move {category.name} up",
            lambda: move_requested(-1),
        )
        self.up_button.setEnabled(row_index > 0)
        self.up_button.setToolTip("Move this category up in the list")
        layout.addWidget(self.up_button)

        self.down_button = self._button(
            "↓",
            f"Move {category.name} down",
            lambda: move_requested(1),
        )
        self.down_button.setEnabled(row_index < row_count - 1)
        self.down_button.setToolTip("Move this category down in the list")
        layout.addWidget(self.down_button)

        self.rename_button = self._button("Rename", f"Rename {category.name}", rename_requested)
        self.delete_button = self._button("Delete", f"Delete {category.name}", delete_requested)
        if category.is_default:
            reason = "Built-in categories can be viewed and reordered, but not renamed or deleted."
            for button in (self.rename_button, self.delete_button):
                button.setEnabled(False)
                button.setToolTip(reason)
        else:
            self.delete_button.setObjectName("danger")
        layout.addWidget(self.rename_button)
        layout.addWidget(self.delete_button)

    @staticmethod
    def _button(text: str, accessible_name: str, callback: Callable[[], None]) -> QPushButton:
        button = QPushButton(text)
        button.setAccessibleName(accessible_name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        return button


class CategoriesView(QWidget):
    """Manage user categories while preserving wallpaper and rotation data."""

    status_message = Signal(str)
    navigate_to = Signal(str)
    open_library_requested = Signal(str)

    def __init__(
        self,
        service: CategoryService,
        parent: Optional[QWidget] = None,
        *,
        confirm_delete: DeleteConfirmation | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._confirm_delete = confirm_delete or self._show_delete_confirmation
        self._summaries: list[CategorySummary] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            f"QPushButton:focus {{ border: 2px solid {ds.ACCENT_LIGHT}; }}\n"
            f"QLineEdit:focus {{ border: 2px solid {ds.ACCENT_LIGHT}; }}\n"
            f"QListWidget:focus {{ border: 2px solid {ds.ACCENT_LIGHT}; }}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("categoriesHeader")
        header.setStyleSheet(
            f"QFrame#categoriesHeader {{ background: {ds.BG_SURFACE}; "
            f"border-bottom: 1px solid {ds.BG_BORDER}; }}"
        )
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(ds.SPACE_XL, ds.SPACE_LG, ds.SPACE_XL, ds.SPACE_LG)
        header_layout.setSpacing(ds.SPACE_SM)

        title = QLabel("Categories")
        title.setObjectName("title")
        title.setAccessibleName("Categories")
        title.setStyleSheet(
            f"color: {ds.TEXT_PRIMARY}; font-size: {ds.FONT_SIZE_XL}px; font-weight: 700;"
        )
        subtitle = QLabel("Organize wallpapers with custom categories.")
        subtitle.setWordWrap(True)
        subtitle.setAccessibleName("Category management description")
        subtitle.setStyleSheet(f"color: {ds.TEXT_SECONDARY};")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        add_row = QHBoxLayout()
        add_row.setSpacing(ds.SPACE_SM)
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("New category name")
        self._name_input.setAccessibleName("New category name")
        self._name_input.setMaxLength(120)
        self._name_input.returnPressed.connect(self._add_from_input)
        add_row.addWidget(self._name_input, stretch=1)
        self._add_button = QPushButton("Add Category")
        self._add_button.setObjectName("accent")
        self._add_button.setAccessibleName("Add category")
        self._add_button.clicked.connect(self._add_from_input)
        add_row.addWidget(self._add_button)
        header_layout.addLayout(add_row)
        root.addWidget(header)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(ds.SPACE_XL, ds.SPACE_MD, ds.SPACE_XL, ds.SPACE_MD)
        content_layout.setSpacing(ds.SPACE_SM)

        self._empty_label = QLabel(
            "No custom categories yet. Add one above to organize your wallpapers."
        )
        self._empty_label.setWordWrap(True)
        self._empty_label.setAccessibleName("No custom categories")
        self._empty_label.setStyleSheet(
            f"color: {ds.TEXT_SECONDARY}; background: {ds.BG_ELEVATED}; "
            f"border: 1px solid {ds.BG_BORDER}; border-radius: 6px; padding: {ds.SPACE_MD}px;"
        )
        content_layout.addWidget(self._empty_label)

        self._error_label = QLabel()
        self._error_label.setWordWrap(True)
        self._error_label.setAccessibleName("Category error")
        self._error_label.setStyleSheet(f"color: {ds.DANGER};")
        self._error_label.hide()
        content_layout.addWidget(self._error_label)

        self._retry_button = QPushButton("Retry")
        self._retry_button.setAccessibleName("Retry loading categories")
        self._retry_button.clicked.connect(self.refresh)
        self._retry_button.hide()
        content_layout.addWidget(self._retry_button, alignment=Qt.AlignmentFlag.AlignLeft)

        self._list = _ReorderableList()
        self._list.order_changed.connect(self._persist_drag_order)
        self._list.itemActivated.connect(self._open_activated_item)
        content_layout.addWidget(self._list, stretch=1)

        self._status_label = QLabel("Ready")
        self._status_label.setAccessibleName("Category screen status")
        self._status_label.setStyleSheet(f"color: {ds.TEXT_SECONDARY}; font-size: {ds.FONT_SIZE_SM}px;")
        content_layout.addWidget(self._status_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)
        self._scroll = scroll

    def refresh(self) -> None:
        """Reload categories from the service and update both empty and error states."""
        try:
            summaries = self._service.list_categories()
        except Exception as exc:
            self._summaries = []
            self._list.clear()
            self._empty_label.hide()
            self._error_label.setText(f"Categories could not be loaded: {exc}")
            self._error_label.show()
            self._retry_button.show()
            self._status_label.setText("Category list unavailable")
            self.status_message.emit("Categories could not be loaded. Retry to try again.")
            return

        self._summaries = summaries
        self._error_label.hide()
        self._retry_button.hide()
        self._list.clear()
        custom_count = sum(not summary.category.is_default for summary in summaries)
        self._empty_label.setVisible(custom_count == 0)
        for index, summary in enumerate(summaries):
            category = summary.category
            category_id = category.id
            if category_id is None:
                continue

            def open_requested(category_id: int = category_id) -> None:
                self.open_category(category_id)

            def move_requested(offset: int, category_id: int = category_id) -> None:
                self.move_category(category_id, offset)

            def rename_requested(category_id: int = category_id) -> None:
                self._prompt_rename(category_id)

            def delete_requested(category_id: int = category_id) -> None:
                self.delete_category(category_id)

            item = QListWidgetItem()
            item.setText(category.name)
            item.setData(Qt.ItemDataRole.UserRole, category_id)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsDragEnabled
                | Qt.ItemFlag.ItemIsDropEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
            )
            self._list.addItem(item)
            row = _CategoryRow(
                summary,
                index,
                len(summaries),
                open_requested=open_requested,
                move_requested=move_requested,
                rename_requested=rename_requested,
                delete_requested=delete_requested,
            )
            item.setSizeHint(QSize(0, row.sizeHint().height()))
            self._list.setItemWidget(item, row)
        self._list.fit_rows()
        self._update_tab_order()
        self._status_label.setText(
            f"{len(summaries)} categories · {custom_count} custom"
        )

    def _update_tab_order(self) -> None:
        controls: list[QWidget] = [self._name_input, self._add_button]
        for index in range(self._list.count()):
            row = self._list.itemWidget(self._list.item(index))
            if isinstance(row, _CategoryRow):
                controls.extend(
                    [
                        row.open_button,
                        row.up_button,
                        row.down_button,
                        row.rename_button,
                        row.delete_button,
                    ]
                )
        for first, second in zip(controls, controls[1:], strict=False):
            self.setTabOrder(first, second)

    def add_category(self, name: str) -> bool:
        try:
            category = self._service.add(name)
        except Exception as exc:
            self._show_error(str(exc))
            return False
        self._name_input.clear()
        self.refresh()
        self._announce(f'Added category "{category.name}".')
        return True

    def rename_category(self, category_id: int, name: str) -> bool:
        try:
            category = self._service.rename(category_id, name)
        except Exception as exc:
            self._show_error(str(exc))
            return False
        self.refresh()
        self._announce(
            f'Renamed category to "{category.name}". Wallpaper labels and rotation filters were updated.'
        )
        return True

    def delete_category(self, category_id: int) -> bool:
        category = next(
            (summary.category for summary in self._summaries if summary.category.id == category_id),
            None,
        )
        if category is None:
            self._show_error("The selected category is no longer available.")
            return False
        wallpaper_count = next(
            summary.wallpaper_count
            for summary in self._summaries
            if summary.category.id == category_id
        )
        if not self._confirm_delete(category.name, wallpaper_count):
            self._announce("Category deletion cancelled; no data changed.")
            return False
        try:
            deletion = self._service.delete(category_id)
        except Exception as exc:
            self._show_error(str(exc))
            return False
        self.refresh()
        noun = "wallpaper keeps" if deletion.wallpaper_count == 1 else "wallpapers keep"
        self._announce(
            f'Deleted "{deletion.name}". {deletion.wallpaper_count} {noun} the text label '
            "and now appear uncategorized. No wallpaper or file was deleted."
        )
        return True

    def move_category(self, category_id: int, offset: int) -> bool:
        ids: list[int] = []
        for summary in self._summaries:
            stored_id = summary.category.id
            if stored_id is not None:
                ids.append(stored_id)
        if category_id not in ids:
            return False
        index = ids.index(category_id)
        destination = index + offset
        if not 0 <= destination < len(ids):
            return False
        ids[index], ids[destination] = ids[destination], ids[index]
        try:
            self._service.reorder(ids)
        except Exception as exc:
            self._show_error(str(exc))
            self.refresh()
            return False
        self.refresh()
        self._announce("Category order saved.")
        return True

    def open_category(self, category_id: int | None) -> bool:
        if category_id is None:
            return False
        try:
            category_name = self._service.open_in_library(category_id)
        except Exception as exc:
            self._show_error(str(exc))
            return False
        self.open_library_requested.emit(category_name)
        self.navigate_to.emit("library")
        self._announce(f'Opening Library filtered to "{category_name}".')
        return True

    def _add_from_input(self) -> None:
        self.add_category(self._name_input.text())

    def _prompt_rename(self, category_id: int) -> None:
        from PySide6.QtWidgets import QInputDialog

        category = next(
            (summary.category for summary in self._summaries if summary.category.id == category_id),
            None,
        )
        if category is None or category.is_default:
            return
        name, accepted = QInputDialog.getText(
            self, "Rename Category", "Category name:", text=category.name
        )
        if accepted:
            self.rename_category(category_id, name)

    def _persist_drag_order(self, ordered_ids: list[int]) -> None:
        try:
            self._service.reorder(ordered_ids)
        except Exception as exc:
            self._show_error(str(exc))
            # Rebuild from persisted order, including after a failed drag save.
            self.refresh()
        else:
            self.refresh()
            self._announce("Category order saved.")

    def _open_activated_item(self, item: QListWidgetItem) -> None:
        category_id = item.data(Qt.ItemDataRole.UserRole)
        self.open_category(int(category_id) if category_id is not None else None)

    def _show_error(self, message: str) -> None:
        self._status_label.setText(message)
        self.status_message.emit(message)

    def _announce(self, message: str) -> None:
        self._status_label.setText(message)
        self.status_message.emit(message)

    @staticmethod
    def _show_delete_confirmation(name: str, wallpaper_count: int) -> bool:
        noun = "wallpaper" if wallpaper_count == 1 else "wallpapers"
        message = (
            f'Delete category "{name}"? {wallpaper_count} {noun} will keep the text label '
            "and become uncategorized. No wallpaper or file will be deleted."
        )
        box = QMessageBox(QMessageBox.Icon.Warning, "Delete Category", message)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes
