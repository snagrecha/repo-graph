from __future__ import annotations

from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Query, QueryCursor, Tree

from codenexus.graph.schema import Edge, EdgeType, Node, NodeType, make_node_id

from .base import BaseLanguageParser

_LANGUAGE = Language(tspython.language())

_CALL_QUERY = Query(
    _LANGUAGE,
    "(call function: [(identifier) @fn (attribute attribute: (identifier) @fn)])",
)

_ATTR_QUERY = Query(
    _LANGUAGE,
    "(attribute attribute: (identifier) @attr)",
)


def _resolve_relative_import(file_path: str, dots: int, module: str, repo_root: str) -> str | None:
    base_dir = Path(file_path).parent
    for _ in range(dots - 1):
        base_dir = base_dir.parent

    if module:
        parts = module.split(".")
        candidate = base_dir.joinpath(*parts)
        if candidate.with_suffix(".py").exists():
            return str(candidate.with_suffix(".py"))
        if (candidate / "__init__.py").exists():
            return str(candidate / "__init__.py")
    else:
        init = base_dir / "__init__.py"
        if init.exists():
            return str(init)

    return None


def _call_names_in(node, language: Language) -> list[str]:
    cursor = QueryCursor(_CALL_QUERY)
    caps = cursor.captures(node)
    return [n.text.decode() for n in caps.get("fn", [])]


def _attr_accesses_in(node) -> list[tuple[str, int]]:
    """Return (attribute_name, 1-based line number) for every attribute access in the subtree."""
    cursor = QueryCursor(_ATTR_QUERY)
    caps = cursor.captures(node)
    return [(n.text.decode(), n.start_point[0] + 1) for n in caps.get("attr", [])]


def _unwrap_decorated(node) -> object | None:
    """Return the inner function_definition or class_definition, or None."""
    if node.type != "decorated_definition":
        return None
    for child in node.children:
        if child.type in ("function_definition", "class_definition"):
            return child
    return None


class PythonParser(BaseLanguageParser):
    def extract_nodes_and_edges(
        self, tree: Tree, file_path: str, repo_root: str
    ) -> tuple[list[Node], list[Edge]]:
        nodes: list[Node] = []
        edges: list[Edge] = []

        file_id = make_node_id(repo_root, file_path, "")
        nodes.append(
            Node(
                id=file_id,
                type=NodeType.FILE,
                name=Path(file_path).name,
                file_path=file_path,
                start_line=1,
                end_line=tree.root_node.end_point[0] + 1,
                language="python",
            )
        )

        root = tree.root_node

        # First pass — collect definitions so call resolution works.
        func_ids: dict[str, str] = {}  # symbol name → node_id
        func_nodes: dict[str, Node] = {}  # symbol name → Node, for metadata updates

        for child in root.children:
            inner = _unwrap_decorated(child) or child

            if inner.type == "function_definition":
                name_node = inner.child_by_field_name("name")
                if name_node is None:
                    continue
                name = name_node.text.decode()
                node_id = make_node_id(repo_root, file_path, name)
                func_ids[name] = node_id
                fn_node = Node(
                    id=node_id,
                    type=NodeType.FUNCTION,
                    name=name,
                    file_path=file_path,
                    start_line=inner.start_point[0] + 1,
                    end_line=inner.end_point[0] + 1,
                    language="python",
                )
                func_nodes[name] = fn_node
                nodes.append(fn_node)
                edges.append(Edge(source_id=file_id, target_id=node_id, type=EdgeType.CONTAINS))

            elif inner.type == "class_definition":
                name_node = inner.child_by_field_name("name")
                if name_node is None:
                    continue
                name = name_node.text.decode()
                node_id = make_node_id(repo_root, file_path, name)
                nodes.append(
                    Node(
                        id=node_id,
                        type=NodeType.CLASS,
                        name=name,
                        file_path=file_path,
                        start_line=inner.start_point[0] + 1,
                        end_line=inner.end_point[0] + 1,
                        language="python",
                    )
                )
                edges.append(Edge(source_id=file_id, target_id=node_id, type=EdgeType.CONTAINS))

                # inherits edges (resolved within the same file only)
                supers = inner.child_by_field_name("superclasses")
                if supers:
                    for sc in supers.children:
                        if sc.type == "identifier":
                            sc_name = sc.text.decode()
                            sc_id = make_node_id(repo_root, file_path, sc_name)
                            edges.append(
                                Edge(
                                    source_id=node_id,
                                    target_id=sc_id,
                                    type=EdgeType.INHERITS,
                                )
                            )

            elif inner.type == "expression_statement":
                # Module-level UPPER_CASE assignments → symbol nodes.
                assign = None
                for c in inner.children:
                    if c.type == "assignment":
                        assign = c
                        break
                if assign is None:
                    continue
                lhs = assign.child_by_field_name("left")
                if lhs is None or lhs.type != "identifier":
                    continue
                name = lhs.text.decode()
                if not name.isupper() or name.startswith("_"):
                    continue
                node_id = make_node_id(repo_root, file_path, name)
                nodes.append(
                    Node(
                        id=node_id,
                        type=NodeType.SYMBOL,
                        name=name,
                        file_path=file_path,
                        start_line=inner.start_point[0] + 1,
                        end_line=inner.end_point[0] + 1,
                        language="python",
                    )
                )
                edges.append(Edge(source_id=file_id, target_id=node_id, type=EdgeType.CONTAINS))

        # Second pass — imports and intra-file calls.
        for child in root.children:
            if child.type == "import_from_statement":
                relative_dots = 0
                module_name = ""
                for c in child.children:
                    if c.type == "relative_import":
                        for rc in c.children:
                            if rc.type == "import_prefix":
                                relative_dots = rc.text.decode().count(".")
                            elif rc.type == "dotted_name":
                                module_name = rc.text.decode()

                if relative_dots > 0:
                    resolved = _resolve_relative_import(
                        file_path, relative_dots, module_name, repo_root
                    )
                    if resolved:
                        target_id = make_node_id(repo_root, resolved, "")
                        edges.append(
                            Edge(
                                source_id=file_id,
                                target_id=target_id,
                                type=EdgeType.IMPORTS,
                            )
                        )

            elif child.type in ("function_definition",) or (child.type == "decorated_definition"):
                inner = _unwrap_decorated(child) or child
                if inner.type != "function_definition":
                    continue
                name_node = inner.child_by_field_name("name")
                if name_node is None:
                    continue
                caller_name = name_node.text.decode()
                caller_id = func_ids.get(caller_name)
                if caller_id is None:
                    continue
                body = inner.child_by_field_name("body")
                if body is None:
                    continue

                # Intra-file function call edges
                for callee_name in _call_names_in(body, _LANGUAGE):
                    callee_id = func_ids.get(callee_name)
                    if callee_id and callee_id != caller_id:
                        edges.append(
                            Edge(
                                source_id=caller_id,
                                target_id=callee_id,
                                type=EdgeType.CALLS,
                            )
                        )

                # Attribute-access field tracking — store in node metadata for search_field_usages
                fn_node = func_nodes.get(caller_name)
                if fn_node is not None:
                    field_map: dict[str, list[int]] = {}
                    for attr_name, line_num in _attr_accesses_in(body):
                        field_map.setdefault(attr_name, [])
                        if line_num not in field_map[attr_name]:
                            field_map[attr_name].append(line_num)
                    if field_map:
                        fn_node.metadata["accessed_fields"] = field_map

        return nodes, edges
