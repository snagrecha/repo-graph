Here is a complete Product Requirements Document (PRD) for **repo graph**, designed to serve as the foundational blueprint for development and open-source contribution.

---

# Product Requirements Document: repo graph

## 1. Executive Summary
**repo graph** is a local-first, open-source engine that transforms raw code repositories into highly structured Semantic Knowledge Graphs. It is designed with a dual-purpose architecture: to provide a deterministic, low-token context protocol for AI agents (via MCP) and to render an interactive, time-traveling visual map of the codebase for human developers. 

## 2. Problem Statement
* **For AI Agents:** Current AI coding assistants (Claude Code, Cursor) rely on rudimentary grep-style text search or basic RAG to understand codebases. When dealing with large repositories, this floods the LLM's context window with irrelevant text, leading to high token costs and severe hallucinations regarding architectural dependencies.
* **For Human Developers:** Static documentation decays instantly. Developers spend hours untangling "spaghetti code" to understand the potential "blast radius" of a Pull Request or diving through disjointed Git logs to understand *why* a specific function was written a certain way.

## 3. Product Vision & Goals
To become the standard protocol by which AI agents read and interpret local codebases, while simultaneously acting as the ultimate visual onboarding and debugging tool for engineering teams.

**Core Goals:**
* Enable AI agents to query codebase structures deterministically (e.g., "Give me the AST signature of this file and its direct imports") rather than reading raw text.
* **Context Pruning Engine:** Automatically strip non-essential code from the agent's view based on the current task goal, reducing token usage by up to 80% on architectural queries compared to full-file injection.
* Provide humans with a zero-config, visually stunning map of their code that updates in real-time.
* Achieve sub-60-second ingestion time for repositories up to 500k lines of code.

---

## 4. Target Audience
1.  **AI Tooling Developers:** Building local agents that need a better way to navigate codebases.
2.  **Senior Engineers / Tech Leads:** Needing to review massive PRs and understand the architectural impact before merging.
3.  **New Hires:** Trying to safely navigate and understand a legacy codebase without breaking existing features.

---

## 5. Functional Requirements

### 5.1 The Ingestion Engine (Backend)
* **FR1.1 AST Parsing:** The system must use `tree-sitter` to parse code into an Abstract Syntax Tree. It must identify Nodes (files, classes, functions, and module-level/exported symbols only — local variables are excluded to maintain graph scalability) and Edges (imports, function calls, inheritance).
* **FR1.2 Git Temporal Overlay:** The system must parse local `.git` folders to extract commit history, branch history, and author metadata, linking these as properties to the corresponding AST nodes. PR/issue metadata is out of scope for local parsing; an optional GitHub/GitLab API integration (requires a personal access token) may enrich nodes with PR context as an additive, non-blocking feature.
* **FR1.3 Language Support:** Launch support must include Python, TypeScript/JavaScript, and Rust. The architecture must allow community-driven parsers for other languages.

### 5.2 The Knowledge Graph Database
* **FR2.1 Graph Storage:** Must store the parsed nodes and edges using `rustworkx` as the in-memory graph structure and `SQLite` as the on-disk persistence layer. This eliminates any external database dependency.
* **FR2.2 Local Persistence:** The graph must be saved locally via SQLite (stored at `.codenexus/graph.db` inside the target repository) so the ingestion process does not need to run from scratch on every startup — only diffs should be processed after the initial run. SQLite must be opened in WAL mode to allow concurrent reads from the MCP server and UI API without blocking writes.

### 5.3 The Agent Protocol (MCP Server)
* **FR3.1 MCP Compliance:** The system must expose tools via the open Model Context Protocol standard.
* **FR3.2 Deterministic Queries:** Must provide specific endpoints, including:
    * `get_node_signature(node_id)`
    * `get_downstream_dependencies(node_id, depth)` — raw graph traversal (The Blast Radius)
    * `get_upstream_callers(node_id, depth)`
    * `get_node_history(node_id, limit)` — returns relevant commit messages (Phase 2, requires git overlay)
    * `search_nodes(query, type?, language?)` — fuzzy name/symbol search across all nodes
    * `get_blast_radius_report(node_id)` — enriched blast radius with risk score per affected node (Phase 2)
* **FR3.3 Intelligent Context Window:** A tool for agents to "request narrowed context," where repo graph returns a minimized AST/code snippet containing *only* logic relevant to a specific symbol.
* **FR3.4 Agent Action History:** The graph must track which nodes an agent has already inspected or modified during a session, persisted in the local SQLite database and scoped per project. A `get_agent_session_history(session_id)` MCP tool must allow agents to query prior actions on resume, preventing redundant exploration across restarts.

### 5.4 The Temporal Visualizer (Human UI)
* **FR4.1 3D/2D Graph Rendering:** A local web interface that visualizes the graph. Nodes must be sized dynamically based on their "weight" (number of dependencies).
* **FR4.2 The "Blast Radius" View:** A user clicks a node; the UI visually highlights all connected downstream nodes that rely on it, dimming the rest of the graph.
* **FR4.3 Time-Travel Slider:** A global UI slider representing the Git timeline. Scrubbing the slider must visually mutate the graph to show the architecture at a specific commit. Implementation: during initial ingestion, graph state is snapshotted as diff-patches per commit and stored in SQLite; timeline scrubbing replays these diffs rather than re-parsing the repository from scratch.
* **FR4.4 Analytical Overlays (Heatmaps):** Support for toggling layers such as "Complexity" (Cyclomatic breadth), "Churn" (Frequent commits), and "Ownership" (Primary author per module).

### 5.5 Plugin & Extension System
* **FR5.1 Data Ingestion Hooks:** Developers can write custom Python scripts to inject metadata or new node types into the graph (e.g., linking logs to code, or security scanner results).
* **FR5.2 UI Widget API:** Support for custom side-panel widgets that display node-specific data from external tools (e.g., JIRA tickets linked to a class).

---

## 6. Non-Functional Requirements
* **Privacy & Security (Zero-Trust):** 100% of the code ingestion, parsing, and graph storage must happen locally. No proprietary code can be sent to external servers.
* **Performance:** The visualizer must maintain a stable 60 FPS while rendering up to 10,000 nodes simultaneously using WebGL/Canvas.
* **Ingestion Parallelism:** The ingestion engine must default to 4 parallel worker processes for AST parsing, bypassing Python's GIL. Worker count must be configurable via `--workers N`. Files exceeding 500KB must be skipped with a logged warning to avoid tree-sitter grammar performance cliffs on large generated or minified files.
* **Usability (Zero-Config):** Installation must require no database setup or complex environment variables. Two commands should initialize the entire stack: `pip install code-nexus` followed by `code-nexus start .`. A Docker image (`docker run -v $(pwd):/repo repograph/code-nexus`) must also be provided as an alternative for users who prefer not to install Python dependencies globally.

---

## 7. Architecture & Tech Stack

| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Parser / Ingestion** | Python, `tree-sitter`, `PyDriller` | Python offers the best ecosystem for graph manipulation and AI integration; `tree-sitter` is the industry standard for fast AST generation. |
| **Graph Database** | `rustworkx` (Memory), `SQLite` (Disk) | `rustworkx` is a drop-in NetworkX replacement backed by Rust — same Python API, 3–100x faster graph construction and traversal. Removes the need for external DBs like Neo4j. |
| **Agent API** | `FastAPI`, MCP SDK | Lightweight, fast, and officially supported by modern AI agents. |
| **Frontend UI** | React, `react-force-graph` (WebGL), `Three.js` | Capable of rendering massive datasets visually without browser lag. |
| **Plugin System** | Python Dynamic Loading (`importlib`) | Plugins are Python scripts loaded at runtime via `importlib`. WASM-based sandboxing is a post-v1.0 consideration for untrusted third-party plugins. |
| **Distribution** | Docker / Binary Executable (PyInstaller) | Ensures the "Zero-Config" requirement is met. |

---

## 8. Success Metrics (KPIs)
* **Agent Efficiency:** Reduce average tokens consumed per architectural query (blast radius, upstream callers, dependency chains) by 80% compared to full-file injection, while preserving dependency-chain accuracy. Baseline: measured against naive full-file context injection on a 10-repo benchmark suite. Note: token reduction and task completion improvement are not directly proportional — this KPI measures context efficiency, not task success rate.
* **Ingestion Speed:** Parse a 100,000 LOC repository in under 30 seconds on an M1 Mac.
* **Community Adoption:** Reach 500 active projects using repo graph (measured via opt-in anonymous telemetry) within 8 weeks of the official 1.0 launch. GitHub stars are a supplementary vanity signal, not a primary KPI.
* **Integration:** Direct integration/usage by at least two major AI coding tools or frameworks (e.g., LangChain, LlamaIndex, Cursor).

---

## 9. Ecosystem & Integration Strategy
> These integrations are targeted for **Phase 3 (v1.0)**. They are described here for architectural planning; they are not Alpha or Beta scope.

### 9.1 IDE Extensions (The Visual HUD)
* **VS Code / JetBrains:** A companion extension that embeds the repo graph visualizer directly into the IDE sidebar. Clicking a node in the graph opens the corresponding file/line in the editor.
* **Cursor Integration:** repo graph provides a custom `contextProvider` for Cursor, allowing the agent to query the graph natively instead of relying on standard indexing.

### 9.2 CI/CD Pipeline Integration
* **Architecture Impact Reports:** Automation that runs repo graph on every PR, generating a "Blast Radius" report that highlights which modules are affected by the changes and warns of potential circular dependencies.

### 9.3 AI Agent Adapters
* **Claude Desktop / Claude Code:** Native MCP support enables Claude to use repo graph as its primary "spatial memory" for the codebase.

---

## 10. Future Roadmap (The Mesh Evolution)

* **Phase 1 (Alpha):** CLI-based ingestion, basic 2D graph, standard MCP query tools, and agent session history.
* **Phase 2 (Beta):** Git temporal overlay (diff-patch snapshots), 3D Canvas rendering, incremental syncing, and the "Context Pruning" engine.
* **Phase 3 (v1.0):** Plugin API launch, IDE extensions (VS Code / JetBrains), Cursor `contextProvider`, and CI/CD "Blast Radius" reports via GitHub Actions.
* **Phase 4 (Beyond):** WASM plugin sandboxing, multi-repository "Cross-Mesh" (mapping dependencies across microservices), and optional GitHub/GitLab API enrichment.
