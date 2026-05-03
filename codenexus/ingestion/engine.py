import logging
import multiprocessing
import os
import time
from pathlib import Path

from codenexus.graph.schema import Edge, Node
from codenexus.graph.store import GraphStore
from codenexus.ingestion.git_overlay import apply_git_overlay
from codenexus.ingestion.parser import parse_file
from codenexus.plugins.loader import PluginManager

logger = logging.getLogger(__name__)

# Constants
IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv"}
MAX_FILE_BYTES = 500 * 1024  # 500 KB


def _parse_worker(
    args: tuple[str, str],
) -> tuple[str, tuple[list[Node], list[Edge]] | None]:
    """Top-level worker function for multiprocessing.

    Args:
        args: A tuple of (file_path, repo_root).

    Returns:
        A tuple of (file_path, parser_result).
    """
    file_path, repo_root = args
    try:
        result = parse_file(file_path, repo_root)
        return file_path, result
    except Exception as e:
        logger.error(f"Error parsing {file_path}: {e}")
        return file_path, None


class IngestionEngine:
    """Orchestrates the ingestion pipeline.

    Walks files, parses them in parallel, populates the GraphStore, and runs plugins.
    """

    def __init__(self, repo_root: str | Path, db_path: str | Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.db_path = Path(db_path).resolve()
        self.plugins = PluginManager(self.repo_root / ".codenexus" / "plugins")

    def _setup_index_table(self, store: GraphStore) -> None:
        store._db.execute("""
            CREATE TABLE IF NOT EXISTS file_index (
                file_path TEXT PRIMARY KEY,
                last_modified REAL
            );
            """)
        store._db.commit()

    def _get_indexed_mtimes(self, store: GraphStore) -> dict[str, float]:
        rows = store._db.execute("SELECT file_path, last_modified FROM file_index").fetchall()
        return {row["file_path"]: row["last_modified"] for row in rows}

    def _update_indexed_mtime(self, store: GraphStore, file_path: str, mtime: float) -> None:
        store._db.execute(
            "INSERT OR REPLACE INTO file_index (file_path, last_modified) VALUES (?, ?)",
            (file_path, mtime),
        )

    def _walk_files(self) -> list[str]:
        """Finds all parsable files in the repo."""
        found = []
        for root, dirs, files in os.walk(self.repo_root):
            # Skip ignored directories and hidden directories
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]

            for file in files:
                if file.startswith("."):
                    continue
                file_path = Path(root) / file

                try:
                    size = file_path.stat().st_size
                    if size > MAX_FILE_BYTES:
                        continue
                    found.append(str(file_path))
                except OSError:
                    pass
        return found

    def run(
        self,
        workers: int = 4,
        full_reindex: bool = False,
        git_granularity: str = "file",
    ) -> None:
        """Run the full ingestion pipeline."""
        logger.info(f"Starting ingestion for {self.repo_root}")
        start_time = time.time()

        files_to_parse = []
        current_mtimes: dict[str, float] = {}

        all_files = self._walk_files()
        deleted_files = set()

        with GraphStore(self.db_path) as store:
            self._setup_index_table(store)
            indexed_mtimes = self._get_indexed_mtimes(store) if not full_reindex else {}

            for f_path in all_files:
                try:
                    mtime = os.path.getmtime(f_path)
                    current_mtimes[f_path] = mtime

                    if (
                        full_reindex
                        or f_path not in indexed_mtimes
                        or indexed_mtimes[f_path] < mtime
                    ):
                        files_to_parse.append(f_path)
                except OSError:
                    continue

            # Identify deleted files
            if not full_reindex:
                all_files_set = set(all_files)
                deleted_files = set(indexed_mtimes.keys()) - all_files_set
                for f_path in deleted_files:
                    logger.debug(f"Removing deleted file from graph: {f_path}")
                    store.delete_nodes_by_file(f_path)
                    store._db.execute("DELETE FROM file_index WHERE file_path = ?", (f_path,))

                if deleted_files:
                    store._db.commit()

            if not files_to_parse and not deleted_files and not full_reindex:
                logger.info("Graph is up to date. No files to parse.")
                self.plugins.trigger_on_graph_ready(store)
                return

            if files_to_parse:
                logger.info(f"Parsing {len(files_to_parse)} files using {workers} workers...")
                worker_args = [(f, str(self.repo_root)) for f in files_to_parse]

                all_edges: list[Edge] = []

                # We use imap_unordered to process files as soon as they finish parsing
                with multiprocessing.Pool(processes=workers) as pool:
                    for file_path, result in pool.imap_unordered(_parse_worker, worker_args):
                        if result is not None:
                            # Clear old nodes for this file before inserting new ones
                            if not full_reindex and file_path in indexed_mtimes:
                                store.delete_nodes_by_file(file_path)

                            nodes, edges = result
                            for node in nodes:
                                node = self.plugins.trigger_on_node_created(node)
                                store.add_node(node)

                            all_edges.extend(edges)

                        # Update the mtime index even if result is None (unsupported extension)
                        # to prevent retrying every time.
                        if file_path in current_mtimes:
                            self._update_indexed_mtime(store, file_path, current_mtimes[file_path])

                # Now add all edges since all parsed nodes have been added
                for edge in all_edges:
                    try:
                        store.add_edge(edge)
                    except ValueError as e:
                        # Some edges (like imports) might point to unparsed or external files
                        logger.debug(f"Skipping edge {edge.source_id}->{edge.target_id}: {e}")

                store._db.commit()

            # Apply Git history if requested
            if full_reindex:
                apply_git_overlay(str(self.repo_root), store, granularity=git_granularity)

            self.plugins.trigger_on_graph_ready(store)

        logger.info(f"Ingestion complete in {time.time() - start_time:.2f}s.")
