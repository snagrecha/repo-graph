import logging
import time
from collections import defaultdict
from pathlib import Path

from pydriller import Repository

from codenexus.graph.store import GraphStore
from codenexus.ingestion.diff_snapshot import generate_diff_snapshots

logger = logging.getLogger(__name__)


def apply_git_overlay(
    repo_root: str, store: GraphStore, granularity: str = "file", skip_snapshots: bool = False
) -> None:
    """Applies git history metadata to nodes in the GraphStore.

    By default (granularity='file'), it aggregates metrics per file path and applies
    them to all nodes within that file.

    Also generates per-commit diff snapshots (unless *skip_snapshots* is True).
    """
    logger.info("Starting git overlay (granularity=%s) for %s", granularity, repo_root)
    start_time = time.time()

    if granularity != "file":
        logger.warning("Granularity %s not fully implemented, falling back to 'file'", granularity)
        granularity = "file"

    file_churn: dict[str, int] = defaultdict(int)
    file_authors: dict[str, set[str]] = defaultdict(set)
    file_last_modified: dict[str, str] = {}

    repo_path = Path(repo_root).resolve()

    try:
        # Traverse all commits
        for commit in Repository(str(repo_path)).traverse_commits():
            author_name = commit.author.name
            commit_time = commit.committer_date.isoformat()

            for mod in commit.modified_files:
                # Use the new path if it exists, otherwise the old path (for deletions/renames)
                path = mod.new_path or mod.old_path
                if not path:
                    continue

                abs_path = str((repo_path / path).resolve())

                file_churn[abs_path] += 1
                if author_name:
                    file_authors[abs_path].add(author_name)
                # Since commits are yielded in chronological order by default,
                # the last one we see should be the most recent.
                file_last_modified[abs_path] = commit_time

    except Exception as exc:
        logger.error("Failed to extract git history: %s", exc)
        return

    # Now apply to the graph
    nodes = store.get_all_nodes()
    updates = 0
    for node in nodes:
        if node.file_path in file_churn:
            node.metadata["git_churn"] = file_churn[node.file_path]
            node.metadata["git_authors"] = list(file_authors[node.file_path])
            node.metadata["git_last_modified"] = file_last_modified[node.file_path]
            # Write it back to the store (upsert)
            store.add_node(node)
            updates += 1

    logger.info(
        "Git overlay complete in %.2fs. Updated %d nodes.", time.time() - start_time, updates
    )

    if not skip_snapshots:
        generate_diff_snapshots(repo_root, store)
