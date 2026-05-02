from __future__ import annotations

from abc import ABC, abstractmethod

from tree_sitter import Tree

from repo_lens.graph.schema import Edge, Node


class BaseLanguageParser(ABC):
    @abstractmethod
    def extract_nodes_and_edges(
        self, tree: Tree, file_path: str, repo_root: str
    ) -> tuple[list[Node], list[Edge]]: ...
