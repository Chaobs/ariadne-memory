"""
Ariadne CLI — Command-line interface for the Ariadne memory system.
"""

import click
import sys
from pathlib import Path

try:
    from colorama import Fore, init as colorama_init
    colorama_init(autoreset=True)
except ImportError:
    class Fore:
        RED = "\033[91m"
        GREEN = "\033[92m"
        YELLOW = "\033[93m"
        CYAN = "\033[96m"
        RESET = "\033[0m"

from ariadne import __version__
from ariadne.memory import VectorStore
from ariadne.ingest import (
    MarkdownIngestor,
    WordIngestor,
    PPTIngestor,
    PDFIngestor,
    TxtIngestor,
    ConversationIngestor,
    MindMapIngestor,
    CodeIngestor,
)

INGESTORS = {
    ".md": MarkdownIngestor,
    ".docx": WordIngestor,
    ".pptx": PPTIngestor,
    ".pdf": PDFIngestor,
    ".txt": TxtIngestor,
    ".mm": MindMapIngestor,
    ".xmind": MindMapIngestor,
    ".py": CodeIngestor,
    ".java": CodeIngestor,
    ".cpp": CodeIngestor,
    ".c": CodeIngestor,
    ".js": CodeIngestor,
    ".ts": CodeIngestor,
}


def resolve_ingestor(path: Path):
    suffix = path.suffix.lower()
    for ext, cls in INGESTORS.items():
        if suffix == ext:
            return cls()
    return None


@click.group()
@click.version_option(version=__version__)
def main():
    """Ariadne — Cross-Source AI Memory & Knowledge Weaving System."""
    pass


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--recursive", "-r", is_flag=True, help="Recursively ingest all supported files")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def ingest(path: str, recursive: bool, verbose: bool):
    """Ingest a file or directory into the Ariadne memory system."""
    store = VectorStore()
    target = Path(path)

    files_processed = 0
    docs_created = 0

    if target.is_file():
        files = [target]
    elif target.is_dir():
        files = []
        for ext in INGESTORS:
            if recursive:
                files.extend(target.rglob(f"*{ext}"))
            else:
                files.extend(target.glob(f"*{ext}"))
    else:
        click.secho(f"Error: {path} is not a valid file or directory", fg="red")
        sys.exit(1)

    for file_path in files:
        ingestor_cls = resolve_ingestor(file_path)
        if ingestor_cls is None:
            if verbose:
                click.echo(f"  {Fore.YELLOW}SKIP{Fore.RESET}  {file_path} (unsupported format)")
            continue

        try:
            ingestor = ingestor_cls()
            docs = ingestor.ingest(str(file_path))
            if docs:
                store.add(docs)
                files_processed += 1
                docs_created += len(docs)
                if verbose:
                    click.echo(f"  {Fore.GREEN}ADD{Fore.RESET}   {file_path} -> {len(docs)} chunks")
        except Exception as e:
            if verbose:
                click.echo(f"  {Fore.RED}ERROR{Fore.RESET}  {file_path}: {e}")

    click.secho(f"\nDone! Processed {files_processed} files, created {docs_created} documents.", fg="green")


@main.command()
@click.argument("query", type=str)
@click.option("--top-k", "-k", default=5, help="Number of results to return")
@click.option("--verbose", "-v", is_flag=True, help="Show document metadata")
def search(query: str, top_k: int, verbose: bool):
    """Search the Ariadne memory system."""
    store = VectorStore()
    results = store.search(query, top_k=top_k)

    if not results:
        click.secho("No results found.", fg="yellow")
        return

    click.secho(f"\nFound {len(results)} results:\n", fg="green")
    for i, (doc, score) in enumerate(results, 1):
        click.secho(f"[{i}] (score: {score:.4f})", fg="cyan")
        click.echo(doc.content[:300])
        if verbose and doc.metadata:
            click.echo(f"    Source: {doc.metadata.get('source', 'unknown')} | "
                       f"Type: {doc.metadata.get('source_type', 'unknown')}")
        click.echo()


@main.command()
@click.option("--stats", is_flag=True, help="Show collection statistics")
def info(stats: bool):
    """Show information about the Ariadne memory system."""
    store = VectorStore()
    click.echo(f"Ariadne Memory System v{__version__}")
    click.echo(f"Storage backend: ChromaDB")
    click.echo(f"Data directory: {store.persist_dir}")

    if stats:
        try:
            count = store.count()
            click.echo(f"Documents indexed: {count}")
        except Exception:
            click.echo("Documents indexed: (unable to retrieve)")


if __name__ == "__main__":
    main()
