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
def start(path, port):
    """Ingest repository and start the FastAPI server (UI + MCP)."""
    click.echo(f"Starting repo-graph for: {path}")
    click.echo(f"FastAPI server will listen on port: {port}")
    # TODO: Implement ingestion engine and FastAPI startup
    click.echo("Error: Not implemented yet (Phase 1).", err=True)
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
    click.echo(f"Syncing git history for: {path}")
    # TODO: Implement git overlay sync
    click.echo("Error: Not implemented yet (Phase 2).", err=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
