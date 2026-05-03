from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from codenexus.graph.session import SessionManager
from codenexus.graph.store import GraphStore
from codenexus.mcp.tools import context as context_tools
from codenexus.mcp.tools import session as session_tools
from codenexus.mcp.tools import structural, temporal


def create_mcp_server(store: GraphStore, repo_root: str) -> Server:
    """Create and configure the MCP server with all tools."""
    server = Server("codenexus")
    session_manager = SessionManager(store)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="search_nodes",
                description=(
                    "Search for nodes (functions, classes, interfaces, types, symbols) "
                    "by name substring. Also searches file paths, so "
                    "'search_nodes(query=\"utils\")' will match files whose path contains "
                    "'utils'. Use the optional file_path filter to narrow results to a "
                    "specific file or directory."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Substring to match against node name or file path",
                        },
                        "node_type": {
                            "type": "string",
                            "enum": [
                                "file",
                                "class",
                                "function",
                                "module",
                                "symbol",
                                "interface",
                                "type_alias",
                            ],
                            "description": "Optional: restrict to this node type",
                        },
                        "language": {
                            "type": "string",
                            "description": (
                                "Optional: restrict to this language "
                                "(e.g. 'typescript', 'python')"
                            ),
                        },
                        "file_path": {
                            "type": "string",
                            "description": (
                                "Optional: restrict results to nodes whose "
                                "file path contains this substring"
                            ),
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="get_file_symbols",
                description=(
                    "List all symbols (functions, classes, interfaces, types, etc.) "
                    "defined in a specific file. Use this to orient yourself in a file "
                    "before reading its source. The file_path should match the path as "
                    "returned by search_nodes."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": (
                                "Relative file path as stored in the graph "
                                "(e.g. 'src/components/page.tsx')"
                            ),
                        },
                    },
                    "required": ["file_path"],
                },
            ),
            Tool(
                name="get_node_signature",
                description=(
                    "Get detailed metadata and the full source code of a specific node. "
                    "Returns the complete function/class/interface body using the node's "
                    "start_line and end_line. "
                    "snippet_lines is only used as a fallback when end_line is unknown."
                ),
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
                description=(
                    "Find all nodes that the given node calls or imports — "
                    "i.e. its outgoing dependencies. "
                    "Use this to answer 'what does X depend on?' or 'what does X call?'. "
                    "For the reverse ('what calls X?'), use get_upstream_callers."
                ),
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
                description=(
                    "Find all nodes that call or import the given node — "
                    "i.e. its callers/consumers. "
                    "Use this to answer 'what uses X?' or 'what imports X?'. "
                    "For the reverse ('what does X depend on?'), use get_downstream_dependencies."
                ),
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
                name="search_field_usages",
                description=(
                    "Find all functions and components that access a specific field or "
                    "property name. Answers questions like 'where is the certifications "
                    "field rendered?' or 'which functions use the advisor_id property?'. "
                    "Returns each matching node with the exact line numbers where the "
                    "field is accessed."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "field_name": {
                            "type": "string",
                            "description": (
                                "The field/property name to search for " "(e.g. 'certifications')"
                            ),
                        },
                        "language": {
                            "type": "string",
                            "description": "Optional: restrict to 'typescript' or 'python'",
                        },
                    },
                    "required": ["field_name"],
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
            Tool(
                name="get_node_history",
                description=(
                    "Retrieve the git commit history for a specific node. "
                    "Returns commits that modified the file containing the node, "
                    "including author, timestamp, and message."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["node_id"],
                },
            ),
            Tool(
                name="get_graph_at_commit",
                description=(
                    "Return the full graph state as it existed after a specific commit SHA. "
                    "Useful for time-travel queries or understanding historical architecture."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "commit_sha": {"type": "string"},
                    },
                    "required": ["commit_sha"],
                },
            ),
            Tool(
                name="get_narrowed_context",
                description=(
                    "Request a minimised code context focused on a specific node and goal. "
                    "Returns the most relevant 1-hop neighbours and their source snippets, "
                    "greedily packed up to a token budget. Fully deterministic — "
                    "no LLM call inside."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string"},
                        "goal": {"type": "string"},
                        "max_tokens": {"type": "integer", "default": 8000},
                    },
                    "required": ["node_id", "goal"],
                },
            ),
            Tool(
                name="get_blast_radius_report",
                description=(
                    "Return an enriched blast radius for a node with risk scores per "
                    "affected node. Risk is based on git churn, dependency fan-out, "
                    "and proximity to the target."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string"},
                    },
                    "required": ["node_id"],
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
                    file_path=arguments.get("file_path"),
                )
            elif name == "get_file_symbols":
                result = structural.get_file_symbols(
                    store,
                    file_path=arguments["file_path"],
                )
            elif name == "search_field_usages":
                result = structural.search_field_usages(
                    store,
                    field_name=arguments["field_name"],
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
            elif name == "get_node_history":
                result = temporal.get_node_history_tool(
                    store,
                    node_id=arguments["node_id"],
                    limit=arguments.get("limit", 10),
                )
            elif name == "get_graph_at_commit":
                result = temporal.get_graph_at_commit_tool(
                    store,
                    commit_sha=arguments["commit_sha"],
                )
            elif name == "get_narrowed_context":
                result = context_tools.get_narrowed_context(
                    store,
                    repo_root=repo_root,
                    node_id=arguments["node_id"],
                    goal=arguments["goal"],
                    max_tokens=arguments.get("max_tokens", 8000),
                )
            elif name == "get_blast_radius_report":
                result = structural.get_blast_radius_report(
                    store,
                    node_id=arguments["node_id"],
                )
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
