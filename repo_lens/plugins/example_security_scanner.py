import logging

from repo_graph.graph.schema import Node, NodeType
from repo_graph.graph.store import GraphStore
from repo_graph.plugins.base import RepoGraphPlugin

logger = logging.getLogger(__name__)


class ExampleSecurityScanner(RepoGraphPlugin):
    """An example plugin that flags functions for security scans.
    
    This demonstrates how to hook into the node creation process and modify metadata,
    and how to hook into the final graph ready event to run queries.
    """

    def on_node_created(self, node: Node) -> Node:
        if node.type == NodeType.FUNCTION:
            # A real scanner would check the function's source code here.
            # For this example, we just add a placeholder metadata flag.
            node.metadata["security_scan_status"] = "pending"
        return node

    def on_graph_ready(self, store: GraphStore) -> None:
        # Example query: find all functions and check if they need scanning
        logger.info(
            "ExampleSecurityScanner: Graph is ready. In a real scenario, this would run a full scan."
        )
