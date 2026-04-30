import click
import sys
from repo_graph import __version__


@click.group()
@click.version_option(version=__version__)
def main():
    """repo-graph: Transform codebases into semantic knowledge graphs."""
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
    from repo_graph.ingestion.engine import IngestionEngine

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(name)s:%(levelname)s] %(message)s"
    )

    click.echo(f"Starting repo-graph for: {path}")
    
    db_path = Path(path) / ".repo-graph" / "graph.db"
    engine = IngestionEngine(repo_root=path, db_path=db_path)
    engine.run(workers=workers, full_reindex=full_reindex)

    click.echo(f"FastAPI server will listen on port: {port}")
    # TODO: Implement FastAPI startup
    click.echo("Error: FastAPI not implemented yet (Phase 1 API).", err=True)
    sys.exit(1)


@main.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
def mcp(path):
    """Start the MCP server via stdio transport (no UI)."""
    click.echo(f"Starting MCP server for: {path}")
    # TODO: Implement MCP stdio transport
    click.echo("Error: Not implemented yet (Phase 1).", err=True)
    sys.exit(1)


@main.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
def sync(path):
    """Re-run git overlay on an existing graph."""
    import logging
    from pathlib import Path
    from repo_graph.graph.store import GraphStore
    from repo_graph.ingestion.git_overlay import apply_git_overlay

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(name)s:%(levelname)s] %(message)s"
    )

    click.echo(f"Syncing git history for: {path}")
    db_path = Path(path) / ".repo-graph" / "graph.db"

    with GraphStore(db_path) as store:
        apply_git_overlay(path, store)
        
    click.echo("Sync complete.")


if __name__ == "__main__":
    main()
