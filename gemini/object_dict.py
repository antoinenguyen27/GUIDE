from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import (
    Deque,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Sequence,
    Tuple,
    Union,
)

LocationValue = Union["LocationTree", List[str]]
LocationTree = Dict[str, LocationValue]
Path = Tuple[str, ...]


class ObjectDict:
    """Utility wrapper that keeps track of objects inside a nested dictionary.

    The structure is tailored for storing locations such as rooms, furniture,
    and storage zones. Each path resolves to either a nested dictionary or a
    terminal list that contains the concrete object identifiers.
    """

    def __init__(
        self, initial: Optional[Mapping[str, LocationValue]] = None, *, path_separator: str = "/"
    ) -> None:
        if not path_separator:
            raise ValueError("path_separator must be a non-empty string")
        self._data: LocationTree = deepcopy(initial) if initial else {}
        self._sep = path_separator

    def as_dict(self) -> LocationTree:
        """Return a deep copy of the stored data."""
        return deepcopy(self._data)

    def clear(self) -> None:
        """Remove every entry from the dictionary."""
        self._data.clear()

    def has_path(self, path: Sequence[str] | str) -> bool:
        """Return True when the provided path exists."""
        try:
            self._walk(self._normalize_path(path))
        except KeyError:
            return False
        return True

    def get_path(self, path: Sequence[str] | str, default: Optional[LocationValue] = None) -> LocationValue | None:
        """Return the value at path or the provided default."""
        normalized = self._normalize_path(path)
        try:
            return self._walk(normalized)
        except KeyError:
            return default

    def delete_path(self, path: Sequence[str] | str) -> bool:
        """Delete the node at path, cascading cleanup of empty parents."""
        normalized = self._normalize_path(path)
        parents: List[Tuple[LocationTree, str]] = []
        current: LocationValue = self._data
        for key in normalized[:-1]:
            if not isinstance(current, MutableMapping) or key not in current:
                return False
            parents.append((current, key))
            current = current[key]

        if not isinstance(current, MutableMapping):
            return False
        target_key = normalized[-1]
        if target_key not in current:
            return False
        current.pop(target_key)

        # Clean up empty parent branches
        for parent, key in reversed(parents):
            child = parent.get(key)
            if child is None:
                continue
            if isinstance(child, MutableMapping) and not child:
                parent.pop(key)
            elif isinstance(child, list) and not child:
                parent.pop(key)
            else:
                break
        return True

    def add_object(
        self, path: Sequence[str] | str, object_name: str, *, allow_duplicates: bool = False
    ) -> bool:
        """Insert object_name into the list located at path."""
        bucket = self._ensure_bucket(path)
        if not allow_duplicates and object_name in bucket:
            return False
        bucket.append(object_name)
        return True

    def extend_objects(
        self, path: Sequence[str] | str, object_names: Iterable[str], *, allow_duplicates: bool = False
    ) -> int:
        """Add several objects to the same bucket. Returns the number of new insertions."""
        bucket = self._ensure_bucket(path)
        inserted = 0
        for name in object_names:
            if not allow_duplicates and name in bucket:
                continue
            bucket.append(name)
            inserted += 1
        return inserted

    def remove_object(self, object_name: str, path: Sequence[str] | str | None = None) -> bool:
        """Remove the object either from the provided bucket or from the first match."""
        if path is not None:
            try:
                bucket = self._ensure_bucket(path, create=False)
            except KeyError:
                return False
            try:
                bucket.remove(object_name)
            except ValueError:
                return False
            self._prune_empty_branch(path)
            return True

        match = self.find_object(object_name)
        if match is None:
            return False
        bucket = self._ensure_bucket(match, create=False)
        bucket.remove(object_name)
        self._prune_empty_branch(match)
        return True

    def move_object(
        self,
        object_name: str,
        new_path: Sequence[str] | str,
        *,
        old_path: Sequence[str] | str | None = None,
        allow_duplicates: bool = False,
    ) -> bool:
        """Move object_name to a new path."""
        if old_path is not None:
            removed = self.remove_object(object_name, old_path)
        else:
            removed = self.remove_object(object_name)
        if not removed:
            return False
        self.add_object(new_path, object_name, allow_duplicates=allow_duplicates)
        return True

    def find_object(self, object_name: str) -> Optional[Path]:
        """Return the first path containing object_name or None."""
        for name, path in self.iter_object_paths():
            if name == object_name:
                return path
        return None

    def list_objects(self) -> Dict[str, List[Path]]:
        """Return mapping of object name -> list of paths."""
        result: Dict[str, List[Path]] = {}
        for name, path in self.iter_object_paths():
            result.setdefault(name, []).append(path)
        return result

    def iter_object_paths(self) -> Iterator[Tuple[str, Path]]:
        """Yield each object along with the path to its bucket."""
        yield from self._iter_objects(self._data, ())

    def _normalize_path(self, path: Sequence[str] | str) -> Path:
        if isinstance(path, str):
            parts = tuple(filter(None, path.split(self._sep)))
        else:
            parts = tuple(path)
        if not parts:
            raise ValueError("path must contain at least one segment")
        return parts

    def _walk(self, path: Path) -> LocationValue:
        current: LocationValue = self._data
        for key in path:
            if not isinstance(current, MutableMapping) or key not in current:
                raise KeyError("path does not exist")
            current = current[key]
        return current

    def _ensure_bucket(self, path: Sequence[str] | str | Path, *, create: bool = True) -> MutableSequence[str]:
        normalized = self._normalize_path(path)
        parent: LocationValue = self._data
        for key in normalized[:-1]:
            if not isinstance(parent, MutableMapping):
                raise TypeError(f"Cannot descend into non-mapping node at {key!r}")
            parent = parent.setdefault(key, {}) if create else parent[key]
        if not isinstance(parent, MutableMapping):
            raise TypeError("Bucket parent must be a mapping")
        bucket = parent.get(normalized[-1])
        if bucket is None:
            if not create:
                raise KeyError("bucket does not exist")
            parent[normalized[-1]] = []
            bucket = parent[normalized[-1]]
        if not isinstance(bucket, list):
            raise TypeError(f"Path {'/'.join(normalized)} does not resolve to a list bucket")
        return bucket

    def _prune_empty_branch(self, path: Sequence[str] | str | Path) -> None:
        normalized = self._normalize_path(path)
        parents: Deque[Tuple[LocationTree, str]] = deque()
        current: LocationValue = self._data
        for key in normalized[:-1]:
            if not isinstance(current, MutableMapping) or key not in current:
                return
            parents.append((current, key))
            current = current[key]

        if not isinstance(current, MutableMapping):
            return
        leaf = current.get(normalized[-1])
        if isinstance(leaf, list) and not leaf:
            current.pop(normalized[-1], None)

        while parents:
            parent, key = parents.pop()
            child = parent.get(key)
            if isinstance(child, MutableMapping) and not child:
                parent.pop(key, None)
            elif isinstance(child, list) and not child:
                parent.pop(key, None)
            else:
                break

    def _iter_objects(self, node: LocationValue, path: Path) -> Iterator[Tuple[str, Path]]:
        if isinstance(node, list):
            for obj in node:
                yield obj, path
            return
        if isinstance(node, MutableMapping):
            for key, child in node.items():
                yield from self._iter_objects(child, path + (key,))
            return
        raise TypeError(f"Unsupported node type: {type(node)!r}")
