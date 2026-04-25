from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    MODULE = "module"
    SYMBOL = "symbol"


class EdgeType(str, Enum):
    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"
    CONTAINS = "contains"
    CO_CHANGES_WITH = "co_changes_with"


@dataclass
class Node:
    id: str
    type: NodeType
    name: str
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    source_id: str
    target_id: str
    type: EdgeType
    metadata: dict[str, Any] = field(default_factory=dict)


def make_node_id(repo_root: str, file_path: str, symbol_name: str) -> str:
    """Return a stable SHA-256 hex digest for a node.

    Inputs are joined with null bytes so that ("a", "bc", "d") != ("a", "b", "cd").
    """
    raw = f"{repo_root}\x00{file_path}\x00{symbol_name}"
    return hashlib.sha256(raw.encode()).hexdigest()
