from abc import ABC

from repo_lens.graph.schema import Node
from repo_lens.graph.store import GraphStore


class RepoGraphPlugin(ABC):
    """Base class for all repo-lens plugins."""

    def on_node_created(self, node: Node) -> Node:
        """Called when a node is created or parsed.
        
        The plugin can modify the node's metadata before it is written to the database.
        Returns the modified node.
        """
        return node

    def on_graph_ready(self, store: GraphStore) -> None:
        """Called when the entire ingestion pipeline is complete and the graph is ready.
        
        The plugin can execute queries, add edges, or run external integrations.
        """
        pass
