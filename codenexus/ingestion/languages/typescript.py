from __future__ import annotations

from pathlib import Path

import tree_sitter_typescript as tsts
from tree_sitter import Language, Query, QueryCursor, Tree

from codenexus.graph.schema import Edge, EdgeType, Node, NodeType, make_node_id

from .base import BaseLanguageParser

_LANGUAGE_TS = Language(tsts.language_typescript())
_LANGUAGE_TSX = Language(tsts.language_tsx())

_CALL_QUERY_TS = Query(
    _LANGUAGE_TS,
    "(call_expression function: [(identifier) @fn"
    " (member_expression property: (property_identifier) @fn)])",
)
_CALL_QUERY_TSX = Query(
    _LANGUAGE_TSX,
    "(call_expression function: [(identifier) @fn"
    " (member_expression property: (property_identifier) @fn)])",
)

_MEMBER_QUERY_TS = Query(
    _LANGUAGE_TS,
    "(member_expression property: (property_identifier) @prop)",
)
_MEMBER_QUERY_TSX = Query(
    _LANGUAGE_TSX,
    "(member_expression property: (property_identifier) @prop)",
)

# Only meaningful for TSX: captures the component name in <Component /> and <Component>
_JSX_QUERY_TSX = Query(
    _LANGUAGE_TSX,
    "(jsx_opening_element name: (identifier) @component)"
    " (jsx_self_closing_element name: (identifier) @component)",
)

_TS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mts", ".cts")


def _resolve_relative_import(file_path: str, module_spec: str, repo_root: str) -> str | None:
    base_dir = Path(file_path).parent
    candidate = (base_dir / module_spec).resolve()
    # Try exact path first (already has extension)
    if candidate.suffix in _TS_EXTENSIONS and candidate.exists():
        return str(candidate)
    # Try with each extension
    for ext in _TS_EXTENSIONS:
        with_ext = candidate.with_suffix(ext)
        if with_ext.exists():
            return str(with_ext)
    # Try as directory index
    for ext in _TS_EXTENSIONS:
        index = candidate / f"index{ext}"
        if index.exists():
            return str(index)
    return None


def _call_names_in(node, call_query: Query) -> list[str]:
    cursor = QueryCursor(call_query)
    caps = cursor.captures(node)
    return [n.text.decode() for n in caps.get("fn", [])]


def _member_accesses_in(node, member_query: Query) -> list[tuple[str, int]]:
    """Return (property_name, 1-based line number) for every member access in the subtree."""
    cursor = QueryCursor(member_query)
    caps = cursor.captures(node)
    return [(n.text.decode(), n.start_point[0] + 1) for n in caps.get("prop", [])]


def _jsx_components_in(node, jsx_query: Query) -> list[str]:
    """Return PascalCase component names referenced via JSX in the subtree."""
    cursor = QueryCursor(jsx_query)
    caps = cursor.captures(node)
    return [
        n.text.decode()
        for n in caps.get("component", [])
        if n.text and n.text.decode()[:1].isupper()
    ]


def _extract_class_node(
    class_decl,
    file_path: str,
    repo_root: str,
    file_id: str,
) -> tuple[Node, list[Edge]]:
    name_node = class_decl.child_by_field_name("name")
    name = name_node.text.decode() if name_node else "<anonymous>"
    node_id = make_node_id(repo_root, file_path, name)
    node = Node(
        id=node_id,
        type=NodeType.CLASS,
        name=name,
        file_path=file_path,
        start_line=class_decl.start_point[0] + 1,
        end_line=class_decl.end_point[0] + 1,
        language="typescript",
    )
    inner_edges: list[Edge] = [Edge(source_id=file_id, target_id=node_id, type=EdgeType.CONTAINS)]
    # class_heritage has no field name; search by node type
    for sibling in class_decl.children:
        if sibling.type == "class_heritage":
            for clause in sibling.children:
                if clause.type == "extends_clause":
                    for c in clause.children:
                        if c.type == "identifier":
                            base_id = make_node_id(repo_root, file_path, c.text.decode())
                            inner_edges.append(
                                Edge(
                                    source_id=node_id,
                                    target_id=base_id,
                                    type=EdgeType.INHERITS,
                                )
                            )
    return node, inner_edges


class TypeScriptParser(BaseLanguageParser):
    def __init__(self, tsx: bool = False) -> None:
        self._tsx = tsx
        self._language = _LANGUAGE_TSX if tsx else _LANGUAGE_TS
        self._call_query = _CALL_QUERY_TSX if tsx else _CALL_QUERY_TS
        self._member_query = _MEMBER_QUERY_TSX if tsx else _MEMBER_QUERY_TS
        self._jsx_query = _JSX_QUERY_TSX if tsx else None

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
                language="typescript",
            )
        )

        root = tree.root_node
        func_ids: dict[str, str] = {}
        func_nodes: dict[str, Node] = {}  # name → Node, for metadata updates in second pass

        for child in root.children:
            # Unwrap export_statement
            inner = child
            if child.type == "export_statement":
                for c in child.children:
                    if c.type not in ("export", "default", ";"):
                        inner = c
                        break

            if inner.type == "function_declaration":
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
                    language="typescript",
                )
                func_nodes[name] = fn_node
                nodes.append(fn_node)
                edges.append(Edge(source_id=file_id, target_id=node_id, type=EdgeType.CONTAINS))

            elif inner.type == "class_declaration":
                node, class_edges = _extract_class_node(inner, file_path, repo_root, file_id)
                nodes.append(node)
                edges.extend(class_edges)

            elif inner.type == "lexical_declaration":
                for declarator in inner.children:
                    if declarator.type != "variable_declarator":
                        continue
                    name_node = declarator.child_by_field_name("name")
                    if name_node is None:
                        continue
                    name = name_node.text.decode()
                    if name.startswith("_"):
                        continue
                    value_node = declarator.child_by_field_name("value")
                    is_arrow = value_node is not None and value_node.type == "arrow_function"
                    if is_arrow:
                        node_id = make_node_id(repo_root, file_path, name)
                        func_ids[name] = node_id
                        fn_node = Node(
                            id=node_id,
                            type=NodeType.FUNCTION,
                            name=name,
                            file_path=file_path,
                            start_line=inner.start_point[0] + 1,
                            end_line=inner.end_point[0] + 1,
                            language="typescript",
                        )
                        func_nodes[name] = fn_node
                        nodes.append(fn_node)
                        edges.append(
                            Edge(
                                source_id=file_id,
                                target_id=node_id,
                                type=EdgeType.CONTAINS,
                            )
                        )
                    elif name.isupper():
                        node_id = make_node_id(repo_root, file_path, name)
                        nodes.append(
                            Node(
                                id=node_id,
                                type=NodeType.SYMBOL,
                                name=name,
                                file_path=file_path,
                                start_line=inner.start_point[0] + 1,
                                end_line=inner.end_point[0] + 1,
                                language="typescript",
                            )
                        )
                        edges.append(
                            Edge(
                                source_id=file_id,
                                target_id=node_id,
                                type=EdgeType.CONTAINS,
                            )
                        )
                    elif name[0].isupper():
                        # PascalCase non-arrow export const — React components
                        # wrapped in HOCs, styled-components, context objects, etc.
                        node_id = make_node_id(repo_root, file_path, name)
                        nodes.append(
                            Node(
                                id=node_id,
                                type=NodeType.SYMBOL,
                                name=name,
                                file_path=file_path,
                                start_line=inner.start_point[0] + 1,
                                end_line=inner.end_point[0] + 1,
                                language="typescript",
                            )
                        )
                        edges.append(
                            Edge(
                                source_id=file_id,
                                target_id=node_id,
                                type=EdgeType.CONTAINS,
                            )
                        )

            elif inner.type == "interface_declaration":
                name_node = inner.child_by_field_name("name")
                if name_node is not None:
                    name = name_node.text.decode()
                    node_id = make_node_id(repo_root, file_path, name)
                    nodes.append(
                        Node(
                            id=node_id,
                            type=NodeType.INTERFACE,
                            name=name,
                            file_path=file_path,
                            start_line=inner.start_point[0] + 1,
                            end_line=inner.end_point[0] + 1,
                            language="typescript",
                        )
                    )
                    edges.append(Edge(source_id=file_id, target_id=node_id, type=EdgeType.CONTAINS))

            elif inner.type == "type_alias_declaration":
                name_node = inner.child_by_field_name("name")
                if name_node is not None:
                    name = name_node.text.decode()
                    node_id = make_node_id(repo_root, file_path, name)
                    nodes.append(
                        Node(
                            id=node_id,
                            type=NodeType.TYPE_ALIAS,
                            name=name,
                            file_path=file_path,
                            start_line=inner.start_point[0] + 1,
                            end_line=inner.end_point[0] + 1,
                            language="typescript",
                        )
                    )
                    edges.append(Edge(source_id=file_id, target_id=node_id, type=EdgeType.CONTAINS))

            elif inner.type == "enum_declaration":
                name_node = inner.child_by_field_name("name")
                if name_node is not None:
                    name = name_node.text.decode()
                    node_id = make_node_id(repo_root, file_path, name)
                    nodes.append(
                        Node(
                            id=node_id,
                            type=NodeType.SYMBOL,
                            name=name,
                            file_path=file_path,
                            start_line=inner.start_point[0] + 1,
                            end_line=inner.end_point[0] + 1,
                            language="typescript",
                        )
                    )
                    edges.append(Edge(source_id=file_id, target_id=node_id, type=EdgeType.CONTAINS))

            elif child.type == "import_statement":
                # Find the string_fragment (module specifier)
                spec = _import_specifier(child)
                if spec and spec.startswith("."):
                    resolved = _resolve_relative_import(file_path, spec, repo_root)
                    if resolved:
                        target_id = make_node_id(repo_root, resolved, "")
                        edges.append(
                            Edge(
                                source_id=file_id,
                                target_id=target_id,
                                type=EdgeType.IMPORTS,
                            )
                        )

        # Second pass: intra-file calls, JSX component edges, and field-access metadata
        for child in root.children:
            inner = child
            if child.type == "export_statement":
                for c in child.children:
                    if c.type not in ("export", "default", ";"):
                        inner = c
                        break

            caller_name: str | None = None
            caller_id: str | None = None
            body = None

            if inner.type == "function_declaration":
                name_node = inner.child_by_field_name("name")
                if name_node:
                    caller_name = name_node.text.decode()
                    caller_id = func_ids.get(caller_name)
                body = inner.child_by_field_name("body")

            elif inner.type == "lexical_declaration":
                for declarator in inner.children:
                    if declarator.type != "variable_declarator":
                        continue
                    name_node = declarator.child_by_field_name("name")
                    value_node = declarator.child_by_field_name("value")
                    if name_node and value_node and value_node.type == "arrow_function":
                        caller_name = name_node.text.decode()
                        caller_id = func_ids.get(caller_name)
                        body = value_node.child_by_field_name("body")
                        break

            if caller_id is None or body is None:
                continue

            # Intra-file function call edges
            for callee_name in _call_names_in(body, self._call_query):
                callee_id = func_ids.get(callee_name)
                if callee_id and callee_id != caller_id:
                    edges.append(
                        Edge(source_id=caller_id, target_id=callee_id, type=EdgeType.CALLS)
                    )

            # JSX component edges (TSX only) — PascalCase JSX elements become CALLS edges
            if self._jsx_query is not None:
                for component_name in _jsx_components_in(body, self._jsx_query):
                    callee_id = func_ids.get(component_name)
                    if callee_id and callee_id != caller_id:
                        edges.append(
                            Edge(source_id=caller_id, target_id=callee_id, type=EdgeType.CALLS)
                        )

            # Member-access field tracking — store in node metadata for search_field_usages
            fn_node = func_nodes.get(caller_name) if caller_name else None
            if fn_node is not None:
                field_map: dict[str, list[int]] = {}
                for prop_name, line_num in _member_accesses_in(body, self._member_query):
                    field_map.setdefault(prop_name, [])
                    if line_num not in field_map[prop_name]:
                        field_map[prop_name].append(line_num)
                if field_map:
                    fn_node.metadata["accessed_fields"] = field_map

        return nodes, edges


def _import_specifier(import_stmt) -> str | None:
    for child in import_stmt.children:
        if child.type == "string":
            for c in child.children:
                if c.type == "string_fragment":
                    return c.text.decode()
    return None
