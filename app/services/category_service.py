"""Business rules for category management and rotation consistency."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.config import Config
from app.database.category_repository import CategoryRepository
from app.database.models import Category


class CategoryServiceError(ValueError):
    """A user-correctable category operation error."""


@dataclass(frozen=True)
class CategorySummary:
    category: Category
    wallpaper_count: int


@dataclass(frozen=True)
class CategoryDeletion:
    name: str
    wallpaper_count: int


class CategoryService:
    """Coordinate category persistence with wallpaper labels and settings."""

    def __init__(self, repository: CategoryRepository, config: Config) -> None:
        self._repository = repository
        self._config = config

    def list_categories(self) -> list[CategorySummary]:
        """Return categories ordered by sort order and name, with grouped counts."""
        return [
            CategorySummary(category=category, wallpaper_count=count)
            for category, count in self._repository.get_all_with_wallpaper_counts()
        ]

    def add(self, name: str) -> Category:
        clean_name = self._clean_name(name)
        self._ensure_unique(clean_name)
        categories = self._repository.get_all()
        next_order = max((category.sort_order for category in categories), default=-1) + 1
        try:
            category_id = self._repository.add(
                Category(name=clean_name, is_default=False, sort_order=next_order)
            )
        except sqlite3.IntegrityError as exc:
            raise CategoryServiceError(
                f'A category named "{clean_name}" already exists.'
            ) from exc
        except Exception as exc:
            raise CategoryServiceError(
                f'Category "{clean_name}" was not added; no category data changed. {exc}'
            ) from exc
        category = self._repository.get_by_id(category_id)
        if category is None:
            raise CategoryServiceError("The category was saved but could not be reloaded.")
        return category

    def rename(self, category_id: int, name: str) -> Category:
        current = self._get_category(category_id)
        self._ensure_custom(current)
        clean_name = self._clean_name(name)
        self._ensure_unique(clean_name, except_id=category_id)
        if clean_name == current.name:
            return current

        old_rotation = list(self._config.get("rotation_categories", []))
        new_rotation = [
            clean_name if value == current.name else value for value in old_rotation
        ]
        try:
            renamed = self._repository.rename(category_id, clean_name)
        except sqlite3.IntegrityError as exc:
            raise CategoryServiceError(
                f'A category named "{clean_name}" already exists.'
            ) from exc
        except Exception as exc:
            raise CategoryServiceError(
                f'Category "{current.name}" was not renamed; wallpaper labels and rotation '
                f"settings remain unchanged. {exc}"
            ) from exc
        if not renamed:
            raise CategoryServiceError("The category no longer exists.")

        if new_rotation != old_rotation:
            try:
                self._config.apply_settings({"rotation_categories": new_rotation})
            except Exception as save_error:
                try:
                    restored = self._repository.rename(category_id, current.name)
                    if not restored:
                        raise RuntimeError("The renamed category could not be restored.")
                except Exception as restore_error:
                    raise CategoryServiceError(
                        f'The category and wallpaper labels were renamed to "{clean_name}", '
                        f"but rotation settings were not saved. The database remains renamed; "
                        f"rotation settings still contain the previous name "
                        f'"{current.name}". Restore failed: {restore_error}.'
                    ) from save_error
                raise CategoryServiceError(
                    f'Could not save rotation settings. The category and wallpaper labels '
                    f'were restored to "{current.name}"; rotation settings are unchanged.'
                ) from save_error

        updated = self._repository.get_by_id(category_id)
        if updated is None:
            raise CategoryServiceError("The renamed category could not be reloaded.")
        return updated

    def delete(self, category_id: int) -> CategoryDeletion:
        category = self._get_category(category_id)
        self._ensure_custom(category)
        wallpaper_count = self._repository.count_wallpapers(category.name)
        old_rotation = list(self._config.get("rotation_categories", []))
        new_rotation = [value for value in old_rotation if value != category.name]

        # Persist settings first. If the database delete fails, restore the old filters.
        if new_rotation != old_rotation:
            try:
                self._config.apply_settings({"rotation_categories": new_rotation})
            except Exception as exc:
                raise CategoryServiceError(
                    f'Could not save rotation settings; category "{category.name}" was not deleted.'
                ) from exc

        try:
            deleted = self._repository.delete(category_id)
            if not deleted:
                raise CategoryServiceError("The category no longer exists.")
        except Exception as delete_error:
            if new_rotation != old_rotation:
                try:
                    self._config.apply_settings({"rotation_categories": old_rotation})
                except Exception as restore_error:
                    raise CategoryServiceError(
                        f'Category "{category.name}" was not deleted, but its rotation '
                        f"filter could not be restored. Settings now contain the cleaned list; "
                        f"restore failed: {restore_error}."
                    ) from delete_error
            if isinstance(delete_error, CategoryServiceError):
                raise
            raise CategoryServiceError(
                f'Could not delete category "{category.name}"; wallpaper rows and files were kept.'
            ) from delete_error
        return CategoryDeletion(name=category.name, wallpaper_count=wallpaper_count)

    def reorder(self, ordered_ids: list[int]) -> None:
        categories = self._repository.get_all()
        expected = {category.id for category in categories if category.id is not None}
        if len(expected) != len(categories):
            raise CategoryServiceError("A category is missing its database identity.")
        actual = set(ordered_ids)
        if len(ordered_ids) != len(actual) or actual != expected:
            raise CategoryServiceError("The category order is incomplete or contains duplicates.")
        self._repository.set_sort_order(ordered_ids)

    def open_in_library(self, category_id: int) -> str:
        """Return the category label that the Library should use as its filter."""
        return self._get_category(category_id).name

    def _get_category(self, category_id: int) -> Category:
        category = self._repository.get_by_id(category_id)
        if category is None:
            raise CategoryServiceError("The selected category no longer exists.")
        return category

    @staticmethod
    def _ensure_custom(category: Category) -> None:
        if category.is_default:
            raise CategoryServiceError(
                "Built-in categories can be viewed and reordered, but not renamed or deleted."
            )

    def _ensure_unique(self, name: str, *, except_id: int | None = None) -> None:
        folded_name = name.casefold()
        for category in self._repository.get_all():
            if category.id != except_id and category.name.casefold() == folded_name:
                raise CategoryServiceError(
                    f'A category named "{category.name}" already exists.'
                )

    @staticmethod
    def _clean_name(name: str) -> str:
        clean_name = name.strip()
        if not clean_name:
            raise CategoryServiceError("Enter a category name.")
        return clean_name
