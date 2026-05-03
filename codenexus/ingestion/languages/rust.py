from __future__ import annotations

from pathlib import Path

import tree_sitter_rust as tsrust
from tree_sitter import Language, Query, QueryCursor, Tree

from codenexus.graph.schema import Edge, EdgeType, Node, NodeType, make_node_id

from .base import BaseLanguageParser

_LANGUAGE = Language(tsrust.language())

_CALL_QUERY = Query(
    _LANGUAGE,
    "(call_expression function: [(identifier) @fn"
    " (field_expression field: (field_identifier) @fn)"
    " (scoped_identifier name: (identifier) @fn)])",
)


def _use_path_segments(node) -> list[str]:
    """Recursively extract module path segments from a use_declaration child."""
    if node.type == "identifier":
        return [node.text.decode()]
    if node.type == "crate":
        return ["crate"]
    if node.type == "super":
        return ["super"]
    if node.type == "self":
        return ["self"]
    if node.type == "scoped_identifier":
        parts = []
        for c in node.children:
            if c.type != "::":
                parts.extend(_use_path_segments(c))
        return parts
    if node.type == "scoped_use_list":
        # Take the scoped prefix (ignore the brace list — multiple targets)
        for c in node.children:
            if c.type not in ("::", "use_list"):
                return _use_path_segments(c)
    return []


def _resolve_use_path(
    segments: list[str], file_path: str, repo_root: str
) -> str | None:
    if not segments:
        return None

    root = Path(repo_root)

    if segments[0] == "crate":
        src_dir = root / "src"
        if not src_dir.exists():
            src_dir = root
        module_parts = segments[1:]
    elif segments[0] == "super":
        src_dir = Path(file_path).parent.parent
        module_parts = segments[1:]
    elif segments[0] == "self":
        src_dir = Path(file_path).parent
        module_parts = segments[1:]
    else:
        return None

    if not module_parts:
        return None

    # The last segment(s) may be symbol names rather than module names.
    # Try progressively shorter module paths until one resolves to a file.
    for length in range(len(module_parts), 0, -1):
        parts = module_parts[:length]
        candidate = src_dir.joinpath(*parts)
        if candidate.with_suffix(".rs").exists():
            return str(candidate.with_suffix(".rs"))
        if (candidate / "mod.rs").exists():
            return str(candidate / "mod.rs")

    return None


def _call_names_in(node) -> list[str]:
    cursor = QueryCursor(_CALL_QUERY)
    caps = cursor.captures(node)
    return [n.text.decode() for n in caps.get("fn", [])]


def _is_pub(node) -> bool:
    for child in node.children:
        if child.type == "visibility_modifier":
            return True
    return False


def _name_field(node) -> str | None:
    for child in node.children:
        if child.type in ("identifier", "type_identifier"):
            return child.text.decode()
    return None


class RustParser(BaseLanguageParser):
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
                language="rust",
            )
        )

        root = tree.root_node
        func_ids: dict[str, str] = {}

        for child in root.children:
            if child.type == "function_item":
                name = _name_field(child)
                if name is None:
                    continue
                node_id = make_node_id(repo_root, file_path, name)
                func_ids[name] = node_id
                nodes.append(
                    Node(
                        id=node_id,
                        type=NodeType.FUNCTION,
                        name=name,
                        file_path=file_path,
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        language="rust",
                        metadata={"pub": _is_pub(child)},
                    )
                )
                edges.append(
                    Edge(source_id=file_id, target_id=node_id, type=EdgeType.CONTAINS)
                )

            elif child.type in ("struct_item", "enum_item"):
                name = _name_field(child)
                if name is None:
                    continue
                node_id = make_node_id(repo_root, file_path, name)
                nodes.append(
                    Node(
                        id=node_id,
                        type=NodeType.CLASS,
                        name=name,
                        file_path=file_path,
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        language="rust",
                        metadata={"kind": child.type[:-5], "pub": _is_pub(child)},
                    )
                )
                edges.append(
                    Edge(source_id=file_id, target_id=node_id, type=EdgeType.CONTAINS)
                )

            elif child.type == "const_item":
                name = _name_field(child)
                if name is None:
                    continue
                node_id = make_node_id(repo_root, file_path, name)
                nodes.append(
                    Node(
                        id=node_id,
                        type=NodeType.SYMBOL,
                        name=name,
                        file_path=file_path,
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        language="rust",
                        metadata={"pub": _is_pub(child)},
                    )
                )
                edges.append(
                    Edge(source_id=file_id, target_id=node_id, type=EdgeType.CONTAINS)
                )

            elif child.type == "impl_item":
                # Methods in impl blocks: register as functions of the file
                decl_list = child.child_by_field_name("body")
                if decl_list is None:
                    continue
                impl_type = child.child_by_field_name("type")
                type_name = impl_type.text.decode() if impl_type else ""
                for item in decl_list.children:
                    if item.type == "function_item":
                        method_name = _name_field(item)
                        if method_name is None:
                            continue
                        qualified = (
                            f"{type_name}::{method_name}" if type_name else method_name
                        )
                        node_id = make_node_id(repo_root, file_path, qualified)
                        func_ids[method_name] = node_id
                        func_ids[qualified] = node_id
                        nodes.append(
                            Node(
                                id=node_id,
                                type=NodeType.FUNCTION,
                                name=qualified,
                                file_path=file_path,
                                start_line=item.start_point[0] + 1,
                                end_line=item.end_point[0] + 1,
                                language="rust",
                                metadata={"pub": _is_pub(item)},
                            )
                        )
                        edges.append(
                            Edge(
                                source_id=file_id,
                                target_id=node_id,
                                type=EdgeType.CONTAINS,
                            )
                        )
                        # inherits-like: impl attaches to the struct
                        struct_id = make_node_id(repo_root, file_path, type_name)
                        edges.append(
                            Edge(
                                source_id=struct_id,
                                target_id=node_id,
                                type=EdgeType.CONTAINS,
                            )
                        )

            elif child.type == "use_declaration":
                segments: list[str] = []
                for c in child.children:
                    if c.type not in ("use", ";"):
                        segments = _use_path_segments(c)
                        break
                resolved = _resolve_use_path(segments, file_path, repo_root)
                if resolved:
                    target_id = make_node_id(repo_root, resolved, "")
                    edges.append(
                        Edge(
                            source_id=file_id,
                            target_id=target_id,
                            type=EdgeType.IMPORTS,
                        )
                    )

        # Intra-file calls
        for child in root.children:
            if child.type == "function_item":
                name = _name_field(child)
                caller_id = func_ids.get(name) if name else None
                if caller_id is None:
                    continue
                body = child.child_by_field_name("body")
                if body is None:
                    continue
                for callee_name in _call_names_in(body):
                    callee_id = func_ids.get(callee_name)
                    if callee_id and callee_id != caller_id:
                        edges.append(
                            Edge(
                                source_id=caller_id,
                                target_id=callee_id,
                                type=EdgeType.CALLS,
                            )
                        )

        return nodes, edges
