from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import tree_sitter_python as tspython
import tree_sitter_rust as tsrust
import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

from codenexus.graph.schema import Edge, Node

from .languages.python import PythonParser
from .languages.rust import RustParser
from .languages.typescript import TypeScriptParser

if TYPE_CHECKING:
    from .languages.base import BaseLanguageParser

_MAX_FILE_BYTES = 500 * 1024  # 500 KB

_PY_PARSER = Parser(Language(tspython.language()))
_TS_PARSER = Parser(Language(tsts.language_typescript()))
_TSX_PARSER = Parser(Language(tsts.language_tsx()))
_RS_PARSER = Parser(Language(tsrust.language()))

_PY_EXTRACTOR = PythonParser()
_TS_EXTRACTOR = TypeScriptParser(tsx=False)
_TSX_EXTRACTOR = TypeScriptParser(tsx=True)
_RS_EXTRACTOR = RustParser()

# extension → (tree-sitter Parser, language extractor)
LANGUAGE_PARSERS: dict[str, tuple[Parser, BaseLanguageParser]] = {
    ".py": (_PY_PARSER, _PY_EXTRACTOR),
    ".pyi": (_PY_PARSER, _PY_EXTRACTOR),
    ".ts": (_TS_PARSER, _TS_EXTRACTOR),
    ".mts": (_TS_PARSER, _TS_EXTRACTOR),
    ".cts": (_TS_PARSER, _TS_EXTRACTOR),
    ".tsx": (_TSX_PARSER, _TSX_EXTRACTOR),
    ".js": (_TS_PARSER, _TS_EXTRACTOR),
    ".mjs": (_TS_PARSER, _TS_EXTRACTOR),
    ".cjs": (_TS_PARSER, _TS_EXTRACTOR),
    ".jsx": (_TSX_PARSER, _TSX_EXTRACTOR),
    ".rs": (_RS_PARSER, _RS_EXTRACTOR),
}


def parse_file(file_path: str, repo_root: str) -> tuple[list[Node], list[Edge]] | None:
    """Parse a single source file and return its nodes and edges.

    Returns None if the file is unsupported, too large, or unreadable.
    """
    ext = Path(file_path).suffix.lower()
    entry = LANGUAGE_PARSERS.get(ext)
    if entry is None:
        return None

    try:
        size = os.path.getsize(file_path)
    except OSError:
        return None

    if size > _MAX_FILE_BYTES:
        return None

    try:
        with open(file_path, "rb") as fh:
            source = fh.read()
    except OSError:
        return None

    ts_parser, extractor = entry
    tree = ts_parser.parse(source)
    return extractor.extract_nodes_and_edges(tree, file_path, repo_root)
