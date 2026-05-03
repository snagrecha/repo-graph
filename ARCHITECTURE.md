# code-nexus Architecture

## 1. System Overview

code-nexus is structured as three loosely coupled subsystems that share a single local SQLite store:

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Entry Point                       │
│                    `code-nexus start .`                      │
└───────────────┬─────────────────────┬───────────────────────┘
                │                     │
                ▼                     ▼
┌──────────────────────┐   ┌─────────────────────────┐
│  Ingestion Engine    │   │     FastAPI Process      │
│  (Python, parallel)  │   │                          │
│                      │   │  ┌─────────────────────┐ │
│  tree-sitter parse   │   │  │   MCP Server        │ │
│  → rustworkx graph   │──▶│  │   (agent tools)     │ │
│  → SQLite persist    │   │  └─────────────────────┘ │
│  → git overlay       │   │  ┌─────────────────────┐ │
│  → diff snapshots    │   │  │   REST/WS API       │ │
└──────────────────────┘   │  │   (UI data layer)   │ │
                            │  └─────────────────────┘ │
                            └────────────┬────────────┘
                                         │
                            ┌────────────▼────────────┐
                            │   React Frontend         │
                            │   react-force-graph      │
                            │   (WebGL, Three.js)      │
                            └─────────────────────────┘
                                         │
                            ┌────────────▼────────────┐
                            │   SQLite Store           │
                            │   (shared, local)        │
                            └─────────────────────────┘
```

All three subsystems are started by a single `code-nexus start .` command. The ingestion engine runs once at startup (and on file-watch events), then exits. The FastAPI process stays alive serving both the MCP server and the UI API.

---

## 2. Repository Layout

```
codenexus/
├── codenexus/                  # Python package (backend)
│   ├── __main__.py              # CLI entry: `python -m code-nexus`
│   ├── cli.py                   # Click/Typer CLI commands
│   ├── ingestion/
│   │   ├── engine.py            # Orchestrates the full ingestion pipeline
│   │   ├── parser.py            # tree-sitter wrapper, per-file AST extraction
│   │   ├── worker.py            # multiprocessing worker (parses one file)
│   │   ├── git_overlay.py       # PyDriller: commit history → graph properties
│   │   ├── diff_snapshot.py     # Per-commit graph diff-patch generation
│   │   └── languages/           # Per-language node/edge extraction rules
│   │       ├── python.py
│   │       ├── typescript.py
│   │       └── rust.py
│   ├── graph/
│   │   ├── store.py             # rustworkx in-memory graph + SQLite persistence
│   │   ├── schema.py            # Node/Edge dataclasses and type enums
│   │   ├── queries.py           # Reusable graph traversal functions
│   │   └── session.py           # Agent session state (persisted in SQLite)
│   ├── mcp/
│   │   ├── server.py            # MCP tool registration and dispatch
│   │   └── tools/
│   │       ├── structural.py    # get_node_signature, get_downstream_dependencies, etc.
│   │       ├── temporal.py      # get_node_history, get_graph_at_commit
│   │       ├── context.py       # get_narrowed_context (context pruning engine)
│   │       └── session.py       # get_agent_session_history, record_agent_action
│   ├── api/
│   │   ├── app.py               # FastAPI app factory
│   │   ├── routes/
│   │   │   ├── graph.py         # GET /graph, GET /node/:id, GET /blast-radius/:id
│   │   │   ├── timeline.py      # GET /timeline, GET /graph-at/:commit_sha
│   │   │   └── overlays.py      # GET /overlay/complexity, /churn, /ownership
│   │   └── websocket.py         # Live file-watch push to UI
│   └── plugins/
│       ├── loader.py            # importlib-based plugin loading
│       └── base.py              # Plugin base class / interface
├── ui/                          # React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── GraphCanvas.tsx  # react-force-graph WebGL renderer
│   │   │   ├── TimeSlider.tsx   # Git timeline scrubber
│   │   │   ├── BlastRadius.tsx  # Highlight overlay on node click
│   │   │   ├── OverlayToggle.tsx
│   │   │   └── NodePanel.tsx    # Side panel: node details + history
│   │   ├── hooks/
│   │   │   ├── useGraph.ts      # Fetches and caches graph data
│   │   │   └── useTimeline.ts   # Timeline state + commit scrubbing
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── plugins/                     # Example/bundled plugins
│   └── example_security_scanner.py
├── tests/
│   ├── ingestion/
│   ├── mcp/
│   └── fixtures/                # Small synthetic repos for testing
├── Dockerfile
├── pyproject.toml
├── ARCHITECTURE.md              # This file
└── prd.md
```

---

## 3. Graph Schema

Every entity in the graph is a **Node** or an **Edge**. Both are stored in SQLite and loaded into rustworkx at startup.

### Node Types

```python
class NodeType(str, Enum):
    FILE       = "file"
    CLASS      = "class"
    FUNCTION   = "function"
    MODULE     = "module"       # top-level module/package
    SYMBOL     = "symbol"       # module-level exported constant/variable
```

### Node Properties

```python
@dataclass
class Node:
    id: str                     # stable hash: sha256(repo_root + file_path + symbol_name)
                                # NOTE: ID changes when a file is moved or a symbol is renamed.
                                # On incremental update, old nodes are deleted by file_path and
                                # new nodes are inserted with fresh IDs. Cross-references (edges)
                                # pointing to renamed nodes are also deleted and re-inserted.
    type: NodeType
    name: str
    file_path: str              # relative to repo root
    start_line: int
    end_line: int
    language: str
    # populated by git_overlay
    last_modified_commit: str
    last_modified_author: str
    churn_score: int            # number of commits touching this node
    primary_owner: str          # author with most commits
    # populated by complexity pass
    cyclomatic_complexity: int | None
```

### Edge Types

```python
class EdgeType(str, Enum):
    IMPORTS          = "imports"          # file → file
    CALLS            = "calls"            # function → function
    INHERITS         = "inherits"         # class → class
    CONTAINS         = "contains"         # file/class → function/class
    CO_CHANGES_WITH  = "co_changes_with"  # file ↔ file (git co-change analysis) — Phase 2 only
```

### Edge Properties

```python
@dataclass
class Edge:
    source_id: str
    target_id: str
    type: EdgeType
    weight: float               # for CO_CHANGES_WITH: co-change frequency (0–1)
```

---

## 4. SQLite Schema

Single file at `.codenexus/graph.db` inside the target repository. WAL mode is enabled on first open (`PRAGMA journal_mode=WAL`) to allow concurrent reads from the MCP server and UI API without blocking ingestion writes.

```sql
-- Core graph (rebuilt on full re-index, patched on incremental)
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    language TEXT,
    last_modified_commit TEXT,
    last_modified_author TEXT,
    churn_score INTEGER DEFAULT 0,
    primary_owner TEXT,
    cyclomatic_complexity INTEGER,
    extra_json TEXT            -- plugin-injected metadata
);

CREATE TABLE edges (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    type TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    PRIMARY KEY (source_id, target_id, type)
);

-- Git temporal overlay (written once during initial ingestion)
CREATE TABLE commit_snapshots (
    commit_sha TEXT NOT NULL,
    committed_at INTEGER NOT NULL,   -- unix timestamp
    author TEXT NOT NULL,
    message TEXT NOT NULL,
    diff_patch BLOB NOT NULL,        -- msgpack-serialised graph diff
    PRIMARY KEY (commit_sha)
);

-- Agent session state
CREATE TABLE agent_sessions (
    session_id TEXT NOT NULL,
    repo_root TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    last_active INTEGER NOT NULL,
    PRIMARY KEY (session_id)
);

CREATE TABLE agent_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    node_id TEXT,
    action TEXT NOT NULL,            -- "inspected" | "modified" | "queried"
    timestamp INTEGER NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id)
);
```

---

## 5. Ingestion Pipeline

### Startup sequence

```
code-nexus start .
    │
    ├─ 1. Check .codenexus/graph.db exists?
    │       YES → load existing graph into rustworkx, proceed to step 5
    │       NO  → full ingestion (steps 2–4)
    │
    ├─ 2. File discovery
    │       Walk repo, collect files matching language extensions
    │       Skip: .gitignore entries, >500KB files, binary files
    │
    ├─ 3. Parallel AST parsing  (multiprocessing, default 4 workers)
    │       Each worker: tree-sitter parse → extract nodes + edges → return list
    │       Main process: collect results, build rustworkx graph in batch
    │
    ├─ 4. Git overlay  (single-threaded, PyDriller)
    │       Walk commits oldest→newest
    │       For each commit: compute which nodes changed → update churn/owner/last_modified
    │       Generate diff-patch per commit → store in commit_snapshots table
    │
    ├─ 5. Persist graph to SQLite
    │
    ├─ 6. Start FastAPI server (MCP + UI API)
    │
    └─ 7. Start file watcher (watchdog)
            On change: incremental re-parse of changed file only → patch graph + SQLite
```

### Incremental update (file-watch event)

Only the changed file is re-parsed. Its old nodes and edges are removed from the graph (matched by `file_path`); new ones are inserted. The git overlay is not re-run on file-watch events.

### `code-nexus sync` command

Running `code-nexus sync .` explicitly re-runs the git overlay on an already-ingested graph (picks up new commits since last run) and regenerates diff-patch snapshots for new commits only. This is the only way to update temporal data between restarts without doing a full re-index.

---

## 6. MCP Server

**Transport by phase:**
- **Phase 1 (Alpha):** `stdio` transport only. The MCP server runs as a subprocess that Claude Code (or any MCP-compatible agent) spawns directly. No FastAPI dependency for the MCP path. Config snippet for Claude Code: `{"mcpServers": {"code-nexus": {"command": "code-nexus", "args": ["mcp", "."]}}}`.
- **Phase 2+ (Beta/v1.0):** Add `HTTP/SSE` transport, mounted on the FastAPI app at `/mcp`. Required for IDE extensions and CI/CD use cases where a subprocess model doesn't apply.

Both transports use the same underlying tool implementations — only the transport adapter differs.

### Agent workflow — node discovery

All tools that accept `node_id` require a stable node ID. The intended agent workflow is:

```
1. search_nodes(query="PaymentService")  →  returns list of {node_id, name, type, file}
2. get_node_signature(node_id=<id>)      →  inspect the target node
3. get_downstream_dependencies(node_id)  →  blast radius
4. get_narrowed_context(node_id, goal)   →  fetch minimal relevant source
```

`search_nodes` is the mandatory entry point. All other tools assume the agent already holds a valid `node_id`.

### Tool surface (Phase 1 + 2)

| Tool | Args | Returns | Phase |
|---|---|---|---|
| `get_node_signature` | `node_id` | name, type, file, line range, language | 1 |
| `get_downstream_dependencies` | `node_id`, `depth=3` | list of nodes reachable downstream | 1 |
| `get_upstream_callers` | `node_id`, `depth=3` | list of nodes that call/import this node | 1 |
| `get_node_history` | `node_id`, `limit=10` | list of commits touching this node | 1 |
| `search_nodes` | `query`, `type?`, `language?` | fuzzy-matched node list | 1 |
| `get_agent_session_history` | `session_id` | list of prior actions in this session | 1 |
| `record_agent_action` | `session_id`, `node_id`, `action` | confirmation | 1 |
| `get_narrowed_context` | `node_id`, `goal` | minimised code snippet for task goal | 2 |
| `get_graph_at_commit` | `commit_sha` | full graph state at that commit | 2 |
| `get_blast_radius_report` | `node_id` | affected nodes + risk score | 2 |

### Context Pruning Engine (`get_narrowed_context`)

The context pruning tool is the highest-value MCP tool. Given a `node_id` and a natural-language `goal`, it:

1. Extracts the 1-hop ego graph around the node
2. Scores each neighbour by relevance to `goal` using keyword overlap against node names + commit messages
3. Returns only the source code of the top-N scored nodes, serialised as a compact JSON structure

No LLM call is made inside this tool — it is fully deterministic. Token budget is configurable (default: 8,000 tokens).

---

## 7. Frontend Architecture

The UI is a single-page React app served by FastAPI's static file handler. It does not require a separate Node.js process in production.

**Build process:** `vite build` compiles the React app into `ui/dist/`. The Python package's `pyproject.toml` includes a build hook (via `hatch-build-scripts` or equivalent) that runs `vite build` automatically before `pip install`. FastAPI mounts `ui/dist/` as a `StaticFiles` directory at `/`. In development, `vite dev` runs on port 5173 with a proxy to the FastAPI backend on port 7842.

**Default port:** The FastAPI server binds to `localhost:7842` by default. Configurable via `--port N` CLI flag or `REPO_GRAPH_PORT` environment variable.

### Data flow

```
GraphCanvas
    │
    ├── useGraph() → GET /api/graph → full node+edge list (initial load)
    │
    ├── useTimeline() → GET /api/timeline → list of {commit_sha, date, message}
    │        │
    │        └── on scrub → GET /api/graph-at/:commit_sha → patched graph state
    │
    └── WebSocket /ws/graph-updates → push on file-watch events (incremental)
```

### Key rendering decisions

- **WebGL via `react-force-graph-3d`** for the primary canvas. Falls back to 2D (`react-force-graph-2d`) if WebGL is unavailable.
- **Node sizing**: proportional to `churn_score + dependency_count` combined weight.
- **Blast radius highlight**: on node click, BFS outward to `depth=3` — highlighted nodes stay full opacity, rest dim to 10%.
- **Overlay layers** (toggled independently): Complexity (node colour by cyclomatic_complexity), Churn (node colour by churn_score), Ownership (node colour by primary_owner hash).
- **Time-travel**: the slider sends the nearest commit SHA to the backend; the backend replays diff-patches and returns the mutated graph. The frontend does a smooth interpolated transition between the two graph states.

---

## 8. Plugin System

Plugins are Python files dropped into a `plugins/` directory at the repo root (or a configurable path). They are loaded at ingestion time via `importlib`.

### Plugin interface

```python
# plugins/base.py
class RepoGraphPlugin:
    name: str
    version: str

    def on_node_created(self, node: Node) -> Node:
        # called after each node is extracted from AST
        # return the (optionally mutated) node
        return node

    def on_graph_ready(self, graph: rustworkx.PyDiGraph, db_path: str) -> None:
        # called once after full ingestion is complete
        # can add new nodes/edges or write to extra_json fields
        pass
```

### Security note

Plugins run with the same OS permissions as code-nexus. They are **not sandboxed** in Phase 1–3. WASM sandboxing is a Phase 4 goal. Document this clearly in the plugin developer guide.

---

## 9. Phase Build Plan

### Phase 1 — Alpha (ship this first, validate the core bet)

**Goal:** Prove the MCP server works and reduces token usage on real tasks.

- [ ] `codenexus/ingestion/parser.py` — tree-sitter parsing for Python + TypeScript + Rust
- [ ] `codenexus/ingestion/engine.py` — parallel worker pool (multiprocessing)
- [ ] `codenexus/graph/store.py` — rustworkx in-memory graph + SQLite persistence
- [ ] `codenexus/mcp/tools/structural.py` — 5 core MCP tools
- [ ] `codenexus/graph/session.py` — agent session persistence
- [ ] `codenexus/mcp/tools/session.py` — session MCP tools
- [ ] `codenexus/cli.py` — three commands:
  - `code-nexus start .` — ingest + start FastAPI (MCP via HTTP/SSE + UI). Full stack. For human use.
  - `code-nexus mcp .` — ingest + start MCP server via `stdio` only. No UI, no FastAPI. For agent use (Claude Code, etc.).
  - `code-nexus sync .` — re-run git overlay on existing graph, pick up new commits only.
- [ ] File watcher (watchdog) for incremental updates
- [ ] Basic 2D graph UI (react-force-graph-2d, no time-travel yet)
- [ ] Docker image
- [ ] `pyproject.toml` — package name `code-nexus`, entry point `code-nexus = "code-nexus.cli:main"`, Python ≥3.11, Vite build hook, core deps: `tree-sitter`, `rustworkx`, `pydriller`, `fastapi`, `uvicorn`, `watchdog`, `msgpack`, `click`
- [ ] Add `.codenexus/` to the project's `.gitignore` template (graph DB must not be committed)
- [ ] `CONTRIBUTING.md` — language parser guide, plugin guide, dev setup instructions
- [ ] **Benchmark:** measure token consumption on 5 representative multi-file queries vs full-file injection. Publish results in README.

### Phase 2 — Beta

**Goal:** Add the git temporal layer and context pruning — the two core differentiators.

- [ ] `codenexus/ingestion/git_overlay.py` — PyDriller commit → node property mapping
- [ ] `codenexus/ingestion/diff_snapshot.py` — per-commit graph diff-patches
- [ ] `codenexus/mcp/tools/temporal.py` — `get_node_history`, `get_graph_at_commit`
- [ ] `codenexus/mcp/tools/context.py` — context pruning engine
- [ ] `ui/src/components/TimeSlider.tsx` — time-travel slider
- [ ] 3D canvas upgrade (react-force-graph-3d)
- [ ] Analytical overlays (Complexity, Churn, Ownership heatmaps)
- [ ] `get_blast_radius_report` MCP tool

### Phase 3 — v1.0

**Goal:** Plugin ecosystem, IDE extensions, CI/CD integration.

- [ ] **Opt-in anonymous telemetry** — on first run, prompt user once: "Send anonymous usage stats to help prioritise development? [y/N]". Answer stored in `~/.config/codenexus/config.toml`. If opted in, send a single POST on startup to a self-hosted endpoint containing: repo size bucket (not content), language list, OS, ingestion time, MCP tool call counts (not args). No code, no paths, no symbols ever leave the machine. Implementation: `codenexus/telemetry.py`, fire-and-forget with 2s timeout.
- [ ] `codenexus/plugins/` — plugin loader + base class
- [ ] VS Code extension (separate repo: `code-nexus-vscode`)
- [ ] Cursor `contextProvider` adapter
- [ ] GitHub Actions workflow: `code-nexus blast-radius --base main --head HEAD --fail-on-depth 5`
- [ ] `FR5.2` UI widget API

### Phase 4 — Beyond v1.0

- WASM plugin sandboxing
- Multi-repo "Cross-Mesh" (cross-service dependency mapping)
- Optional GitHub/GitLab API enrichment for PR metadata
- Community language parsers (Go, Java, C/C++)

---

## 10. Key Technical Decisions & Rationale

| Decision | Choice | Why | Rejected Alternative |
|---|---|---|---|
| Graph library | `rustworkx` | Drop-in NetworkX API, Rust-backed, 3–100x faster. Critical for sub-30s ingestion. | `NetworkX` (pure Python, too slow at 50k+ nodes) |
| Parsing | `tree-sitter` via `py-tree-sitter` | Industry standard, 70+ grammars, byte-level precision | `ast` (Python-only), `ctags` (less precise) |
| Git parsing | `PyDriller` | Clean Python API over GitPython, built-in commit traversal | Raw `git log` subprocess |
| Persistence | `SQLite` (single file, WAL mode) | Zero external dependencies, file is portable, WAL allows concurrent reads | `DuckDB` (heavier), `Neo4j` (requires install) |
| Diff storage | `msgpack` blobs in SQLite | Compact binary serialisation, no schema migrations for diff format | JSON (2–3x larger), separate files |
| MCP transport | `stdio` (Phase 1), `HTTP/SSE` (Phase 2+) | `stdio` is simplest for local CLI use; HTTP/SSE needed for IDE extensions | WebSocket (more complex, less MCP-idiomatic) |
| Frontend bundler | `Vite` | Fast HMR in dev; `vite build` → static assets served by FastAPI in prod | CRA (slow), Next.js (overkill for single-page tool) |
| Node scope | Module-level + exported symbols only | Keeps graph under 50k nodes for most repos; local variables add noise, not signal | All variables (would generate millions of nodes in large repos) |
| File size cap | Skip files > 500KB | Prevents tree-sitter-javascript grammar performance cliff on generated/minified files | No cap (would cause unpredictable ingestion times) |
| Parallelism model | `multiprocessing` (not `asyncio`) | Bypasses Python GIL for CPU-bound AST parsing | `asyncio` (GIL-bound for CPU work), `threading` (GIL-bound) |
| Python minimum version | 3.11+ | `rustworkx` and `py-tree-sitter` both support 3.8+, but 3.11 offers 10–60% speed improvements for CPU-bound workloads relevant to ingestion | 3.8/3.9/3.10 (all valid, just slower) |
| File watcher | `watchdog` | Cross-platform, well-maintained, works on macOS/Linux/Windows | `inotify` (Linux-only), polling (high CPU) |

---

## 11. Performance Targets (Revised)

| Metric | Target | Conditions |
|---|---|---|
| Initial ingestion, 100k LOC | < 30s | M1 Mac, 4 workers, SSD |
| Initial ingestion, 500k LOC | < 60s | M1 Mac, 4 workers, SSD |
| Incremental update (1 file changed) | < 2s | Any hardware |
| MCP query response (structural) | < 100ms | Graph loaded in memory |
| MCP query response (context pruning) | < 500ms | Graph loaded in memory |
| UI render, 10,000 nodes | stable 60 FPS | WebGL/Three.js |
| Agent token reduction (architectural queries) | > 80% vs full-file injection | Measured on 10-repo benchmark suite |
