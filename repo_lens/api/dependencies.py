from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repo_lens.graph.store import GraphStore

_store: GraphStore | None = None
_repo_root: str = ""


def init_dependencies(store: GraphStore, repo_root: str) -> None:
    global _store, _repo_root
    _store = store
    _repo_root = repo_root


def get_store() -> GraphStore:
    if _store is None:
        raise RuntimeError("GraphStore not initialized — call init_dependencies first")
    return _store


def get_repo_root() -> str:
    return _repo_root
