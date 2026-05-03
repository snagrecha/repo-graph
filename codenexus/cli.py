import click
from codenexus import __version__


@click.group()
@click.version_option(version=__version__)
def main():
    """codenexus: Transform codebases into semantic knowledge graphs."""
    pass


@main.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--port", default=7842, help="Port for the FastAPI server")
@click.option("--workers", default=4, help="Number of parallel parsing workers")
@click.option("--full-reindex", is_flag=True, help="Force full re-index (includes git overlay)")
def start(path, port, workers, full_reindex):
    """Ingest repository and start the FastAPI server (UI + MCP)."""
    import logging
    from pathlib import Path
    from codenexus.ingestion.engine import IngestionEngine

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(name)s:%(levelname)s] %(message)s"
    )

    click.echo(f"Starting codenexus for: {path}")
    
    db_path = Path(path) / ".code-nexus" / "graph.db"
    engine = IngestionEngine(repo_root=path, db_path=db_path)
    engine.run(workers=workers, full_reindex=full_reindex)

    import uvicorn
    from codenexus.api.app import create_app
    from codenexus.graph.store import GraphStore

    store = GraphStore(db_path)
    try:
        app = create_app(store, str(Path(path).resolve()))
        click.echo(f"Listening on http://localhost:{port}")
        click.echo(f"MCP SSE endpoint: http://localhost:{port}/mcp/sse")
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    finally:
        store.close()


@main.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--workers", default=4, help="Number of parallel parsing workers")
def mcp(path, workers):
    """Ingest repository and start the MCP server via stdio transport."""
    import asyncio
    import logging
    from pathlib import Path
    from codenexus.ingestion.engine import IngestionEngine
    from codenexus.graph.store import GraphStore
    from codenexus.mcp.server import run_stdio_server

    logging.basicConfig(
        level=logging.WARNING, format="%(asctime)s [%(name)s:%(levelname)s] %(message)s"
    )

    db_path = Path(path) / ".code-nexus" / "graph.db"
    
    # 1. Ensure graph is ingested
    engine = IngestionEngine(repo_root=path, db_path=db_path)
    engine.run(workers=workers)

    # 2. Start MCP server
    # We use a context manager to ensure DB is closed on exit if needed,
    # but the server runs until stdin is closed.
    store = GraphStore(db_path)
    try:
        asyncio.run(run_stdio_server(store, path))
    finally:
        store.close()


@main.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
def sync(path):
    """Re-run git overlay on an existing graph."""
    import logging
    from pathlib import Path
    from codenexus.graph.store import GraphStore
    from codenexus.ingestion.git_overlay import apply_git_overlay

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(name)s:%(levelname)s] %(message)s"
    )

    click.echo(f"Syncing git history for: {path}")
    db_path = Path(path) / ".code-nexus" / "graph.db"

    with GraphStore(db_path) as store:
        apply_git_overlay(path, store)
        
    click.echo("Sync complete.")


if __name__ == "__main__":
    main()
