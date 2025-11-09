from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Set


class ProcessGraph:
    """Directed process graph with string-labeled steps."""

    def __init__(self, name: str) -> None:
        self.name: str = name
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)

    @property
    def steps(self) -> Iterable[str]:
        return self._adjacency.keys()

    def add_step(self, step: str) -> None:
        if step not in self._adjacency:
            self._adjacency[step] = set()

    def remove_step(self, step: str) -> None:
        if step in self._adjacency:
            self._adjacency.pop(step)
            for neighbors in self._adjacency.values():
                neighbors.discard(step)


    def update_step(self, old_step: str, new_step: str) -> None:
        if old_step == new_step or old_step not in self._adjacency:
            return

        self.add_step(new_step)

        # Outgoing edges
        successors = self._adjacency.pop(old_step)
        self._adjacency[new_step].update(successors - {new_step})

        # Incoming edges
        for neighbors in self._adjacency.values():
            if old_step in neighbors:
                neighbors.discard(old_step)
                if new_step != neighbors:
                    neighbors.add(new_step)
                    
    def add_transition(self, start: str, end: str) -> None:
        self.add_step(start)
        self.add_step(end)
        self._adjacency[start].add(end)

    def remove_transition(self, start: str, end: str) -> None:
        if start in self._adjacency:
            self._adjacency[start].discard(end)

    def successors(self, step: str) -> List[str]:
        return sorted(self._adjacency.get(step, set()))

    def predecessors(self, step: str) -> List[str]:
        return sorted(
            node for node, neighbors in self._adjacency.items() if step in neighbors
        )

    def print_graph(self) -> str:
        return str(self)

    def __str__(self) -> str:
        lines = [f"ProcessGraph(name={self.name!r})"]
        for step in sorted(self._adjacency):
            successors = ", ".join(sorted(self._adjacency[step])) or "-"
            lines.append(f"  {step} -> {successors}")
        return "\n".join(lines)
