from __future__ import annotations

from copy import deepcopy
from types import MappingProxyType
from typing import Callable, ClassVar, Dict, Iterable, List, Mapping, Optional

from .object_dict import ObjectDict, Path, LocationTree
from .process_graph import ProcessGraph


class PreferenceService:
    """Manage process graphs and object locations as Gemini tool functions."""

    _FUNCTION_REGISTRY: ClassVar[List[Dict[str, object]]] = [
        {
            "method": "tool_list_process_graphs",
            "declaration": {
                "name": "list_process_graphs",
                "description": "Enumerates every known process graph with their steps and transitions.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "method": "tool_create_process_graph",
            "declaration": {
                "name": "create_process_graph",
                "description": "Creates a fresh process graph that the assistant can populate with steps.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Unique name for the new process graph.",
                        }
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "method": "tool_delete_process_graph",
            "declaration": {
                "name": "delete_process_graph",
                "description": "Deletes a process graph that is no longer needed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the process graph to delete.",
                        }
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "method": "tool_add_process_step",
            "declaration": {
                "name": "add_process_step",
                "description": "Adds a labeled step to an existing process graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "graph_name": {
                            "type": "string",
                            "description": "Name of the process graph.",
                        },
                        "step": {
                            "type": "string",
                            "description": "Unique identifier for the step.",
                        },
                    },
                    "required": ["graph_name", "step"],
                },
            },
        },
        {
            "method": "tool_update_process_step",
            "declaration": {
                "name": "update_process_step",
                "description": "Renames an existing step within a process graph without affecting its edges.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "graph_name": {
                            "type": "string",
                            "description": "Name of the process graph.",
                        },
                        "old_step": {
                            "type": "string",
                            "description": "Current name of the step.",
                        },
                        "new_step": {
                            "type": "string",
                            "description": "Replacement step name.",
                        },
                    },
                    "required": ["graph_name", "old_step", "new_step"],
                },
            },
        },
        {
            "method": "tool_add_process_transition",
            "declaration": {
                "name": "add_process_transition",
                "description": "Creates a directional edge from one step to another.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "graph_name": {
                            "type": "string",
                            "description": "Name of the process graph.",
                        },
                        "start": {
                            "type": "string",
                            "description": "Origin step name.",
                        },
                        "end": {
                            "type": "string",
                            "description": "Destination step name.",
                        },
                    },
                    "required": ["graph_name", "start", "end"],
                },
            },
        },
        {
            "method": "tool_remove_process_transition",
            "declaration": {
                "name": "remove_process_transition",
                "description": "Deletes a directional edge between two process steps.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "graph_name": {
                            "type": "string",
                            "description": "Name of the process graph.",
                        },
                        "start": {
                            "type": "string",
                            "description": "Origin step name.",
                        },
                        "end": {
                            "type": "string",
                            "description": "Destination step name.",
                        },
                    },
                    "required": ["graph_name", "start", "end"],
                },
            },
        },
        {
            "method": "tool_list_object_locations",
            "declaration": {
                "name": "list_object_locations",
                "description": "Returns every known object location or narrows to a specific item.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "object_name": {
                            "type": "string",
                            "description": "Optional object identifier to filter results.",
                        }
                    },
                    "required": [],
                },
            },
        },
        {
            "method": "tool_add_object",
            "declaration": {
                "name": "add_object",
                "description": "Stores an object at a precise location path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Hierarchical path (e.g. ['Kitchen','Drawers','Top']).",
                        },
                        "object_name": {
                            "type": "string",
                            "description": "Identifier for the stored object.",
                        },
                        "allow_duplicates": {
                            "type": "boolean",
                            "description": "Set true to keep duplicates within the same bucket.",
                        },
                    },
                    "required": ["path", "object_name"],
                },
            },
        },
        {
            "method": "tool_move_object",
            "declaration": {
                "name": "move_object",
                "description": "Moves an object to a different location path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "object_name": {
                            "type": "string",
                            "description": "Identifier of the object to move.",
                        },
                        "new_path": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Destination path for the object.",
                        },
                        "old_path": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional source path when multiple copies exist.",
                        },
                        "allow_duplicates": {
                            "type": "boolean",
                            "description": "Set true to retain the object at both paths.",
                        },
                    },
                    "required": ["object_name", "new_path"],
                },
            },
        },
        {
            "method": "tool_delete_path",
            "declaration": {
                "name": "delete_path",
                "description": "Removes a location bucket entirely and prunes empty parents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Hierarchical path to delete.",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
    ]

    def __init__(
        self,
        *,
        initial_process_graphs: Optional[Iterable[ProcessGraph]] = None,
        initial_object_locations: Optional[LocationTree] = None,
    ) -> None:
        self._graphs: Dict[str, ProcessGraph] = {}
        if initial_process_graphs:
            for graph in initial_process_graphs:
                self._graphs[graph.name] = graph
        self._object_dict = ObjectDict(initial_object_locations or {})

    @property
    def process_graphs(self) -> Mapping[str, ProcessGraph]:
        """Expose a read-only view of managed process graphs."""
        return MappingProxyType(self._graphs)

    @property
    def object_locations(self) -> LocationTree:
        """Return a snapshot of the object location hierarchy."""
        return self._object_dict.as_dict()

    @property
    def toolkit(self) -> List[Callable[..., Dict[str, object]]]:
        """Return callables that can be passed to google.genai tool configs."""
        return [getattr(self, spec["method"]) for spec in self._FUNCTION_REGISTRY]

    @property
    def function_declarations(self) -> List[Dict[str, object]]:
        """Return OpenAPI-style JSON declarations for every tool."""
        return [deepcopy(spec["declaration"]) for spec in self._FUNCTION_REGISTRY]

    def get_tool_callable(self, function_name: str) -> Callable[..., Dict[str, object]]:
        """Resolve a function declaration name to the concrete method."""
        for spec in self._FUNCTION_REGISTRY:
            declaration = spec["declaration"]
            if declaration["name"] == function_name:
                return getattr(self, spec["method"])
        raise KeyError(f"Unknown tool declaration: {function_name}")

    # ----------------------------- Process Graphs ----------------------------- #
    def tool_list_process_graphs(self) -> Dict[str, object]:
        """List every process graph so Gemini can choose the right one."""
        graphs = [self._graph_snapshot(graph) for graph in self._graphs.values()]
        return self._success(graphs=graphs)

    def tool_create_process_graph(self, name: str) -> Dict[str, object]:
        """Create an empty process graph."""
        if name in self._graphs:
            return self._error(f"Graph {name!r} already exists.")
        graph = ProcessGraph(name)
        self._graphs[name] = graph
        return self._success(graph=self._graph_snapshot(graph))

    def tool_delete_process_graph(self, name: str) -> Dict[str, object]:
        """Delete a process graph that is no longer needed."""
        graph = self._graphs.pop(name, None)
        if not graph:
            return self._error(f"Graph {name!r} was not found.")
        return self._success(message=f"Graph {name} deleted.")

    def tool_add_process_step(self, graph_name: str, step: str) -> Dict[str, object]:
        """Add a step node to a graph."""
        graph = self._graphs.get(graph_name)
        if not graph:
            return self._error(f"Graph {graph_name!r} was not found.")
        graph.add_step(step)
        return self._success(graph=self._graph_snapshot(graph))

    def tool_update_process_step(
        self, graph_name: str, old_step: str, new_step: str
    ) -> Dict[str, object]:
        """Rename a step without dropping edges."""
        graph = self._graphs.get(graph_name)
        if not graph:
            return self._error(f"Graph {graph_name!r} was not found.")
        graph.update_step(old_step, new_step)
        return self._success(graph=self._graph_snapshot(graph))

    def tool_add_process_transition(
        self, graph_name: str, start: str, end: str
    ) -> Dict[str, object]:
        """Create a directional edge between two steps."""
        graph = self._graphs.get(graph_name)
        if not graph:
            return self._error(f"Graph {graph_name!r} was not found.")
        graph.add_transition(start, end)
        return self._success(graph=self._graph_snapshot(graph))

    def tool_remove_process_transition(
        self, graph_name: str, start: str, end: str
    ) -> Dict[str, object]:
        """Remove a directional edge between two steps."""
        graph = self._graphs.get(graph_name)
        if not graph:
            return self._error(f"Graph {graph_name!r} was not found.")
        graph.remove_transition(start, end)
        return self._success(graph=self._graph_snapshot(graph))

    # ------------------------------ Object Dict ------------------------------ #
    def tool_list_object_locations(self, object_name: Optional[str] = None) -> Dict[str, object]:
        """List all object locations or filter by a specific object."""
        if object_name:
            path = self._object_dict.find_object(object_name)
            if path is None:
                return self._error(f"{object_name!r} was not found.")
            return self._success(locations=[self._serialize_path(path)])
        mapping = {
            name: [self._serialize_path(path) for path in paths]
            for name, paths in self._object_dict.list_objects().items()
        }
        return self._success(locations=mapping)

    def tool_add_object(
        self, path: List[str], object_name: str, allow_duplicates: bool = False
    ) -> Dict[str, object]:
        """Add an object to the specified location path."""
        added = self._object_dict.add_object(path, object_name, allow_duplicates=allow_duplicates)
        if not added:
            return self._error(f"{object_name!r} already exists at {path}.")
        return self._success(object=object_name, path=path)

    def tool_move_object(
        self,
        object_name: str,
        new_path: List[str],
        old_path: Optional[List[str]] = None,
        allow_duplicates: bool = False,
    ) -> Dict[str, object]:
        """Move an object to a different location."""
        moved = self._object_dict.move_object(
            object_name, new_path, old_path=old_path, allow_duplicates=allow_duplicates
        )
        if not moved:
            return self._error(f"Unable to move {object_name!r}.")
        return self._success(object=object_name, new_path=new_path)

    def tool_delete_path(self, path: List[str]) -> Dict[str, object]:
        """Delete a path and clean up empty parents."""
        deleted = self._object_dict.delete_path(path)
        if not deleted:
            return self._error(f"Path {path} does not exist.")
        return self._success(message=f"Removed path {path}.")

    # ------------------------------ Helpers ------------------------------ #
    def _graph_snapshot(self, graph: ProcessGraph) -> Dict[str, object]:
        steps = sorted(graph.steps)
        transitions: List[Dict[str, str]] = []
        for step in steps:
            for successor in graph.successors(step):
                transitions.append({"from": step, "to": successor})
        return {"name": graph.name, "steps": steps, "transitions": transitions}

    @staticmethod
    def _serialize_path(path: Path) -> List[str]:
        return list(path)

    @staticmethod
    def _success(**payload: object) -> Dict[str, object]:
        return {"status": "success", **payload}

    @staticmethod
    def _error(message: str, **payload: object) -> Dict[str, object]:
        return {"status": "error", "message": message, **payload}
