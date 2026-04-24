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

# ── Windows GBK console Unicode fix ───────────────────────────────────────────
# Force stdout/stderr to UTF-8 before any Rich output.
# Rich Console uses the console's encoding at instantiation time; if that encoding
# is GBK/CP936 it cannot render Unicode box-drawing / checkmark characters.
import sys as _sys
if _sys.platform == "win32":
    try:
        import io
        _sys.stdout = io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
        _sys.stderr = io.TextIOWrapper(_sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass  # Best-effort only; non-Windows or non-console environments are unaffected
# ────────────────────────────────────────────────────────────────────────────────

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


# Supported extensions for directory scanning (derived from registry)
def _get_scan_extensions() -> set:
    from ariadne.plugins.registry import IngestorRegistry
    return IngestorRegistry.get_supported_extensions()

SCAN_EXTENSIONS = _get_scan_extensions()


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

rag_app = typer.Typer(help="RAG pipeline commands (hybrid search + reranking + citations).")
app.add_typer(rag_app, name="rag")

mcp_app = typer.Typer(help="MCP server commands (Model Context Protocol integration).")
app.add_typer(mcp_app, name="mcp")

web_app = typer.Typer(help="Web UI commands (FastAPI + React frontend).")
app.add_typer(web_app, name="web")

wiki_app = typer.Typer(help="LLM Wiki commands (Karpathy-style persistent knowledge base).")
app.add_typer(wiki_app, name="wiki")

session_app = typer.Typer(help="Session memory commands (cross-session observation capture).")
app.add_typer(session_app, name="session")

hook_app = typer.Typer(help="Hook runner for IDE/AI platform lifecycle events.")
app.add_typer(hook_app, name="hook")


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
    enrich: bool = typer.Option(False, "--enrich", "-e",
        help="Extract entities/relations via LLM and store in knowledge graph"),
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

    # Knowledge Graph enrichment
    entities_added = 0
    relations_added = 0
    if enrich and docs_created > 0:
        from ariadne.paths import GRAPH_DB_PATH
        try:
            from ariadne.graph import GraphStorage, GraphEnricher
            from ariadne.config import get_config

            graph = GraphStorage(db_path=str(GRAPH_DB_PATH))
            cfg = get_config()
            llm = cfg.create_llm()

            if llm is None:
                console.print("[yellow]Warning: No LLM configured. "
                              "Run 'ariadne config test' to set up LLM.[/yellow]")
            else:
                enricher = GraphEnricher(llm=llm)
                # Re-fetch all docs for enrichment (from the vector store)
                all_docs = store.get_all_documents()

                with console.status("[cyan]Extracting entities via LLM..."):
                    for doc in all_docs:
                        try:
                            graph_doc = enricher.enrich(doc)
                            for entity in graph_doc.entities:
                                graph.add_entity(entity)
                                entities_added += 1
                            for relation in graph_doc.relations:
                                graph.add_relation(relation)
                                relations_added += 1
                        except Exception as e:
                            if verbose:
                                console.print(f"  [dim]Enrich skip: {e}[/dim]")

                console.print(
                    f"  Graph: [cyan]+{entities_added}[/cyan] entities, "
                    f"[cyan]+{relations_added}[/cyan] relations"
                )
        except Exception as e:
            console.print(f"[yellow]Graph enrichment skipped: {e}[/yellow]")
            if verbose:
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]")

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
# Web UI
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
    format: str = typer.Option("text", "--format", "-f",
        help="Output format: text, dot, json, mermaid"),
    query: Optional[str] = typer.Option(None, "--query", "-q",
        help="Query a specific entity by name"),
    depth: int = typer.Option(1, "--depth", "-d", help="Traversal depth for entity query"),
    max_nodes: int = typer.Option(50, "--max-nodes", help="Maximum nodes to display"),
    output: Optional[str] = typer.Option(None, "--output", "-o",
        help="Write output to file instead of stdout"),
):
    """Display knowledge graph or entity relationships.

    Examples:
        ariadne advanced graph
        ariadne advanced graph -f dot > graph.dot
        ariadne advanced graph -q "Albert Einstein" -d 2
        ariadne advanced graph -o graph.html -f html
    """
    from ariadne.graph import GraphStorage
    from ariadne.advanced import GraphVisualizer
    from ariadne.paths import GRAPH_DB_PATH

    graph_path = str(GRAPH_DB_PATH)
    try:
        graph = GraphStorage(db_path=graph_path)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load graph storage: {e}[/yellow]")
        graph = None

    entity_count = len(graph) if graph else 0
    relation_count = len(graph.get_all_relations()) if graph else 0

    # text mode — summary + optional entity query
    if format == "text":
        console.print(Panel(
            f"Entities: [cyan]{entity_count}[/cyan]  |  "
            f"Relations: [cyan]{relation_count}[/cyan]\n"
            f"Graph DB: [dim]{GRAPH_DB_PATH}[/dim]\n\n"
            + ("[dim]No entities yet. Run 'ariadne advanced graph-enrich' "
               "to extract entities from your documents.[/dim]"
               if entity_count == 0 else ""),
            title="Knowledge Graph Summary",
            border_style="cyan",
        ))

        if query and graph:
            entity = graph.get_entity_by_name(query)
            if not entity:
                console.print(f"[yellow]Entity not found: {query}[/yellow]")
            else:
                console.print(f"\n[bold cyan]{entity.name}[/bold cyan] "
                              f"([dim]{entity.entity_type.value}[/dim])")
                if entity.description:
                    console.print(f"  {entity.description}")
                relations = graph.get_relations(entity.entity_id, max_depth=depth)
                if relations:
                    table = Table(title=f"Relations ({len(relations)})", show_lines=True)
                    table.add_column("Type", style="cyan")
                    table.add_column("Connected Entity", style="green")
                    table.add_column("Description", style="dim")
                    for rel in relations:
                        target = graph.get_entity(rel.target_id)
                        target_name = target.name if target else rel.target_id
                        table.add_row(
                            rel.relation_type.value,
                            target_name,
                            rel.description or "",
                        )
                    console.print(table)
                else:
                    console.print("[dim]No relations found.[/dim]")
        return

    # Non-text format — use GraphVisualizer
    if not graph:
        console.print("[red]Graph storage not available.[/red]")
        raise typer.Exit(1)

    vis = GraphVisualizer(graph)

    entity_ids = None
    if query:
        entity = graph.get_entity_by_name(query)
        if entity:
            # Build ego-graph: entity + its neighbors
            entity_ids = {entity.entity_id}
            relations = graph.get_relations(entity.entity_id, max_depth=depth)
            for rel in relations:
                entity_ids.add(rel.target_id)
                entity_ids.add(rel.source_id)

    if format == "dot":
        output_str = vis.to_dot(entity_ids=list(entity_ids) if entity_ids else None,
                                max_nodes=max_nodes)
    elif format == "json":
        output_str = vis.to_json(entity_ids=list(entity_ids) if entity_ids else None,
                                 max_nodes=max_nodes)
    elif format == "mermaid":
        output_str = vis.to_mermaid(entity_ids=list(entity_ids) if entity_ids else None,
                                    max_nodes=max_nodes)
    else:
        console.print(f"[red]Unknown format: {format}[/red]")
        raise typer.Exit(1)

    if output:
        Path(output).write_text(output_str, encoding="utf-8")
        console.print(f"[green]Written {len(output_str)} chars to {output}[/green]")
    else:
        console.print(output_str)


@advanced_app.command("graph-enrich")
def advanced_graph_enrich(
    memory: Optional[str] = typer.Option(None, "--memory", "-m",
        help="Memory system to enrich (default: current default)"),
    limit: int = typer.Option(100, "--limit", "-l",
        help="Maximum documents to process (0=all)"),
    force: bool = typer.Option(False, "--force", "-f",
        help="Re-extract even for documents already with entities"),
    verbose: bool = typer.Option(False, "--verbose", "-v",
        help="Show per-document progress"),
):
    """Extract entities and relations from existing documents into the knowledge graph.

    This backfills the knowledge graph by running LLM entity extraction over
    all documents currently stored in a memory system.

    Examples:
        ariadne advanced graph-enrich
        ariadne advanced graph-enrich -m research -l 50 -v
    """
    from ariadne.graph import GraphStorage, GraphEnricher
    from ariadne.paths import GRAPH_DB_PATH

    cfg = get_config()
    llm = cfg.create_llm()
    if llm is None:
        console.print("[bold red]No LLM configured.[/bold red]")
        console.print("Run 'ariadne config set <provider>' to set up an LLM first.")
        raise typer.Exit(1)

    manager = get_manager()
    store = manager.get_store(memory)
    graph = GraphStorage(db_path=str(GRAPH_DB_PATH))

    # Get documents from vector store
    all_docs = store.get_all_documents(limit=limit if limit > 0 else 10000)
    if not all_docs:
        console.print("[yellow]No documents found in this memory system.[/yellow]")
        return

    target = memory or manager.DEFAULT_COLLECTION
    console.print(f"Memory: [cyan]{target}[/cyan]  |  Documents: [cyan]{len(all_docs)}[/cyan]")
    console.print(f"LLM: [dim]{cfg.get('llm.provider', 'unknown')}[/dim]\n")

    enricher = GraphEnricher(llm=llm)
    entities_added = 0
    relations_added = 0
    errors = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting entities...", total=len(all_docs))

        for doc in all_docs:
            try:
                graph_doc = enricher.enrich(doc)
                for entity in graph_doc.entities:
                    graph.add_entity(entity)
                    entities_added += 1
                for relation in graph_doc.relations:
                    graph.add_relation(relation)
                    relations_added += 1

                if verbose:
                    names = [e.name for e in graph_doc.entities[:3]]
                    console.print(
                        f"  [green]+[/green] {Path(doc.source_path).name}: "
                        f"{len(graph_doc.entities)} entities, "
                        f"{len(graph_doc.relations)} relations"
                        + (f" ({', '.join(names)})" if names else "")
                    )
            except Exception as e:
                errors += 1
                if verbose:
                    console.print(f"  [red]ERROR[/red] {Path(doc.source_path).name}: {e}")

            progress.advance(task)

    # Summary
    console.print()
    console.print(Panel(
        f"Documents processed: [bold green]{len(all_docs)}[/bold green]\n"
        f"Entities added:     [cyan]{entities_added}[/cyan]\n"
        f"Relations added:     [cyan]{relations_added}[/cyan]"
        + (f"\nErrors:              [red]{errors}[/red]" if errors else ""),
        title="Graph Enrich Complete",
        border_style="green" if not errors else "yellow",
    ))
    console.print(
        f"\nView the graph: [dim]ariadne advanced graph[/dim]"
    )


# ═══════════════════════════════════════════
# RAG Pipeline
# ═══════════════════════════════════════════

@rag_app.command("search")
def rag_search(
    query: str = typer.Argument(..., help="Search query"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to return"),
    fetch_k: int = typer.Option(20, "--fetch-k", "-f", help="Candidates to fetch before reranking"),
    alpha: float = typer.Option(0.5, "--alpha", "-a", help="Vector weight (1.0=vector only, 0.0=BM25 only)"),
    no_rerank: bool = typer.Option(False, "--no-rerank", help="Skip reranking stage"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed scores and timing"),
    memory: Optional[str] = typer.Option(None, "--memory", "-m", help="Target memory system"),
):
    """RAG search with hybrid vector+BM25 retrieval, reranking, and citations.

    Examples:
        ariadne rag search "machine learning optimization"
        ariadne rag search "neural networks" -k 10 --verbose
        ariadne rag search "transformer architecture" -a 0.7 --no-rerank
    """
    manager = get_manager()
    store = manager.get_store(memory)

    # Lazy import to avoid hard dependency
    try:
        from ariadne.rag import create_rag_engine
    except ImportError as e:
        console.print("[bold red]RAG dependencies not installed.[/bold red]")
        console.print("Install with: [cyan]pip install rank-bm25 sentence-transformers[/cyan]")
        console.print(f"[dim]Error: {e}[/dim]")
        raise typer.Exit(1)

    target = memory or manager.DEFAULT_COLLECTION
    console.print(f"[Memory: [cyan]{target}[/cyan]] RAG search for: [yellow]{query}[/yellow]")

    with console.status("[cyan]Searching..."):
        engine = create_rag_engine(store, config={
            "rerank": not no_rerank,
            "alpha": alpha,
            "top_k": top_k,
        })

        result = engine.query(
            query=query,
            top_k=top_k,
            fetch_k=fetch_k,
            alpha=alpha,
            include_citations=True,
            include_context=False,
        )

    if result.is_empty:
        console.print("[yellow]No results found.[/yellow]")
        return

    # Display results
    target_system = memory or manager.DEFAULT_COLLECTION
    console.print(f"\n[Memory: [cyan]{target_system}[/cyan]] "
                  f"Found [bold green]{len(result.results)}[/bold green] results:\n")

    for i, res in enumerate(result.results, 1):
        doc = res.document
        # Truncate content for display
        content_preview = doc.content[:400].replace("\n", " ")
        source_type = doc.source_type.value
        title = doc.metadata.get("title", Path(doc.source_path).stem)
        score_bar = engine._score_bar(res.combined_score)

        console.print(f"[{i}] [bold]{title}[/bold] ({source_type}) {score_bar}")
        console.print(f"  {content_preview}...")
        if verbose:
            rerank_method = result.metadata.get("rerank_method", "none")
            console.print(f"  [dim]vec={res.vector_score:.3f} bm25={res.bm25_score:.3f} "
                          f"rank={res.rank} src={res.source} rerank={rerank_method}[/dim]")
        console.print()

    # Citations
    if result.citations:
        console.print(Panel(
            "\n".join(c.format_markdown() for c in result.citations),
            title=f"[cyan]Citations[/cyan] ({len(result.citations)})",
            border_style="cyan",
        ))

    # Timing
    if verbose and result.timings:
        timing_lines = [f"{k}: {v:.1f}ms" for k, v in result.timings.items()]
        console.print(f"[dim]Timing: {', '.join(timing_lines)}[/dim]")


@rag_app.command("rebuild-index")
def rag_rebuild_index(
    memory: Optional[str] = typer.Option(None, "--memory", "-m", help="Target memory system"),
):
    """Rebuild the BM25 index from the vector store.

    Run this after ingesting many new documents to keep keyword search accurate.

    Examples:
        ariadne rag rebuild-index
        ariadne rag rebuild-index -m research
    """
    manager = get_manager()
    store = manager.get_store(memory)

    try:
        from ariadne.rag import create_rag_engine
    except ImportError as e:
        console.print("[bold red]RAG dependencies not installed.[/bold red]")
        console.print(f"[dim]{e}[/dim]")
        raise typer.Exit(1)

    target = memory or manager.DEFAULT_COLLECTION
    with console.status("[cyan]Rebuilding BM25 index..."):
        engine = create_rag_engine(store)
        count = engine.rebuild_bm25_index()

    console.print(f"[bold green][OK][/bold green] Indexed [bold]{count}[/bold] documents in BM25")


@rag_app.command("health")
def rag_health(
    memory: Optional[str] = typer.Option(None, "--memory", "-m", help="Target memory system"),
):
    """Check health of RAG pipeline components.

    Examples:
        ariadne rag health
        ariadne rag health -m research
    """
    manager = get_manager()
    store = manager.get_store(memory)

    try:
        from ariadne.rag import create_rag_engine
    except ImportError as e:
        console.print("[bold red]RAG dependencies not installed.[/bold red]")
        console.print(f"[dim]{e}[/dim]")
        raise typer.Exit(1)

    target = memory or manager.DEFAULT_COLLECTION
    with console.status("[cyan]Checking RAG health..."):
        engine = create_rag_engine(store)
        status = engine.health_check()

    table = Table(title=f"RAG Health — {target}", show_lines=False)
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim")

    component_labels = {
        "bm25": "BM25 Index",
        "reranker": "Reranker",
        "vector_store": "Vector Store",
    }

    for key, info in status.items():
        healthy = info.get("healthy", False)
        label = component_labels.get(key, key)
        status_str = "[green]✓ OK[/green]" if healthy else "[red]✗ FAIL[/red]"
        details = ", ".join(f"{k}={v}" for k, v in info.items() if k != "healthy")
        table.add_row(label, status_str, details)

    console.print(table)


# ═══════════════════════════════════════════
# MCP Server
# ═══════════════════════════════════════════

@mcp_app.command("run")
def mcp_run(
    transport: str = typer.Option("stdio", "--transport", "-t",
        help="Transport mode: stdio (for Claude Code) or http"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host for HTTP mode"),
    port: int = typer.Option(8765, "--port", "-p", help="Port for HTTP mode"),
):
    """Start the Ariadne MCP server.

    This exposes Ariadne's capabilities (search, ingest, graph) as MCP tools
    that can be consumed by Claude Code, Cursor, or any MCP-compatible client.

    Examples:
        ariadne mcp run                          # stdio mode (for Claude Code)
        ariadne mcp run -t http -p 8765         # HTTP mode
        npx @anthropic/mcp-cli ariadne -- ariadne mcp run  # via MCP CLI proxy
    """
    try:
        from ariadne.mcp import AriadneMCPServer
    except ImportError as e:
        console.print("[bold red]MCP module not available.[/bold red]")
        console.print(f"[dim]{e}[/dim]")
        raise typer.Exit(1)

    from ariadne.paths import MEMORIES_DIR, GRAPH_DB_PATH
    from ariadne.config import get_config

    cfg = get_config()
    server = AriadneMCPServer(
        vector_store_path=str(MEMORIES_DIR),
        graph_db_path=str(GRAPH_DB_PATH),
    )

    console.print(f"[cyan]Starting Ariadne MCP Server ({transport} mode)...[/cyan]")
    console.print(f"  Vector store: [dim]{MEMORIES_DIR}[/dim]")
    console.print(f"  Graph DB:     [dim]{GRAPH_DB_PATH}[/dim]")
    console.print(f"  LLM:          [dim]{cfg.get('llm.provider', 'not configured')}[/dim]")
    console.print()

    if transport == "stdio":
        server.run_stdio()
    elif transport == "http":
        console.print(f"[cyan]HTTP server listening on {host}:{port}[/cyan]")
        server.run(host=host, port=port)
    else:
        console.print(f"[red]Unknown transport: {transport}[/red]")
        raise typer.Exit(1)


@mcp_app.command("info")
def mcp_info():
    """Show MCP server configuration and available tools."""
    try:
        from ariadne.mcp import AriadneMCPServer
        from ariadne.mcp.tools import AriadneToolHandler
    except ImportError as e:
        console.print("[bold red]MCP module not available.[/bold red]")
        console.print(f"[dim]{e}[/dim]")
        raise typer.Exit(1)

    from ariadne.paths import MEMORIES_DIR, GRAPH_DB_PATH
    from ariadne.config import get_config

    cfg = get_config()
    server = AriadneMCPServer(
        vector_store_path=str(MEMORIES_DIR),
        graph_db_path=str(GRAPH_DB_PATH),
    )
    handler = AriadneToolHandler(
        vector_store=str(MEMORIES_DIR),
        graph_storage=str(GRAPH_DB_PATH),
    )

    console.print(Panel(
        f"[cyan]ariadne-memory[/cyan] MCP Server\n"
        f"Version: [dim]2.0.0[/dim]  |  Protocol: [dim]2024-11-05[/dim]\n\n"
        f"Vector store: [dim]{MEMORIES_DIR}[/dim]\n"
        f"Graph DB:     [dim]{GRAPH_DB_PATH}[/dim]\n"
        f"LLM:          [dim]{cfg.get('llm.provider', 'not configured')}[/dim]",
        title="MCP Server Info",
        border_style="cyan",
    ))

    tools = handler.list()
    if tools:
        console.print(f"\n[bold cyan]Available tools[/bold cyan] ({len(tools)}):")
        for tool in tools:
            console.print(f"  • [green]{tool['name']}[/green]")
            console.print(f"    [dim]{tool['description'][:80]}...[/dim]")
    else:
        console.print("[yellow]No tools registered.[/yellow]")

    console.print(f"\n[bold cyan]Usage[/bold cyan]:")
    console.print(f"  Claude Code:   [dim]claude --mcp ariadne python -m ariadne.cli mcp run[/dim]")
    console.print(f"  HTTP client:   [dim]POST http://127.0.0.1:8765/mcp[/dim]")


# ═══════════════════════════════════════════
# Web UI
# ═══════════════════════════════════════════

@web_app.command("run", help="Start the web UI server (FastAPI + React frontend).")
def web_run(
    host: str = typer.Option("127.0.0.1", "--host", help="Server host"),
    port: int = typer.Option(8770, "--port", "-p", help="Server port"),
    open_browser: bool = typer.Option(True, "--no-open", help="Don't open browser automatically"),
):
    """Start the Ariadne web UI server."""
    try:
        from ariadne.web import run_server
    except ImportError as e:
        console.print("[bold red]Web UI dependencies not installed.[/bold red]")
        console.print(f"[dim]Please run: pip install fastapi uvicorn pydantic[/dim]")
        console.print(f"[dim]Or: pip install ariadne-memory[web][/dim]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[cyan]Ariadne Web UI[/cyan]\n"
        f"Starting at [bold]http://{host}:{port}[/bold]\n"
        f"Frontend: [dim]React SPA[/dim]  |  API: [dim]FastAPI[/dim]",
        title="Web Server",
        border_style="cyan",
    ))

    if open_browser:
        import webbrowser
        import threading
        threading.Timer(1.5, lambda: webbrowser.open(f"http://{host}:{port}")).start()

    run_server(host=host, port=port)


@web_app.command("info", help="Show web UI status and configuration.")
def web_info():
    """Show web UI configuration and status."""
    try:
        from ariadne.web import run_server
        web_available = True
    except ImportError:
        web_available = False

    static_dir = Path(__file__).parent / "web" / "static"
    has_frontend = static_dir.exists()

    console.print(Panel(
        f"[cyan]Ariadne Web UI[/cyan]\n\n"
        f"Backend:       [cyan]FastAPI + uvicorn[/cyan]\n"
        f"Frontend:      [cyan]React SPA[/cyan]\n"
        f"Static dir:    [dim]{static_dir if has_frontend else 'not found'}[/dim]\n"
        f"Available:     [{'green' if web_available else 'red'}]{'Yes' if web_available else 'No'}[/]",
        title="Web UI Info",
        border_style="cyan",
    ))

    if not web_available:
        console.print("\n[yellow]To enable web UI, install:[/yellow]")
        console.print("[dim]  pip install fastapi uvicorn pydantic[/dim]")

    if not has_frontend:
        console.print("\n[yellow]Frontend not built yet.[/yellow]")
        console.print("[dim]  See: ariadne/web/frontend/ for React source[/dim]")


# ═══════════════════════════════════════════
# LLM Wiki
# ═══════════════════════════════════════════

@wiki_app.command("init", help="Initialize a new LLM Wiki project.")
def wiki_init(
    path: str = typer.Argument(".", help="Project directory path"),
    name: str = typer.Option("", "--name", "-n", help="Wiki project name"),
):
    """Create a new LLM Wiki project with the standard directory structure."""
    from ariadne.wiki import init_wiki_project
    from ariadne.wiki.models import WikiProject

    abs_path = os.path.abspath(path)
    console.print(Panel(
        f"[cyan]Initializing LLM Wiki[/cyan]\n"
        f"Path: [bold]{abs_path}[/bold]",
        title="Wiki Init",
        border_style="cyan",
    ))

    try:
        project = init_wiki_project(abs_path, name=name)
        console.print(f"[green]✓[/green] Created wiki project at [bold]{abs_path}[/bold]")
        console.print("\nStructure:")
        console.print("  [dim]raw/sources/[/dim]     — Drop your source files here")
        console.print("  [dim]raw/assets/[/dim]      — Images and attachments")
        console.print("  [dim]wiki/[/dim]             — LLM-generated wiki pages")
        console.print("  [dim]schema.md[/dim]         — Wiki structure rules")
        console.print("  [dim]purpose.md[/dim]        — Wiki goals and purpose")
        console.print("\n[dim]Next: ariadne wiki ingest <source-file>[/dim]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@wiki_app.command("ingest", help="Ingest a source file into the wiki (two-step CoT).")
def wiki_ingest(
    source: str = typer.Argument(..., help="Source file path"),
    project: str = typer.Option(".", "--project", "-p", help="Wiki project directory"),
    language: str = typer.Option("", "--lang", "-l", help="Output language (e.g. 'Chinese', 'English')"),
    folder_context: str = typer.Option("", "--folder", "-f", help="Folder context hint for LLM"),
    skip_cache: bool = typer.Option(False, "--skip-cache", help="Skip cache check"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """
    Ingest a source document into the LLM Wiki using two-step Chain-of-Thought.

    Step 1: LLM analyzes the source document
    Step 2: LLM generates wiki pages (entities, concepts, source summary)
    """
    from ariadne.wiki import ingest_source, init_wiki_project
    from ariadne.wiki.models import WikiProject

    source_path = os.path.abspath(source)
    project_path = os.path.abspath(project)

    if not os.path.exists(source_path):
        console.print(f"[red]Source file not found:[/red] {source_path}")
        raise typer.Exit(1)

    # Auto-init if project doesn't have wiki structure
    if not os.path.exists(os.path.join(project_path, "wiki")):
        console.print("[dim]Project not initialized. Auto-initializing...[/dim]")
        init_wiki_project(project_path)

    wiki_project = WikiProject(root_path=project_path)

    console.print(Panel(
        f"[cyan]LLM Wiki Ingest[/cyan]\n"
        f"Source: [bold]{os.path.basename(source_path)}[/bold]\n"
        f"Project: [dim]{project_path}[/dim]",
        title="Wiki Ingest",
        border_style="cyan",
    ))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Step 1/2: Analyzing source...", total=None)

        result = ingest_source(
            project=wiki_project,
            source_path=source_path,
            language=language,
            folder_context=folder_context,
            skip_cache=skip_cache,
        )

        progress.update(task, description="Done")

    if result.cached:
        console.print(f"[yellow]⚡ Cached[/yellow] — {len(result.pages_written)} pages from previous ingest")
    else:
        console.print(f"[green]✓[/green] Generated [bold]{len(result.pages_written)}[/bold] wiki page(s)")

    if verbose and result.pages_written:
        for p in result.pages_written:
            console.print(f"  [dim]→ {p}[/dim]")

    if result.review_items:
        console.print(f"[yellow]⚠[/yellow]  {len(result.review_items)} item(s) flagged for review")

    if result.warnings:
        for w in result.warnings:
            console.print(f"[yellow]Warning:[/yellow] {w}")


@wiki_app.command("ingest-vault", help="Import an Obsidian vault into the wiki project.")
def wiki_ingest_vault(
    vault: str = typer.Argument(..., help="Path to Obsidian vault directory"),
    project: str = typer.Option(".", "--project", "-p", help="Wiki project directory"),
    ingest: bool = typer.Option(False, "--ingest", help="Run LLM ingest after importing"),
    language: str = typer.Option("", "--lang", "-l", help="Output language"),
):
    """Import an Obsidian vault into the wiki project's raw/sources/ directory."""
    from ariadne.wiki import import_obsidian_vault
    from ariadne.wiki.models import WikiProject

    vault_path = os.path.abspath(vault)
    project_path = os.path.abspath(project)

    if not os.path.isdir(vault_path):
        console.print(f"[red]Vault directory not found:[/red] {vault_path}")
        raise typer.Exit(1)

    wiki_project = WikiProject(root_path=project_path)

    console.print(Panel(
        f"[cyan]Obsidian Vault Import[/cyan]\n"
        f"Vault: [bold]{vault_path}[/bold]\n"
        f"Project: [dim]{project_path}[/dim]\n"
        f"LLM Ingest: [bold]{'Yes' if ingest else 'No'}[/bold]",
        title="Wiki Vault Import",
        border_style="cyan",
    ))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Importing vault...", total=None)
        result = import_obsidian_vault(
            vault_path=vault_path,
            project=wiki_project,
            copy_to_raw=True,
            ingest_immediately=ingest,
            language=language,
        )

    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Imported [bold]{len(result['imported_files'])}[/bold] files")
    if result['skipped_files']:
        console.print(f"[dim]Skipped {len(result['skipped_files'])} files[/dim]")
    if result['errors']:
        for e in result['errors']:
            console.print(f"[yellow]Warning:[/yellow] {e}")


@wiki_app.command("query", help="Ask a question against the wiki knowledge base.")
def wiki_query(
    question: str = typer.Argument(..., help="Question to ask"),
    project: str = typer.Option(".", "--project", "-p", help="Wiki project directory"),
    language: str = typer.Option("", "--lang", "-l", help="Output language"),
    save: bool = typer.Option(False, "--save", "-s", help="Save answer to wiki/queries/"),
):
    """Query the wiki knowledge base and get a cited answer."""
    from ariadne.wiki import query_wiki
    from ariadne.wiki.models import WikiProject

    project_path = os.path.abspath(project)
    wiki_project = WikiProject(root_path=project_path)

    console.print(Panel(
        f"[cyan]Wiki Query[/cyan]\n"
        f"[bold]{question}[/bold]",
        title="Wiki Query",
        border_style="cyan",
    ))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Searching wiki and generating answer...", total=None)
        result = query_wiki(
            project=wiki_project,
            question=question,
            language=language,
            save_to_wiki=save,
        )

    console.print("\n" + result.answer)

    if result.cited_pages:
        console.print(f"\n[dim]Sources: {', '.join(result.cited_pages[:5])}[/dim]")

    if result.saved_to:
        console.print(f"\n[green]✓[/green] Saved to [bold]{result.saved_to}[/bold]")


@wiki_app.command("lint", help="Check wiki health (structural + semantic).")
def wiki_lint(
    project: str = typer.Option(".", "--project", "-p", help="Wiki project directory"),
    structural_only: bool = typer.Option(False, "--structural", help="Only run structural checks (no LLM)"),
    language: str = typer.Option("", "--lang", "-l", help="Output language for semantic lint"),
):
    """Run structural and semantic lint checks on the wiki."""
    from ariadne.wiki import run_structural_lint, run_semantic_lint, run_full_lint
    from ariadne.wiki.models import WikiProject, LintSeverity

    project_path = os.path.abspath(project)
    wiki_project = WikiProject(root_path=project_path)

    console.print(Panel(
        f"[cyan]Wiki Lint[/cyan]\n"
        f"Project: [dim]{project_path}[/dim]\n"
        f"Mode: [bold]{'Structural only' if structural_only else 'Full (structural + semantic)'}[/bold]",
        title="Wiki Lint",
        border_style="cyan",
    ))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Analyzing wiki...", total=None)
        if structural_only:
            results = run_structural_lint(wiki_project)
        else:
            results = run_full_lint(wiki_project, language=language)

    if not results:
        console.print("[green]✓[/green] Wiki looks healthy! No issues found.")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Severity", style="bold", width=10)
    table.add_column("Type", width=18)
    table.add_column("Page", width=30)
    table.add_column("Detail")

    for r in results:
        severity_style = "red" if r.severity == LintSeverity.WARNING else "yellow"
        table.add_row(
            f"[{severity_style}]{r.severity.value}[/{severity_style}]",
            r.issue_type.value,
            r.page,
            r.detail[:80],
        )

    console.print(table)
    warnings = sum(1 for r in results if r.severity == LintSeverity.WARNING)
    infos = len(results) - warnings
    console.print(f"\nTotal: [red]{warnings} warning(s)[/red], [yellow]{infos} info(s)[/yellow]")


@wiki_app.command("list", help="List all wiki pages.")
def wiki_list(
    project: str = typer.Option(".", "--project", "-p", help="Wiki project directory"),
):
    """List all pages in the wiki."""
    from ariadne.wiki import list_wiki_pages
    from ariadne.wiki.models import WikiProject

    project_path = os.path.abspath(project)
    wiki_project = WikiProject(root_path=project_path)

    pages = list_wiki_pages(wiki_project.wiki_dir)
    if not pages:
        console.print("[dim]No wiki pages found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", width=4)
    table.add_column("Page", width=50)
    table.add_column("Type", width=12)

    for i, path in enumerate(pages, 1):
        from ariadne.wiki import read_wiki_page
        page = read_wiki_page(path)
        rel = os.path.relpath(path, wiki_project.wiki_dir).replace("\\", "/")
        page_type = page.frontmatter.page_type.value if page else "-"
        table.add_row(str(i), rel, page_type)

    console.print(table)
    console.print(f"\n[dim]{len(pages)} page(s) total[/dim]")


# ═══════════════════════════════════════════
# Session Memory
# ═══════════════════════════════════════════

@session_app.command("start")
def session_start(
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
    platform: str = typer.Option("generic", "--platform", help="Platform: claude_code, openclaw, cursor, generic"),
):
    """Start a new session and display prior context."""
    from ariadne.session import get_manager, Platform
    project_path = os.path.abspath(project)
    try:
        plat = Platform(platform)
    except ValueError:
        plat = Platform.GENERIC

    mgr = get_manager()
    session, context = mgr.start_session(project_path=project_path, platform=plat)

    console.print(Panel(
        f"Session ID: [bold cyan]{session.id}[/bold cyan]\n"
        f"Project: [dim]{project_path}[/dim]\n"
        f"Platform: [dim]{plat.value}[/dim]",
        title="Session Started",
        border_style="green",
    ))

    if context:
        console.print("\n[cyan]Prior context injected:[/cyan]")
        console.print(Panel(context[:1000] + ("..." if len(context) > 1000 else ""),
                             border_style="dim"))
    else:
        console.print("[dim]No prior session history found.[/dim]")


@session_app.command("end")
def session_end(
    session_id: str = typer.Argument(..., help="Session ID to end"),
    no_summary: bool = typer.Option(False, "--no-summary", help="Skip LLM summarization"),
):
    """End a session and generate a summary."""
    from ariadne.session import get_manager
    mgr = get_manager()

    with console.status("Ending session and generating summary..."):
        summary = mgr.end_session(session_id, generate_summary=not no_summary)

    if summary:
        console.print(Panel(
            f"[bold]Narrative:[/bold] {summary.narrative}\n\n"
            + (f"[bold]Key decisions:[/bold] {', '.join(summary.key_decisions)}\n" if summary.key_decisions else "")
            + (f"[bold]Files:[/bold] {', '.join(summary.files_changed[:5])}" if summary.files_changed else ""),
            title="[cyan]Session Summary[/cyan]",
            border_style="cyan",
        ))
    else:
        console.print(f"[green]✓[/green] Session [dim]{session_id}[/dim] ended.")


@session_app.command("list")
def session_list(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Filter by project"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of sessions"),
):
    """List recent sessions."""
    from ariadne.session import get_manager
    mgr = get_manager()

    project_path = os.path.abspath(project) if project else None
    sessions = mgr.list_sessions(project_path=project_path, limit=limit)

    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    table = Table(title="Recent Sessions", show_lines=False)
    table.add_column("Date", style="dim", width=12)
    table.add_column("Platform", style="cyan", width=12)
    table.add_column("Status", width=10)
    table.add_column("Summary")

    for s in sessions:
        date = s.started_at[:10]
        status_color = {"active": "green", "completed": "blue", "summarized": "cyan"}.get(s.status.value, "dim")
        summary = (s.summary[:60] + "...") if s.summary and len(s.summary) > 60 else (s.summary or "[dim]–[/dim]")
        table.add_row(date, s.platform.value, f"[{status_color}]{s.status.value}[/{status_color}]", summary)

    console.print(table)


@session_app.command("search")
def session_search(
    query: str = typer.Argument(..., help="Search query"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Filter by project path"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of results"),
):
    """Search session memory for relevant observations."""
    from ariadne.session import get_manager
    mgr = get_manager()

    project_path = os.path.abspath(project) if project else None

    with console.status("Searching session memory..."):
        results = mgr.search_observations(query=query, project_path=project_path, limit=limit)

    if not results:
        console.print("[yellow]No matching observations found.[/yellow]")
        return

    console.print(f"\nFound [bold green]{len(results)}[/bold green] results:\n")
    for obs, score in results:
        console.print(f"[{obs.obs_type.value.upper()}] {obs.summary}")
        console.print(f"  [dim]Score: {score:.3f} · {obs.created_at[:10]}[/dim]")
        if obs.files:
            console.print(f"  [dim]Files: {', '.join(obs.files[:3])}[/dim]")
        console.print()


@session_app.command("stats")
def session_stats():
    """Show session memory statistics."""
    from ariadne.session import get_manager
    mgr = get_manager()
    stats = mgr.stats()

    console.print(Panel(
        f"Sessions:     [cyan]{stats.get('sessions', 0)}[/cyan]\n"
        f"Observations: [cyan]{stats.get('observations', 0)}[/cyan]\n"
        f"Active:       [green]{stats.get('active_sessions', 0)}[/green]\n"
        f"Pending msgs: [dim]{stats.get('pending_messages', 0)}[/dim]",
        title="Session Memory Stats",
        border_style="cyan",
    ))


@session_app.command("recent")
def session_recent(
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
    limit: int = typer.Option(3, "--limit", "-n", help="Number of sessions to show"),
):
    """Show recent work context from session memory."""
    from ariadne.session import get_manager
    mgr = get_manager()
    project_path = os.path.abspath(project)
    text = mgr.recent_context_text(project_path=project_path, limit=limit)
    console.print(Panel(text, title="[cyan]Recent Work Context[/cyan]", border_style="cyan"))


# ═══════════════════════════════════════════
# Hook Runner
# ═══════════════════════════════════════════

@hook_app.command("run")
def hook_run(
    event: str = typer.Option(..., "--event", "-e",
        help="Hook event: session_start, user_prompt, post_tool, stop, session_end"),
    platform: Optional[str] = typer.Option(None, "--platform", "-p",
        help="Platform: claude_code, openclaw, cursor, windsurf, generic"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Disable LLM observation analysis"),
):
    """
    Run an Ariadne session memory hook (reads JSON from stdin).

    This command is designed to be called by IDE/AI platform lifecycle hooks.

    Example Claude Code configuration (~/.claude/settings.json):

        {
          "hooks": {
            "SessionStart":     [{"hooks": [{"type": "command", "command": "ariadne hook run --event session_start"}]}],
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "ariadne hook run --event user_prompt"}]}],
            "PostToolUse":      [{"hooks": [{"type": "command", "command": "ariadne hook run --event post_tool"}]}],
            "Stop":             [{"hooks": [{"type": "command", "command": "ariadne hook run --event stop"}]}]
          }
        }

    Example usage from command line:

        echo '{"session_id": "abc", "cwd": "/my/project"}' | ariadne hook run --event session_start
    """
    from ariadne.hooks.runner import run_hook
    result = run_hook(event=event, platform=platform, use_llm=not no_llm)

    if result.context:
        # Write context to stdout — this is what the IDE injects
        sys.stdout.write(result.context)
        sys.stdout.flush()

    raise typer.Exit(result.exit_code)


@hook_app.command("setup")
def hook_setup(
    platform: str = typer.Argument("claude_code",
        help="Platform to configure: claude_code, cursor"),
    show_only: bool = typer.Option(False, "--show", help="Show configuration without writing"),
):
    """Generate hook configuration for your AI platform."""
    ariadne_cmd = "ariadne hook run"

    configs = {
        "claude_code": {
            "file": "~/.claude/settings.json",
            "config": {
                "hooks": {
                    "SessionStart":     [{"hooks": [{"type": "command", "command": f"{ariadne_cmd} --event session_start"}]}],
                    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": f"{ariadne_cmd} --event user_prompt"}]}],
                    "PostToolUse":      [{"hooks": [{"type": "command", "command": f"{ariadne_cmd} --event post_tool"}]}],
                    "Stop":             [{"hooks": [{"type": "command", "command": f"{ariadne_cmd} --event stop"}]}],
                }
            }
        },
        "cursor": {
            "file": "~/.cursor/settings.json",
            "config": {
                "ariadne.hooks": {
                    "session_start": f"{ariadne_cmd} --event session_start --platform cursor",
                    "post_tool":     f"{ariadne_cmd} --event post_tool --platform cursor",
                    "stop":          f"{ariadne_cmd} --event stop --platform cursor",
                }
            }
        }
    }

    cfg = configs.get(platform)
    if not cfg:
        console.print(f"[red]Unknown platform: {platform}[/red]")
        console.print(f"Supported: {', '.join(configs.keys())}")
        raise typer.Exit(1)

    import json as _json
    config_str = _json.dumps(cfg["config"], indent=2)

    console.print(Panel(
        f"[bold]Target file:[/bold] {cfg['file']}\n\n"
        f"[bold]Configuration:[/bold]\n{config_str}",
        title=f"[cyan]Hook Setup: {platform}[/cyan]",
        border_style="cyan",
    ))

    if not show_only:
        console.print(
            f"\n[dim]Add the above to [bold]{cfg['file']}[/bold] to enable session memory hooks.[/dim]"
        )
        console.print(
            "[dim]For MCP-based platforms (OpenClaw), use ariadne_session_start / "
            "ariadne_session_observe tools directly.[/dim]"
        )


# ═══════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════

def main():
    """Entry point for the Ariadne CLI."""
    from ariadne.logging import get_session_logger
    session_log = get_session_logger()
    session_log.start("cli", args=" ".join(sys.argv[1:]))
    try:
        app()
    finally:
        session_log.shutdown()


if __name__ == "__main__":
    main()

