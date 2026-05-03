# Contributing to code-nexus

Thank you for your interest in contributing to code-nexus! This document outlines how to set up your development environment, contribute code, and extend the project.

## Development Setup

### Prerequisites
- Python ≥ 3.11
- Node.js ≥ 18 (for UI development)
- Git

### Local Installation (Editable Mode)

```bash
git clone https://github.com/snagrecha/code-nexus.git
cd code-nexus

# Install Python dependencies
pip install -e ".[dev]"

# Install UI dependencies
cd ui
npm install
cd ..
```

### Running Tests

```bash
# Backend tests
pytest tests/

# Frontend tests (from ui/ directory)
npm test
```

### Development Server

```bash
# Backend + UI (hot reload)
code-nexus start .
```

The backend runs on `http://localhost:7842`, and the React dev server (Vite) runs on `http://localhost:5173` with proxy to the backend.

## Adding Language Support

To add parsing support for a new language:

1. **Create a language-specific parser module** in `codenexus/ingestion/languages/`:
   ```python
   # codenexus/ingestion/languages/go.py
   from codenexus.ingestion.languages.base import BaseLanguageParser
   
   class GoParser(BaseLanguageParser):
       language = "go"
       extensions = [".go"]
       
       def extract_nodes_and_edges(self, tree, file_path):
           # Return (nodes, edges) tuples
           pass
   ```

2. **Register your parser** in `codenexus/ingestion/parser.py`:
   ```python
   from codenexus.ingestion.languages.go import GoParser
   
   LANGUAGE_PARSERS = {
       "go": GoParser(),
       # ...
   }
   ```

3. **Test on a small repository:**
   ```bash
   code-nexus start /path/to/test/go/repo
   ```

4. **Add unit tests** in `tests/ingestion/languages/test_go.py`.

## Writing Plugins

Plugins allow you to inject custom metadata or node types into the graph.

### Plugin Template

```python
# plugins/my_plugin.py
from codenexus.graph.schema import Node, Edge
from codenexus.plugins.base import RepoGraphPlugin

class MyPlugin(RepoGraphPlugin):
    name = "my-plugin"
    version = "0.1.0"
    
    def on_node_created(self, node: Node) -> Node:
        """Called after each node is extracted from AST."""
        # Example: mark security-sensitive functions
        if node.type == "function" and "password" in node.name.lower():
            node.extra_json = {"security_sensitive": True}
        return node
    
    def on_graph_ready(self, graph, db_path: str) -> None:
        """Called after full ingestion is complete."""
        # Example: add custom edges based on external analysis
        pass
```

### Loading Plugins

Place your plugin in a `plugins/` directory at the repo root:
```bash
code-nexus start . --plugins-dir ./plugins
```

**Security Note:** Plugins run with your OS permissions in Phase 1–3. WASM sandboxing is a Phase 4 goal. Only load plugins you trust.

## Adding MCP Tools

To add a new MCP tool:

1. **Implement the tool function** in the appropriate `codenexus/mcp/tools/*.py` module:
   ```python
   # codenexus/mcp/tools/structural.py
   def my_new_tool(node_id: str, param: str) -> dict:
       """Tool description for the MCP server."""
       # Implementation
       return {"result": "..."}
   ```

2. **Register it in the MCP server** in `codenexus/mcp/server.py`:
   ```python
   server.register_tool(
       name="my_new_tool",
       description="What this tool does",
       input_schema={
           "type": "object",
           "properties": {
               "node_id": {"type": "string"},
               "param": {"type": "string"}
           },
           "required": ["node_id"]
       },
       handler=my_new_tool
   )
   ```

3. **Add tests** in `tests/mcp/test_tools.py`.

4. **Update ARCHITECTURE.md** to document the new tool in the "Tool surface" table.

## Code Style

- **Python:** Follow PEP 8. Format with `black`, lint with `ruff`.
  ```bash
  black codenexus tests
  ruff check codenexus tests
  ```

- **TypeScript/React:** Use Prettier and ESLint.
  ```bash
  npm run lint
  npm run format
  ```

## Commit Messages

Use clear, descriptive commit messages:

```
[component] Brief description

Longer explanation if needed. Mention issue numbers:
Fixes #123
```

Examples:
- `[parser] Add Go language support`
- `[ui] Improve blast radius rendering performance`
- `[mcp] Add context pruning tool (Phase 2)`

## Submitting a Pull Request

1. **Fork and branch:** Create a feature branch from `main`.
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Develop and test:** Make your changes, add tests, ensure tests pass.
   ```bash
   pytest tests/
   npm test
   ```

3. **Format code:**
   ```bash
   black code-nexus tests
   ruff check --fix code-nexus tests
   npm run format
   ```

4. **Open a PR:** Include a clear description of what you changed and why.

## Reporting Issues

- **Bug reports:** Describe steps to reproduce, expected vs. actual behavior, environment details.
- **Feature requests:** Explain the use case and how it aligns with code-nexus's goals.
- **Performance issues:** Include repo size, system specs, and timing traces if possible.

## Architecture & Design Philosophy

Before making large changes, review:
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design and rationale
- [prd.md](prd.md) — Product vision and functional requirements
- [Phase Build Plan](#phase-build-plan) in ARCHITECTURE.md — What's in scope for each phase

**Core principles:**
- Local-first: No network calls or external services needed.
- Performance-first: Ingestion time and query latency are hard constraints.
- AI-first: Design all features with agent usability in mind.
- Zero-config: Users should only need `pip install` + `code-nexus start .`.

## Questions?

- Open a GitHub issue for bug reports and feature discussions.
- Refer to [ARCHITECTURE.md](ARCHITECTURE.md) for deep technical details.
- Check [prd.md](prd.md) for product context and roadmap.

Thank you for contributing! 🎉
