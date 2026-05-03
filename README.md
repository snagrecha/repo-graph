# code-nexus

> **Transform your codebase into a structured semantic knowledge graph for AI agents and developers.**

`code-nexus` is a local-first, open-source engine that parses your repository into a queryable knowledge graph with rich temporal context from Git history. It provides:

- **For AI Agents:** A Model Context Protocol (MCP) server that enables Claude Code and other AI tools to query your codebase structurally instead of via text search—reducing token usage by up to 80% on architectural queries.
- **For Developers:** An interactive, time-traveling visual map of your code that helps you understand blast radius, code ownership, and architectural dependencies.

## Features

✨ **AST-Powered Code Understanding**
- Parses Python, TypeScript/JavaScript, and Rust with `tree-sitter`
- Extracts files, classes, functions, and module-level symbols
- Identifies imports, function calls, and inheritance relationships

🔍 **AI Agent-First Design**
- MCP-compliant query tools: `search_nodes`, `get_node_signature`, `get_downstream_dependencies`, `get_upstream_callers`
- Context pruning engine: automatically filters non-essential code to minimize token usage
- Agent session persistence: track inspection history across restarts

⏱️ **Git-Integrated Temporal Context**
- Commit history overlay: tracks churn, ownership, and last-modified metadata per node
- Time-travel slider: visualize how your architecture evolved
- Diff-patch snapshots: efficiently replay historical graph states

📊 **Interactive Visualization**
- WebGL 3D graph rendering of up to 10,000 nodes at 60 FPS
- Blast radius highlighting: click a node to see everything that depends on it
- Analytical overlays: complexity heatmaps, churn scoring, ownership visualization

🔌 **Plugin System**
- Extend the graph with custom metadata via Python plugins
- Hook into node creation and graph-ready events
- Drop plugins into `plugins/` directory—no configuration needed

⚡ **Zero External Dependencies**
- Local SQLite storage (graph lives in `.codenexus/graph.db`)
- No network calls, no cloud services
- Single command to start: `code-nexus start .`

## Quick Start

### Installation

```bash
pip install code-nexus
```

Or use Docker:
```bash
docker run -v $(pwd):/repo code-nexus:latest code-nexus start /repo
```

### Usage

**For Developers (Interactive UI):**
```bash
cd your-repo
code-nexus start .
```
Opens `http://localhost:7842` in your browser.

**For AI Agents (MCP Server):**
```bash
cd your-repo
code-nexus mcp .
```
Configure your MCP client (e.g., Claude Code):
```json
{
  "mcpServers": {
    "code-nexus": {
      "command": "code-nexus",
      "args": ["mcp", "."]
    }
  }
}
```

**Sync with Latest Commits:**
```bash
code-nexus sync .
```
Re-runs the git overlay on an existing graph to pick up new commits without a full re-index.

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Parsing** | `tree-sitter` + Python | Industry-standard AST extraction, 70+ grammar support |
| **Graph Engine** | `rustworkx` (in-memory) | 3–100x faster than NetworkX for large graphs |
| **Persistence** | SQLite (WAL mode) | Zero external dependencies, portable, concurrent reads |
| **Agent Protocol** | MCP (Model Context Protocol) | Standard for AI agent tooling |
| **Frontend** | React + `react-force-graph-3d` | WebGL rendering for massive graphs |
| **API** | FastAPI + Uvicorn | Lightweight, production-ready |

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design, database schema, MCP tool specifications, and performance targets.

At a glance:
```
code-nexus start .
    ├─ Ingestion Engine (parallel AST parsing)
    │   └─ Outputs: rustworkx graph + SQLite persistence
    ├─ FastAPI Server
    │   ├─ MCP Server (stdio + HTTP/SSE)
    │   └─ REST/WebSocket API for UI
    ├─ React Frontend (3D graph visualization)
    └─ File Watcher (incremental updates)
```

## Performance Targets

| Metric | Target | Conditions |
|---|---|---|
| 100k LOC ingestion | < 30s | M1 Mac, 4 workers, SSD |
| 500k LOC ingestion | < 60s | M1 Mac, 4 workers, SSD |
| Incremental update | < 2s | Single file changed |
| MCP structural query | < 100ms | Graph in memory |
| Context pruning | < 500ms | Graph in memory |
| UI rendering | 60 FPS | 10,000 nodes, WebGL |
| Token reduction | > 80% | vs full-file injection |

## Available MCP Tools (Phase 1)

| Tool | Purpose |
|---|---|
| `search_nodes(query, type?, language?)` | Fuzzy search for nodes by name |
| `get_node_signature(node_id)` | Retrieve node metadata and location |
| `get_downstream_dependencies(node_id, depth?)` | Find all nodes that depend on this node |
| `get_upstream_callers(node_id, depth?)` | Find all nodes that this node depends on |
| `get_node_history(node_id, limit?)` | Get commit history for a node *(Phase 2)* |
| `get_agent_session_history(session_id)` | Retrieve prior agent actions in this session |
| `record_agent_action(session_id, node_id, action)` | Log agent inspection/modification for persistence |

## Roadmap

### Phase 1 (Alpha) — Core MCP Engine & UI
- ✅ AST parsing (Python, TypeScript, Rust)
- ✅ Parallel ingestion pipeline
- ✅ SQLite persistence
- ✅ 3D WebGL Graph UI with Blast Radius & Overlays
- ✅ MCP server (`stdio` transport)

### Phase 2 (Beta) — Temporal Intelligence
- 🔄 **Current**
- 🔲 Git overlay with diff-patch snapshots
- 🔲 Context pruning engine
- 🔲 Time-travel slider

### Phase 3 (v1.0) — Ecosystem
- 🔲 Plugin system launch
- 🔲 VS Code / JetBrains extensions
- 🔲 Cursor `contextProvider` adapter
- 🔲 GitHub Actions blast-radius reports
- 🔲 Anonymous telemetry (opt-in)

### Phase 4+ (Beyond)
- WASM plugin sandboxing
- Cross-repository dependency mapping
- GitHub/GitLab API enrichment

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Language parser development guide
- Plugin authoring guide
- Development setup
- Testing framework

## Privacy & Security

✅ **100% local processing.** No code, paths, or symbols leave your machine.

✅ **Zero external dependencies.** Graph storage is a single SQLite file inside your repo (`.codenexus/`).

⚠️ **Plugins are not sandboxed in Phase 1–3.** They run with the same OS permissions as code-nexus. WASM sandboxing is a Phase 4 goal. Only load plugins you trust.

## License

MIT License © 2026 Sneh Nagrecha

See [LICENSE](LICENSE) for details.

## Support

- 📖 [Architecture Guide](ARCHITECTURE.md)
- 📋 [Product Requirements](prd.md)
- 💬 [GitHub Issues](https://github.com/your-org/codenexus/issues)
- 🐳 Docker: `docker run -v $(pwd):/repo code-nexus:latest`

---

**Built with ❤️ to help AI and humans navigate code together.**