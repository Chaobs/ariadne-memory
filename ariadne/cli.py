"""
Ariadne CLI — Modern command-line interface powered by Typer.

Supports:
- Single and multi-memory system operations
- File ingestion with progress (Rich)
- Semantic search
- Memory system management (create, rename, delete, merge)
- LLM configuration and testing
- Advanced features (summary, graph, export)

Built with Typer (type-hint driven) + Rich (beautiful terminal output).
"""

import sys
import os
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.text import Text

from ariadne import __version__
from ariadne.memory import VectorStore, MemoryManager, get_manager
from ariadne.ingest import get_ingestor
from ariadne.ingest.markitdown_ingestor import MarkItDownIngestor
from ariadne.config import (
    AriadneConfig,
    get_config,
    reload_config,
    print_config_info,
    list_supported_providers,
)

# Rich console for styled output
console = Console()

# Supported extensions for directory scanning
SCAN_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".pdf", ".docx", ".pptx",
    ".xlsx", ".xls", ".csv", ".json",
    ".mm", ".xmind",
    ".py", ".java", ".cpp", ".c", ".h", ".hpp",
    ".js", ".ts", ".jsx", ".tsx", ".cs", ".go", ".rs", ".rb",
    ".php", ".swift", ".kt", ".scala",
    ".epub", ".bib", ".ris",
    ".eml", ".mbox",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
    ".mp4", ".avi", ".mkv", ".mov",
    ".mp3", ".wav", ".m4a", ".flac", ".ogg",
    # markitdown-supported
    ".html", ".htm", ".rss", ".ipynb", ".msg", ".rtf",
    ".ods", ".odt", ".odp", ".xml",
}


def resolve_ingestor(path: Path):
    """Resolve an ingestor for the given file path using the unified factory."""
    try:
        return get_ingestor(str(path))
    except (ValueError, ImportError):
        return None


# ═══════════════════════════════════════════
# Main app
# ═══════════════════════════════════════════

app = typer.Typer(
    name="ariadne",
    help="Ariadne — Cross-Source AI Memory & Knowledge Weaving System.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

memory_app = typer.Typer(help="Memory system management commands.")
app.add_typer(memory_app, name="memory")

config_app = typer.Typer(help="Configuration management commands.")
app.add_typer(config_app, name="config")

advanced_app = typer.Typer(help="Advanced features (requires LLM configuration).")
app.add_typer(advanced_app, name="advanced")


def version_callback(value: bool):
    if value:
        console.print(f"Ariadne v{__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        None, "--version", "-v", help="Show version and exit.",
        callback=version_callback, is_eager=True,
    ),
):
    """Ariadne — Cross-Source AI Memory & Knowledge Weaving System."""


# ═══════════════════════════════════════════
# Memory System Management
# ═══════════════════════════════════════════

@memory_app.command("list")
def memory_list():
    """List all memory systems."""
    manager = get_manager()
    systems = manager.list_systems()

    table = Table(title="Memory Systems", show_lines=False)
    table.add_column("Default", style="bold cyan", width=3)
    table.add_column("Name", style="green")
    table.add_column("Documents", justify="right", style="yellow")
    table.add_column("Description", style="dim")

    for s in systems:
        info = manager.get_info(s.name)
        count = str(info.get("document_count", "?")) if info else "?"
        marker = "★" if s.name == manager.DEFAULT_COLLECTION else ""
        desc = s.description or ""
        table.add_row(marker, s.name, count, desc)

    console.print(table)
    console.print(f"Total: [bold]{len(systems)}[/bold] memory system(s)")


@memory_app.command("create")
def memory_create(
    name: str = typer.Argument(..., help="Name for the new memory system"),
    description: str = typer.Option("", "--description", "-d", help="Description"),
):
    """Create a new memory system."""
    manager = get_manager()
    try:
        manager.create(name, description)
        console.print(f"[bold green][OK][/bold green] Created: {name}")
    except ValueError as e:
        console.print(f"[bold red][ERROR][/bold red] {e}")
        raise typer.Exit(1)


@memory_app.command("rename")
def memory_rename(
    old_name: str = typer.Argument(..., help="Current name"),
    new_name: str = typer.Argument(..., help="New name"),
):
    """Rename a memory system."""
    manager = get_manager()
    try:
        manager.rename(old_name, new_name)
        console.print(f"[bold green][OK][/bold green] Renamed: {old_name} → {new_name}")
    except ValueError as e:
        console.print(f"[bold red][ERROR][/bold red] {e}")
        raise typer.Exit(1)


@memory_app.command("delete")
def memory_delete(
    name: str = typer.Argument(..., help="Memory system to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a memory system."""
    manager = get_manager()

    if name == manager.DEFAULT_COLLECTION:
        console.print("[bold red][ERROR][/bold red] Cannot delete the default memory system")
        raise typer.Exit(1)

    if not yes:
        confirm = typer.confirm(f"Delete '{name}'? This cannot be undone.")
        if not confirm:
            raise typer.Abort()

    try:
        manager.delete(name, confirm=False)
        console.print(f"[bold green][OK][/bold green] Deleted: {name}")
    except ValueError as e:
        console.print(f"[bold red][ERROR][/bold red] {e}")
        raise typer.Exit(1)


@memory_app.command("merge")
def memory_merge(
    source_names: List[str] = typer.Argument(..., help="Source memory systems to merge"),
    new_name: str = typer.Option(..., "--into", help="Name for the merged system"),
    delete_sources: bool = typer.Option(False, "--delete", "-d", help="Delete sources after merge"),
):
    """Merge multiple memory systems into a new one.

    Example:
        ariadne memory merge research notes --into combined
    """
    manager = get_manager()
    try:
        manager.merge(source_names, new_name, delete_sources=delete_sources)
        console.print(f"[bold green][OK][/bold green] Merged into: {new_name}")
    except ValueError as e:
        console.print(f"[bold red][ERROR][/bold red] {e}")
        raise typer.Exit(1)


@memory_app.command("info")
def memory_info(
    name: Optional[str] = typer.Argument(None, help="Memory system name (default if omitted)"),
):
    """Show information about a memory system."""
    manager = get_manager()

    if name is None:
        name = manager.DEFAULT_COLLECTION

    info = manager.get_info(name)
    if not info:
        console.print(f"[bold red][ERROR][/bold red] Memory system '{name}' not found")
        raise typer.Exit(1)

    panel_content = Text()
    panel_content.append(f"Path:        {info['path']}\n")
    panel_content.append(f"Documents:   {info.get('document_count', 0)}\n")
    panel_content.append(f"Created:     {info.get('created_at', 'N/A')[:10]}\n")
    panel_content.append(f"Updated:     {info.get('updated_at', 'N/A')[:10]}\n")
    if info.get('description'):
        panel_content.append(f"Description: {info['description']}\n")

    console.print(Panel(panel_content, title=f"[cyan]{name}[/cyan]", border_style="cyan"))


@memory_app.command("clear")
def memory_clear(
    name: Optional[str] = typer.Argument(None, help="Memory system name (default if omitted)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Clear all documents from a memory system."""
    manager = get_manager()

    if name is None:
        name = manager.DEFAULT_COLLECTION

    if not yes:
        confirm = typer.confirm(f"Clear all documents from '{name}'?")
        if not confirm:
            raise typer.Abort()

    try:
        manager.clear(name)
        console.print(f"[bold green][OK][/bold green] Cleared: {name}")
    except Exception as e:
        console.print(f"[bold red][ERROR][/bold red] {e}")
        raise typer.Exit(1)


@memory_app.command("export")
def memory_export(
    name: str = typer.Argument(..., help="Memory system to export"),
    output_path: str = typer.Argument(..., help="Output directory path"),
):
    """Export a memory system to a directory (for backup or sharing).

    Example:
        ariadne memory export research ./backup/research_memory
    """
    manager = get_manager()
    try:
        path = manager.export(name, output_path)
        console.print(f"[bold green][OK][/bold green] Exported '{name}' to: {path}")
    except ValueError as e:
        console.print(f"[bold red][ERROR][/bold red] {e}")
        raise typer.Exit(1)


@memory_app.command("import")
def memory_import(
    source_path: str = typer.Argument(..., help="Source directory path", exists=True),
    name: str = typer.Argument(..., help="Name for the imported memory system"),
):
    """Import a memory system from a previously exported directory.

    Example:
        ariadne memory import ./backup/research_memory imported_research
    """
    manager = get_manager()
    try:
        manager.import_memory(source_path, name)
        console.print(f"[bold green][OK][/bold green] Imported '{source_path}' as: {name}")
    except ValueError as e:
        console.print(f"[bold red][ERROR][/bold red] {e}")
        raise typer.Exit(1)


# ═══════════════════════════════════════════
# File Ingestion
# ═══════════════════════════════════════════

@app.command()
def ingest(
    path: str = typer.Argument(..., help="File or directory to ingest", exists=True),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Recursively ingest all supported files"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
    batch_size: int = typer.Option(100, "--batch-size", "-b", help="Batch size for vector storage"),
    memory: Optional[str] = typer.Option(None, "--memory", "-m", help="Target memory system name"),
):
    """Ingest a file or directory into a memory system."""
    manager = get_manager()
    store = manager.get_store(memory)

    target = Path(path)
    files_processed = 0
    docs_created = 0
    errors = []

    if target.is_file():
        files = [target]
    elif target.is_dir():
        files = []
        for ext in SCAN_EXTENSIONS:
            if recursive:
                files.extend(target.rglob(f"*{ext}"))
            else:
                files.extend(target.glob(f"*{ext}"))
    else:
        console.print(f"[bold red]Error:[/bold red] {path} is not a valid file or directory")
        raise typer.Exit(1)

    if not files:
        console.print("[yellow]No supported files found.[/yellow]")
        return

    target_system = memory or manager.DEFAULT_COLLECTION
    console.print(f"Target: [cyan]{target_system}[/cyan]")

    batch_docs = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Ingesting...", total=len(files))

        for file_path in files:
            ingestor = resolve_ingestor(file_path)
            if ingestor is None:
                if verbose:
                    console.print(f"  [yellow]SKIP[/yellow]  {file_path} (unsupported format)")
                progress.advance(task)
                continue

            try:
                docs = ingestor.ingest(str(file_path))
                if docs:
                    batch_docs.extend(docs)
                    files_processed += 1
                    docs_created += len(docs)

                    if len(batch_docs) >= batch_size:
                        store.add(batch_docs)
                        batch_docs = []

                    if verbose:
                        console.print(f"  [green]ADD[/green]   {file_path.name} → {len(docs)} chunks")
            except Exception as e:
                errors.append((str(file_path), str(e)))
                if verbose:
                    console.print(f"  [red]ERROR[/red]  {file_path.name}: {e}")

            progress.advance(task)

    # Flush remaining docs
    if batch_docs:
        store.add(batch_docs)

    # Summary
    console.print()
    console.print(Panel(
        f"Processed [bold green]{files_processed}[/bold green] files, "
        f"created [bold green]{docs_created}[/bold green] documents."
        + (f"\n[red]Errors: {len(errors)}[/red]" if errors else ""),
        title="Ingest Complete",
        border_style="green" if not errors else "yellow",
    ))

    if errors and verbose:
        for err_path, err_msg in errors:
            console.print(f"  [dim]- {err_path}: {err_msg}[/dim]")


# ═══════════════════════════════════════════
# Search
# ═══════════════════════════════════════════

@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show document metadata"),
    memory: Optional[str] = typer.Option(None, "--memory", "-m", help="Target memory system"),
):
    """Search a memory system."""
    manager = get_manager()
    store = manager.get_store(memory)
    results = store.search(query, top_k=top_k)

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    target_system = memory or manager.DEFAULT_COLLECTION
    console.print(f"\n[Memory: [cyan]{target_system}[/cyan]] Found [bold green]{len(results)}[/bold green] results:\n")

    for i, (doc, score) in enumerate(results, 1):
        # Truncate content for display
        content_preview = doc.content[:300].replace("\n", " ")
        console.print(f"[{i}] [dim](score: {score:.4f})[/dim]")
        console.print(f"  {content_preview}")
        if verbose and doc.metadata:
            src = doc.metadata.get("source", "unknown")
            stype = doc.metadata.get("source_type", "unknown")
            console.print(f"  [dim]Source: {src} | Type: {stype}[/dim]")
        console.print()


# ═══════════════════════════════════════════
# Info
# ═══════════════════════════════════════════

@app.command()
def info(
    stats: bool = typer.Option(False, "--stats", help="Show collection statistics"),
    memory: Optional[str] = typer.Option(None, "--memory", "-m", help="Target memory system"),
):
    """Show information about the Ariadne memory system."""
    manager = get_manager()
    target = memory or manager.DEFAULT_COLLECTION
    store = manager.get_store(target)

    info_text = Text()
    info_text.append(f"Ariadne Memory System v{__version__}\n")
    info_text.append(f"Current Memory:  {target}\n")
    info_text.append(f"Storage backend: ChromaDB\n")
    info_text.append(f"Data directory:  {store.persist_dir}\n")

    if stats:
        try:
            count = store.count()
            info_text.append(f"Documents indexed: {count}\n")
        except Exception:
            info_text.append("Documents indexed: (unable to retrieve)\n")

    console.print(Panel(info_text, border_style="cyan"))


# ═══════════════════════════════════════════
# GUI
# ═══════════════════════════════════════════

@app.command()
def gui():
    """Launch the graphical user interface."""
    try:
        from ariadne.gui import main as gui_main
        gui_main()
    except ImportError:
        console.print("[bold red]Error:[/bold red] tkinter is not available on this system.")
        console.print("[yellow]GUI requires a graphical environment (Windows/macOS/Linux desktop).[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error launching GUI:[/bold red] {e}")
        raise typer.Exit(1)


# ═══════════════════════════════════════════
# Config Management
# ═══════════════════════════════════════════

@config_app.command("show")
def config_show():
    """Show current configuration."""
    cfg = get_config()
    print_config_info(cfg)


@config_app.command("list-providers")
def config_list_providers():
    """List all supported LLM providers."""
    list_supported_providers()


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Configuration key (e.g. llm.provider)"),
    value: str = typer.Argument(..., help="Configuration value"),
):
    """Set a configuration value.

    Examples:
        ariadne config set llm.provider deepseek
        ariadne config set llm.model deepseek-chat
        ariadne config set locale.language zh_CN
        ariadne config set advanced.enable_reranker true
    """
    cfg = get_config()

    # Convert value type
    if value.lower() in ("true", "false"):
        value = value.lower() == "true"
    elif value.isdigit():
        value = int(value)
    elif value.replace(".", "", 1).isdigit():
        value = float(value)

    cfg.set(key, value)
    cfg.save_user()

    console.print(f"[bold green][OK][/bold green] Set {key} = {value}")
    console.print(f"Config saved to: {cfg.config_dir / 'config.json'}")


@config_app.command("get")
def config_get(
    key: str = typer.Argument(..., help="Configuration key"),
):
    """Get a configuration value."""
    cfg = get_config()
    value = cfg.get(key)
    if value is not None:
        console.print(f"{key} = {value}")
    else:
        console.print(f"[yellow]Key '{key}' not found[/yellow]")


@config_app.command("test")
def config_test():
    """Test LLM configuration."""
    cfg = get_config()

    with console.status("Testing LLM configuration..."):
        success, message = cfg.test_llm()

    if success:
        console.print(f"[bold green][OK][/bold green] {message}")
    else:
        console.print(f"[bold red][FAIL][/bold red] {message}")
        raise typer.Exit(1)


@config_app.command("set-api-key")
def config_set_api_key(
    provider: str = typer.Argument(..., help="LLM provider name"),
    api_key: str = typer.Argument(..., help="API key"),
    env: bool = typer.Option(False, "--env", "-e", help="Save to environment variable instead of config"),
):
    """Set API key for a provider.

    Examples:
        ariadne config set-api-key deepseek sk-xxxxx
        ariadne config set-api-key openai sk-xxxxx -e
    """
    provider = provider.lower()

    if env:
        env_var = f"{provider.upper()}_API_KEY"
        os.environ[env_var] = api_key
        console.print(f"[bold green][OK][/bold green] Set {env_var} (will apply for this session)")
    else:
        cfg = get_config()
        cfg.set("llm.provider", provider)
        cfg.set("llm.api_key", api_key)
        cfg.save_user()

        config_path = cfg.save_user()
        console.print(f"[bold green][OK][/bold green] Set API key for {provider}")
        console.print(f"Config saved to: {config_path}")


# ═══════════════════════════════════════════
# Advanced Features
# ═══════════════════════════════════════════

@advanced_app.command("summarize")
def advanced_summarize(
    query: Optional[str] = typer.Argument(None, help="Search query to summarize"),
    memory: Optional[str] = typer.Option(None, "--memory", "-m", help="Target memory system"),
    output_lang: Optional[str] = typer.Option(None, "--output-lang", "-l", help="Output language (zh_CN, en, fr, etc.)"),
):
    """Summarize search results or entire memory.

    Examples:
        ariadne advanced summarize
        ariadne advanced summarize "machine learning"
        ariadne advanced summarize -m research -l en
    """
    cfg = get_config()

    if not cfg.get("advanced.enable_summary"):
        console.print("[yellow]Summary feature is disabled. Enable with:[/yellow]")
        console.print("  ariadne config set advanced.enable_summary true")
        raise typer.Exit(1)

    llm = cfg.create_llm()
    if llm is None:
        console.print("[bold red]No LLM configured.[/bold red] Please set up your API key first.")
        console.print("Run 'ariadne config set-api-key <provider> <key>' to configure.")
        raise typer.Exit(1)

    manager = get_manager()
    store = manager.get_store(memory)
    target = memory or manager.DEFAULT_COLLECTION

    if query:
        console.print(f"Searching memory '[cyan]{target}[/cyan]' for: {query}")
        results = store.search(query, top_k=10)

        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return

        console.print(f"Found {len(results)} results, generating summary...")

        context = "\n\n".join(
            [f"[Document {i+1}]\n{doc.content[:500]}" for i, (doc, _) in enumerate(results)]
        )

        out_lang = output_lang or cfg.get_output_language()
        lang_prompts = {
            "zh_CN": "请用简体中文总结",
            "zh_TW": "請用繁體中文總結",
            "en": "Please summarize in English",
            "fr": "Veuillez résumer en français",
            "es": "Por favor, resuma en español",
            "ru": "Пожалуйста, суммируйте на русском",
            "ar": "يرجى تلخيص باللغة العربية",
        }
        lang_prompt = lang_prompts.get(out_lang, "Please summarize in English")

        prompt = f"""Based on the following search results, provide a concise summary.

Search Query: {query}

{lang_prompt}:

{context}

Please provide:
1. Main topics and themes
2. Key insights or findings
3. A brief summary (2-3 sentences)
"""
    else:
        console.print(f"Generating summary of memory '[cyan]{target}[/cyan]'...")
        count = store.count()

        if count == 0:
            console.print("[yellow]Memory is empty.[/yellow]")
            return

        console.print(f"Memory contains {count} documents. Note: Full summary requires processing all documents.")
        console.print("[yellow]Please use a search query for targeted summaries.[/yellow]")
        return

    try:
        with console.status("Generating summary..."):
            response = llm.chat(prompt)
        console.print(Panel(response.content, title="[cyan]Summary[/cyan]", border_style="cyan"))
    except Exception as e:
        console.print(f"[bold red]Error generating summary:[/bold red] {e}")
        raise typer.Exit(1)


@advanced_app.command("graph")
def advanced_graph(
    memory: Optional[str] = typer.Option(None, "--memory", "-m", help="Target memory system"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text, dot, json"),
):
    """Display knowledge graph or entity relationships.

    Examples:
        ariadne advanced graph
        ariadne advanced graph -m research -f dot
    """
    if format == "text":
        console.print(Panel(
            "This feature extracts entities and relationships from your memory.\n"
            "For visualization, use the GUI or export to DOT format.\n\n"
            "[dim]Note: Full graph extraction requires LLM configuration.\n"
            "Run 'ariadne config test' to verify your setup.[/dim]",
            title="Knowledge Graph",
            border_style="cyan",
        ))
    elif format == "dot":
        console.print("// DOT format for knowledge graph visualization")
        console.print("// Use with Graphviz: dot -Tpng graph.dot -o graph.png")
        console.print("digraph KnowledgeGraph {")
        console.print('    rankdir=LR;')
        console.print('    node [shape=box];')
        console.print("    // Configure LLM to enable entity extraction")
        console.print("}")
    else:
        import json
        console.print(json.dumps(
            {"status": "graph_feature", "note": "Configure LLM for entity extraction"},
            indent=2,
        ))


# ═══════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════

def main():
    """Entry point for the Ariadne CLI."""
    app()


if __name__ == "__main__":
    main()
