"""Pure row/column layout logic for dockable content.

This module deliberately has no ImGui or window imports.  It is the small,
testable model behind docking: the view decides *where* the user wants to move
an item, and :class:`ContentLayout` applies that move.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, Iterable, Sequence, TypeVar


T = TypeVar("T")


class DockPlacement(StrEnum):
    """Position of an item relative to a target item."""

    LEFT = "left"
    RIGHT = "right"
    ABOVE = "above"
    BELOW = "below"
    BOTTOM = "bottom"


@dataclass(frozen=True)
class LayoutPosition:
    row: int
    column: int


class ContentLayout(Generic[T]):
    """An identity-based layout made of rows with a column limit.

    Items are compared by identity instead of equality. UI components are
    stateful objects, so two equal-looking instances must still be treated as
    separate contents.
    """

    def __init__(
            self,
            items: Iterable[T] = (),
            *,
            max_columns: int = 2,
    ):
        if max_columns < 1:
            raise ValueError("A content layout needs at least one column")
        self.max_columns = max_columns
        self._rows: list[list[T]] = []
        for item in items:
            self.add(item)

    @property
    def rows(self) -> tuple[tuple[T, ...], ...]:
        return tuple(tuple(row) for row in self._rows)

    @property
    def items(self) -> tuple[T, ...]:
        return tuple(item for row in self._rows for item in row)

    def __len__(self) -> int:
        return sum(len(row) for row in self._rows)

    def __contains__(self, item: object) -> bool:
        return self.position_of(item) is not None

    def position_of(self, item: object) -> LayoutPosition | None:
        for row_index, row in enumerate(self._rows):
            for column_index, existing in enumerate(row):
                if existing is item:
                    return LayoutPosition(row_index, column_index)
        return None

    def can_place(
            self,
            item: T | None,
            *,
            target: T | None = None,
            placement: DockPlacement = DockPlacement.BOTTOM,
    ) -> bool:
        """Return whether ``item`` can be added or moved as requested."""
        if target is None:
            return placement == DockPlacement.BOTTOM
        if item is target:
            return False

        target_position = self.position_of(target)
        if target_position is None:
            return False
        if placement in (DockPlacement.ABOVE, DockPlacement.BELOW):
            return True
        if placement not in (DockPlacement.LEFT, DockPlacement.RIGHT):
            return False

        occupied = len(self._rows[target_position.row])
        item_position = self.position_of(item)
        if item_position is not None and item_position.row == target_position.row:
            occupied -= 1
        return occupied < self.max_columns

    def add(
            self,
            item: T,
            *,
            target: T | None = None,
            placement: DockPlacement = DockPlacement.BOTTOM,
    ):
        """Add an item at the requested location."""
        if item in self:
            raise ValueError("The item already belongs to this layout")
        if not self.can_place(item, target=target, placement=placement):
            raise ValueError("The item cannot be placed at the requested position")
        self._insert(item, target=target, placement=placement)

    def move(
            self,
            item: T,
            *,
            target: T | None = None,
            placement: DockPlacement = DockPlacement.BOTTOM,
    ) -> bool:
        """Move an existing item, returning ``False`` for an invalid no-op."""
        if item not in self:
            raise ValueError("The item does not belong to this layout")
        if not self.can_place(item, target=target, placement=placement):
            return False

        old_rows = self.rows
        self.remove(item)
        self._insert(item, target=target, placement=placement)
        return self._identity_signature(self.rows) != self._identity_signature(
            old_rows
        )

    def remove(self, item: T) -> LayoutPosition:
        """Remove an item and return its former position."""
        position = self.position_of(item)
        if position is None:
            raise ValueError("The item does not belong to this layout")
        self._rows[position.row].pop(position.column)
        if not self._rows[position.row]:
            self._rows.pop(position.row)
        return position

    def replace_many(self, items: Sequence[T], replacement: T):
        """Replace several items with one item at the first item's position."""
        candidates = tuple(items)
        if not candidates:
            raise ValueError("At least one item is required")
        if len({id(item) for item in candidates}) != len(candidates):
            raise ValueError("An item can only occur once in a replacement")
        if any(item not in self for item in candidates):
            raise ValueError("All replaced items must belong to this layout")
        if replacement in self and all(replacement is not item for item in candidates):
            raise ValueError("The replacement already belongs to this layout")

        candidate_ids = {id(item) for item in candidates}
        inserted = False
        new_rows: list[list[T]] = []
        for row in self._rows:
            new_row: list[T] = []
            for item in row:
                if id(item) in candidate_ids:
                    if not inserted:
                        new_row.append(replacement)
                        inserted = True
                else:
                    new_row.append(item)
            if new_row:
                new_rows.append(new_row)
        self._rows = new_rows

    def replace_one(self, item: T, replacements: Sequence[T]):
        """Replace one item and wrap an overflowing row into further rows."""
        position = self.position_of(item)
        if position is None:
            raise ValueError("The replaced item does not belong to this layout")
        replacements = tuple(replacements)
        if len({id(value) for value in replacements}) != len(replacements):
            raise ValueError("A replacement item can only occur once")
        for replacement in replacements:
            if replacement in self and replacement is not item:
                raise ValueError("A replacement already belongs to this layout")

        row = self._rows[position.row]
        expanded = (
            row[:position.column]
            + list(replacements)
            + row[position.column + 1:]
        )
        wrapped = [
            expanded[index:index + self.max_columns]
            for index in range(0, len(expanded), self.max_columns)
        ]
        self._rows[position.row:position.row + 1] = wrapped

    def stack(self):
        """Arrange all current items vertically, preserving their order."""
        self._rows = [[item] for item in self.items]

    def restore(self, rows: Iterable[Iterable[T]]):
        """Replace the complete layout after validating its invariants.

        This is useful for tests and future command/snapshot implementations;
        it intentionally performs no serialization.
        """
        new_rows = [list(row) for row in rows]
        if any(not row for row in new_rows):
            raise ValueError("Layout rows cannot be empty")
        if any(len(row) > self.max_columns for row in new_rows):
            raise ValueError("A layout row exceeds the column limit")
        flattened = [item for row in new_rows for item in row]
        if len({id(item) for item in flattened}) != len(flattened):
            raise ValueError("An item can only occur once in a layout")
        self._rows = new_rows

    def _insert(
            self,
            item: T,
            *,
            target: T | None,
            placement: DockPlacement,
    ):
        if target is None:
            self._rows.append([item])
            return

        position = self.position_of(target)
        if position is None:
            raise ValueError("The placement target does not belong to this layout")
        if placement == DockPlacement.LEFT:
            self._rows[position.row].insert(position.column, item)
        elif placement == DockPlacement.RIGHT:
            self._rows[position.row].insert(position.column + 1, item)
        elif placement == DockPlacement.ABOVE:
            self._rows.insert(position.row, [item])
        elif placement == DockPlacement.BELOW:
            self._rows.insert(position.row + 1, [item])
        else:
            raise ValueError(f"Unsupported target placement: {placement}")

    @staticmethod
    def _identity_signature(
            rows: Iterable[Iterable[T]],
    ) -> tuple[tuple[int, ...], ...]:
        return tuple(
            tuple(id(item) for item in row)
            for row in rows
        )
