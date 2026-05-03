from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from repo_lens.api.websocket import manager
from repo_lens.graph.store import GraphStore
from repo_lens.ingestion.parser import LANGUAGE_PARSERS

logger = logging.getLogger(__name__)


class GraphWatcher(FileSystemEventHandler):
    def __init__(
        self, store: GraphStore, repo_root: str, loop: asyncio.AbstractEventLoop
    ) -> None:
        super().__init__()
        self._store = store
        self._repo_root = repo_root
        self._loop = loop

    def _is_supported(self, path: str) -> bool:
        return Path(path).suffix.lower() in LANGUAGE_PARSERS

    def _reparse(self, path: str) -> None:
        from repo_lens.ingestion.parser import parse_file

        self._store.delete_nodes_by_file(path)
        result = parse_file(path, self._repo_root)
        if result:
            nodes, edges = result
            for node in nodes:
                self._store.add_node(node)
            for edge in edges:
                try:
                    self._store.add_edge(edge)
                except ValueError:
                    pass  # endpoint deleted in same batch — skip dangling edge

        asyncio.run_coroutine_threadsafe(
            manager.broadcast({"type": "file_updated", "file_path": path}),
            self._loop,
        )

    def _handle_delete(self, path: str) -> None:
        self._store.delete_nodes_by_file(path)
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({"type": "file_deleted", "file_path": path}),
            self._loop,
        )

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._is_supported(str(event.src_path)):
            logger.debug("Watcher: modified %s", event.src_path)
            self._reparse(str(event.src_path))

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._is_supported(str(event.src_path)):
            logger.debug("Watcher: created %s", event.src_path)
            self._reparse(str(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._is_supported(str(event.src_path)):
            logger.debug("Watcher: deleted %s", event.src_path)
            self._handle_delete(str(event.src_path))


def start_watcher(
    store: GraphStore, repo_root: str, loop: asyncio.AbstractEventLoop
) -> Observer:
    handler = GraphWatcher(store, repo_root, loop)
    observer = Observer()
    observer.schedule(handler, path=repo_root, recursive=True)
    observer.start()
    logger.info("File watcher started for: %s", repo_root)
    return observer
