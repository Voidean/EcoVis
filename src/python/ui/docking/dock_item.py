"""Minimal identity contract for content managed by the docking model."""

from typing import Protocol


class DockItem(Protocol):
    """Opaque content known to docking only through its runtime identity."""

    instance_id: int
