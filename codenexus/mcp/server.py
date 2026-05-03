from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from codenexus.graph.session import SessionManager
from codenexus.graph.store import GraphStore
from codenexus.mcp.tools import session as session_tools
from codenexus.mcp.tools import structural


def create_mcp_server(store: GraphStore, repo_root: str) -> Server:
    """Create and configure the MCP server with all tools."""
    server = Server("codenexus")
    session_manager = SessionManager(store)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="search_nodes",
                description="Search for nodes (functions, classes, symbols) by name or file path.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "node_type": {
                            "type": "string",
                            "enum": ["file", "class", "function", "module", "symbol"],
                        },
                        "language": {"type": "string"},
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="get_node_signature",
                description="Get detailed metadata and a code snippet for a specific node.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string"},
                        "snippet_lines": {"type": "integer", "default": 10},
                    },
                    "required": ["node_id"],
                },
            ),
            Tool(
                name="get_downstream_dependencies",
                description="Find all nodes that depend on (import or call) this node.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string"},
                        "depth": {"type": "integer", "default": 3},
                    },
                    "required": ["node_id"],
                },
            ),
            Tool(
                name="get_upstream_callers",
                description="Find all nodes that this node depends on or calls.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string"},
                        "depth": {"type": "integer", "default": 3},
                    },
                    "required": ["node_id"],
                },
            ),
            Tool(
                name="get_agent_session_history",
                description="Get the history of actions for the current agent session.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                    },
                    "required": ["session_id"],
                },
            ),
            Tool(
                name="record_agent_action",
                description="Record an action taken by the agent (e.g., 'inspected', 'modified').",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "action": {"type": "string"},
                        "node_id": {"type": "string"},
                        "metadata": {"type": "object"},
                    },
                    "required": ["session_id", "action"],
                },
            ),
            Tool(
                name="create_session",
                description="Create a new agent session and return the session_id.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            if name == "search_nodes":
                result = structural.search_nodes(
                    store,
                    query=arguments["query"],
                    node_type=arguments.get("node_type"),
                    language=arguments.get("language"),
                )
            elif name == "get_node_signature":
                result = structural.get_node_signature(
                    store,
                    repo_root,
                    node_id=arguments["node_id"],
                    snippet_lines=arguments.get("snippet_lines", 10),
                )
            elif name == "get_downstream_dependencies":
                result = structural.get_downstream_dependencies(
                    store,
                    node_id=arguments["node_id"],
                    depth=arguments.get("depth", 3),
                )
            elif name == "get_upstream_callers":
                result = structural.get_upstream_callers(
                    store,
                    node_id=arguments["node_id"],
                    depth=arguments.get("depth", 3),
                )
            elif name == "get_agent_session_history":
                result = session_tools.get_agent_session_history(
                    session_manager, session_id=arguments["session_id"]
                )
            elif name == "record_agent_action":
                result = session_tools.record_agent_action(
                    session_manager,
                    session_id=arguments["session_id"],
                    action=arguments["action"],
                    node_id=arguments.get("node_id"),
                    metadata=arguments.get("metadata"),
                )
            elif name == "create_session":
                session_id = session_manager.create_session(repo_root)
                result = {"session_id": session_id}
            else:
                raise ValueError(f"Unknown tool: {name}")

            import json

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    return server


async def run_stdio_server(store: GraphStore, repo_root: str):
    """Run the MCP server over stdio."""
    server = create_mcp_server(store, repo_root)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
