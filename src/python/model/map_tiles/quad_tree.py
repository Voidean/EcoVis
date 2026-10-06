from collections import deque
from typing import TypeVar, Generic, Callable

T = TypeVar("T")


class QuadTree(Generic[T]):
    def __init__(self, factory: Callable[[], T]):
        self.factory = factory
        self.root: QuadTreeNode[T] = QuadTreeNode[T](0, 0, 0, factory)

    def nodes(self):
        node_queue = deque([self.root])
        while node_queue:
            node = node_queue.popleft()
            yield node
            if not node.is_leaf: node_queue.extend(node.children)

    def leaves(self):
        node_queue = deque([self.root])
        while node_queue:
            node = node_queue.popleft()
            if node.is_leaf:
                yield node
            else:
                node_queue.extend(node.children)


class QuadTreeNode(Generic[T]):
    def __init__(self, column, row, level, factory: Callable[[], T]):
        self.column = column
        self.row = row
        self.level = level

        self.children = None

        self.factory = factory
        self.data: T = factory() if factory else None

    def subdivide(self):
        self.children = (
            QuadTreeNode(self.column * 2, self.row * 2, self.level + 1, self.factory),  # Top-Left
            QuadTreeNode(self.column * 2 + 1, self.row * 2, self.level + 1, self.factory),  # Top-Right
            QuadTreeNode(self.column * 2, self.row * 2 + 1, self.level + 1, self.factory),  # Bottom-Left
            QuadTreeNode(self.column * 2 + 1, self.row * 2 + 1, self.level + 1, self.factory),  # Bottom-Right
        )

    def make_leaf(self):
        self.children = None

    @property
    def is_leaf(self):
        return self.children is None

    @property
    def position(self):
        return self.column, self.row, self.level


def ancestor(node_pos, level_delta):
    column, row, level = node_pos
    if level_delta > level: raise IndexError
    return column >> level_delta, row >> level_delta, level - level_delta


def ancestors(node_pos):
    column, row, level = node_pos
    for level_delta in range(1, level + 1):
        yield (column >> level_delta, row >> level_delta, level - level_delta), level_delta


def children(node_pos):
    column, row, level = node_pos
    return [
        (column * 2, row * 2, level + 1),
        (column * 2 + 1, row * 2, level + 1),
        (column * 2, row * 2 + 1, level + 1),
        (column * 2 + 1, row * 2 + 1, level + 1)
    ]

ROOT_POS = (0, 0, 0)
