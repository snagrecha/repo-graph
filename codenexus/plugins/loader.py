import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Any

from codenexus.graph.schema import Node
from codenexus.graph.store import GraphStore
from .base import RepoGraphPlugin

logger = logging.getLogger(__name__)


class PluginManager:
    """Discovers, loads, and executes plugins."""

    def __init__(self, plugins_dir: str | Path | None = None) -> None:
        self.plugins: list[RepoGraphPlugin] = []
        if plugins_dir:
            self.load_plugins(Path(plugins_dir))

    def load_plugins(self, plugins_dir: Path) -> None:
        """Dynamically load all Python files in the given directory as plugins."""
        if not plugins_dir.exists() or not plugins_dir.is_dir():
            return

        for py_file in plugins_dir.glob("*.py"):
            if py_file.name in ("__init__.py", "base.py", "loader.py"):
                continue

            try:
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find all subclasses of RepoGraphPlugin in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, RepoGraphPlugin) and obj is not RepoGraphPlugin:
                        self.plugins.append(obj())
                        logger.debug(f"Loaded plugin: {obj.__name__} from {py_file.name}")
            except Exception as e:
                logger.error(f"Failed to load plugin from {py_file.name}: {e}")

    def trigger_on_node_created(self, node: Node) -> Node:
        """Run all plugins' on_node_created hooks."""
        for plugin in self.plugins:
            try:
                node = plugin.on_node_created(node)
            except Exception as e:
                logger.error(
                    f"Plugin {plugin.__class__.__name__} failed in on_node_created: {e}"
                )
        return node

    def trigger_on_graph_ready(self, store: GraphStore) -> None:
        """Run all plugins' on_graph_ready hooks."""
        for plugin in self.plugins:
            try:
                plugin.on_graph_ready(store)
            except Exception as e:
                logger.error(
                    f"Plugin {plugin.__class__.__name__} failed in on_graph_ready: {e}"
                )
