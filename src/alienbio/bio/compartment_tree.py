"""CompartmentTree: hierarchical topology of compartments."""

from __future__ import annotations

from typing import Dict, List, Optional

# Type alias
CompartmentId = int


class CompartmentTreeImpl:
    """Implementation: Hierarchical structure of compartments.

    Represents the tree topology of compartments (organism > organ > cell > organelle).
    Stored separately from concentrations to allow efficient structure updates.

    The tree is represented with:
    - parents: List[Optional[CompartmentId]] - parent[child] = parent_id or None for root
    - children: Dict[CompartmentId, List[CompartmentId]] - children by parent

    Compartments are identified by integer IDs (0, 1, 2, ...).

    Example:
        # Create tree: organism with two organs
        tree = CompartmentTreeImpl()
        organism = tree.add_root("organism")      # 0
        organ_a = tree.add_child(organism, "organ_a")  # 1
        organ_b = tree.add_child(organism, "organ_b")  # 2
        cell_1 = tree.add_child(organ_a, "cell_1")     # 3

        print(tree.parent(cell_1))    # 1 (organ_a)
        print(tree.children(organism))  # [1, 2]
    """

    __slots__ = ("_parents", "_children", "_names", "_root")

    def __init__(self) -> None:
        """Initialize empty compartment tree."""
        self._parents: List[Optional[CompartmentId]] = []
        self._children: Dict[CompartmentId, List[CompartmentId]] = {}
        self._names: List[str] = []
        self._root: Optional[CompartmentId] = None

    @property
    def num_compartments(self) -> int:
        """Total number of compartments."""
        return len(self._parents)

    def parent(self, child: CompartmentId) -> Optional[CompartmentId]:
        """Get parent of a compartment (None for root)."""
        return self._parents[child]

    def children(self, parent: CompartmentId) -> List[CompartmentId]:
        """Get children of a compartment."""
        return self._children.get(parent, [])

    def root(self) -> CompartmentId:
        """Get the root compartment."""
        if self._root is None:
            raise ValueError("Tree has no root")
        return self._root

    def is_root(self, compartment: CompartmentId) -> bool:
        """Check if compartment is the root."""
        return self._parents[compartment] is None

    def name(self, compartment: CompartmentId) -> str:
        """Get the name of a compartment."""
        return self._names[compartment]

    def add_root(self, name: str = "root") -> CompartmentId:
        """Add the root compartment.

        Args:
            name: Human-readable name for the root

        Returns:
            The root compartment ID (always 0)

        Raises:
            ValueError: If root already exists
        """
        if self._root is not None:
            raise ValueError("Root already exists")

        compartment_id = len(self._parents)
        self._parents.append(None)
        self._children[compartment_id] = []
        self._names.append(name)
        self._root = compartment_id
        return compartment_id

    def add_child(
        self, parent: CompartmentId, name: str = ""
    ) -> CompartmentId:
        """Add a child compartment.

        Args:
            parent: Parent compartment ID
            name: Human-readable name for the child

        Returns:
            The new compartment ID
        """
        if parent >= len(self._parents):
            raise ValueError(f"Parent {parent} does not exist")

        compartment_id = len(self._parents)
        if not name:
            name = f"compartment_{compartment_id}"

        self._parents.append(parent)
        self._children[compartment_id] = []
        self._children[parent].append(compartment_id)
        self._names.append(name)
        return compartment_id

    def ancestors(self, compartment: CompartmentId) -> List[CompartmentId]:
        """Get all ancestors from compartment to root (inclusive)."""
        result = []
        current: Optional[CompartmentId] = compartment
        while current is not None:
            result.append(current)
            current = self._parents[current]
        return result

    def descendants(self, compartment: CompartmentId) -> List[CompartmentId]:
        """Get all descendants of a compartment (not including self)."""
        result = []
        stack = list(self._children.get(compartment, []))
        while stack:
            child = stack.pop()
            result.append(child)
            stack.extend(self._children.get(child, []))
        return result

    def depth(self, compartment: CompartmentId) -> int:
        """Get depth of compartment (root = 0)."""
        d = 0
        current = self._parents[compartment]
        while current is not None:
            d += 1
            current = self._parents[current]
        return d

    def to_dict(self) -> Dict:
        """Serialize tree structure."""
        return {
            "parents": self._parents.copy(),
            "names": self._names.copy(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> CompartmentTreeImpl:
        """Deserialize tree structure."""
        tree = cls()
        tree._parents = data["parents"]
        tree._names = data["names"]

        # Rebuild children dict and find root
        for child, parent in enumerate(tree._parents):
            tree._children[child] = []
            if parent is None:
                tree._root = child

        for child, parent in enumerate(tree._parents):
            if parent is not None:
                tree._children[parent].append(child)

        return tree

    def __repr__(self) -> str:
        """Full representation."""
        return f"CompartmentTreeImpl(compartments={self.num_compartments})"

    def __str__(self) -> str:
        """Tree visualization."""
        if self._root is None:
            return "CompartmentTree(empty)"

        lines = []

        def _format(comp: CompartmentId, indent: str = "") -> None:
            lines.append(f"{indent}{self._names[comp]} ({comp})")
            children = self._children.get(comp, [])
            for i, child in enumerate(children):
                is_last = i == len(children) - 1
                prefix = "└── " if is_last else "├── "
                next_indent = indent + ("    " if is_last else "│   ")
                lines.append(f"{indent}{prefix}{self._names[child]} ({child})")
                for grandchild in self._children.get(child, []):
                    _format(grandchild, next_indent)

        _format(self._root)
        return "\n".join(lines)
