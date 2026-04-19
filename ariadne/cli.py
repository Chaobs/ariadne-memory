"""
Ariadne CLI — Command-line interface for the Ariadne memory system.

Supports:
- Single and multi-memory system operations
- File ingestion with progress
- Semantic search
- Memory system management (create, rename, delete, merge)
- LLM configuration and testing
- Advanced features (summary, graph, export)
"""

import click
import sys
import os
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

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # Progress bar disabled if tqdm not installed

from ariadne import __version__
from ariadne.memory import VectorStore, MemoryManager, get_manager
from ariadne.ingest import (
    MarkdownIngestor,
    WordIngestor,
    PPTIngestor,
    PDFIngestor,
    TxtIngestor,
    ConversationIngestor,
    MindMapIngestor,
    CodeIngestor,
    ExcelIngestor,
    CsvIngestor,
)
from ariadne.config import (
    AriadneConfig,
    get_config,
    reload_config,
    print_config_info,
    list_supported_providers,
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
    ".xlsx": ExcelIngestor,
    ".xls": ExcelIngestor,
    ".csv": CsvIngestor,
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


# === Memory System Management ===

@main.group()
def memory():
    """Memory system management commands."""
    pass


@memory.command("list")
def memory_list():
    """List all memory systems."""
    manager = get_manager()
    systems = manager.list_systems()
    
    click.secho("\nAll Memory Systems:", fg="cyan")
    click.secho("="*50)
    
    for s in systems:
        info = manager.get_info(s.name)
        count = info.get("document_count", "?") if info else "?"
        marker = " * " if s.name == manager.DEFAULT_COLLECTION else "   "
        click.echo(f"{marker}{s.name}: {count} documents")
        if s.description:
            click.echo(f"    {s.description}")
    
    click.secho(f"\nTotal: {len(systems)} memory system(s)")


@memory.command("create")
@click.argument("name")
@click.option("--description", "-d", default="", help="Description for the memory system")
def memory_create(name: str, description: str):
    """Create a new memory system."""
    manager = get_manager()
    try:
        manager.create(name, description)
        click.secho(f"[OK] Created: {name}", fg="green")
    except ValueError as e:
        click.secho(f"[ERROR] {e}", fg="red")
        sys.exit(1)


@memory.command("rename")
@click.argument("old_name")
@click.argument("new_name")
def memory_rename(old_name: str, new_name: str):
    """Rename a memory system."""
    manager = get_manager()
    try:
        manager.rename(old_name, new_name)
        click.secho(f"[OK] Renamed: {old_name} -> {new_name}", fg="green")
    except ValueError as e:
        click.secho(f"[ERROR] {e}", fg="red")
        sys.exit(1)


@memory.command("delete")
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def memory_delete(name: str, yes: bool):
    """Delete a memory system."""
    manager = get_manager()
    
    if name == manager.DEFAULT_COLLECTION:
        click.secho("[ERROR] Cannot delete the default memory system", fg="red")
        sys.exit(1)
    
    if not yes:
        click.confirm(f"Delete '{name}'? This cannot be undone.", abort=True)
    
    try:
        manager.delete(name, confirm=False)
        click.secho(f"[OK] Deleted: {name}", fg="green")
    except ValueError as e:
        click.secho(f"[ERROR] {e}", fg="red")
        sys.exit(1)


@memory.command("merge")
@click.argument("source_names", nargs=-1, required=True)
@click.argument("new_name")
@click.option("--delete", "-d", is_flag=True, help="Delete source systems after merge")
def memory_merge(source_names: tuple, new_name: str, delete: bool):
    """Merge multiple memory systems into a new one."""
    manager = get_manager()
    
    sources = list(source_names)
    try:
        manager.merge(sources, new_name, delete_sources=delete)
        click.secho(f"[OK] Merged into: {new_name}", fg="green")
    except ValueError as e:
        click.secho(f"[ERROR] {e}", fg="red")
        sys.exit(1)


@memory.command("info")
@click.argument("name", required=False)
def memory_info(name: str):
    """Show information about a memory system."""
    manager = get_manager()
    
    if name is None:
        name = manager.DEFAULT_COLLECTION
    
    info = manager.get_info(name)
    if not info:
        click.secho(f"[ERROR] Memory system '{name}' not found", fg="red")
        sys.exit(1)
    
    click.secho(f"\nMemory System: {name}", fg="cyan")
    click.secho("="*50)
    click.echo(f"Path: {info['path']}")
    click.echo(f"Documents: {info.get('document_count', 0)}")
    click.echo(f"Created: {info.get('created_at', 'N/A')[:10]}")
    click.echo(f"Updated: {info.get('updated_at', 'N/A')[:10]}")
    if info.get('description'):
        click.echo(f"Description: {info['description']}")


@memory.command("clear")
@click.argument("name", required=False)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def memory_clear(name: str, yes: bool):
    """Clear all documents from a memory system."""
    manager = get_manager()
    
    if name is None:
        name = manager.DEFAULT_COLLECTION
    
    if not yes:
        click.confirm(f"Clear all documents from '{name}'?", abort=True)
    
    try:
        manager.clear(name)
        click.secho(f"[OK] Cleared: {name}", fg="green")
    except Exception as e:
        click.secho(f"[ERROR] {e}", fg="red")
        sys.exit(1)


@memory.command("export")
@click.argument("name")
@click.argument("output_path", type=click.Path())
def memory_export(name: str, output_path: str):
    """Export a memory system to a directory (for backup or sharing).
    
    Example:
        ariadne memory export research ./backup/research_memory
    """
    manager = get_manager()
    
    try:
        path = manager.export(name, output_path)
        click.secho(f"[OK] Exported '{name}' to: {path}", fg="green")
    except ValueError as e:
        click.secho(f"[ERROR] {e}", fg="red")
        sys.exit(1)


@memory.command("import")
@click.argument("source_path", type=click.Path(exists=True))
@click.argument("name")
def memory_import(source_path: str, name: str):
    """Import a memory system from a previously exported directory.
    
    Example:
        ariadne memory import ./backup/research_memory imported_research
    """
    manager = get_manager()
    
    try:
        manager.import_memory(source_path, name)
        click.secho(f"[OK] Imported '{source_path}' as: {name}", fg="green")
    except ValueError as e:
        click.secho(f"[ERROR] {e}", fg="red")
        sys.exit(1)


# === File Ingestion ===

@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--recursive", "-r", is_flag=True, help="Recursively ingest all supported files")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--batch-size", "-b", default=100, help="Batch size for vector storage")
@click.option("--memory", "-m", default=None, help="Target memory system name")
def ingest(path: str, recursive: bool, verbose: bool, batch_size: int, memory: str):
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
        for ext in INGESTORS:
            if recursive:
                files.extend(target.rglob(f"*{ext}"))
            else:
                files.extend(target.glob(f"*{ext}"))
    else:
        click.secho(f"Error: {path} is not a valid file or directory", fg="red")
        sys.exit(1)

    if not files:
        click.secho("No supported files found.", fg="yellow")
        return
    
    target_system = memory or manager.DEFAULT_COLLECTION
    click.echo(f"Target: {target_system}")

    # Batch accumulation for progress bar
    batch_docs = []

    # Create progress bar if tqdm is available
    iterator = tqdm(files, desc="Ingesting", unit="file", disable=tqdm is None)

    for file_path in iterator:
        ingestor_cls = resolve_ingestor(file_path)
        if ingestor_cls is None:
            if verbose:
                click.echo(f"  {Fore.YELLOW}SKIP{Fore.RESET}  {file_path} (unsupported format)")
            continue

        try:
            ingestor = ingestor_cls()
            docs = ingestor.ingest(str(file_path))
            if docs:
                batch_docs.extend(docs)
                files_processed += 1
                docs_created += len(docs)

                # Flush batch when full
                if len(batch_docs) >= batch_size:
                    store.add(batch_docs)
                    batch_docs = []

                if verbose:
                    click.echo(f"  {Fore.GREEN}ADD{Fore.RESET}   {file_path.name} -> {len(docs)} chunks")
        except Exception as e:
            errors.append((str(file_path), str(e)))
            if verbose:
                click.echo(f"  {Fore.RED}ERROR{Fore.RESET}  {file_path.name}: {e}")

    # Flush remaining docs
    if batch_docs:
        store.add(batch_docs)

    # Summary
    click.secho(f"\n{'='*50}", fg="cyan")
    click.secho(f"Done! Processed {files_processed} files, created {docs_created} documents.", fg="green")
    if errors:
        click.secho(f"Errors: {len(errors)}", fg="red")
        if verbose:
            for path, err in errors:
                click.echo(f"  - {path}: {err}")


# === Search ===

@main.command()
@click.argument("query", type=str)
@click.option("--top-k", "-k", default=5, help="Number of results to return")
@click.option("--verbose", "-v", is_flag=True, help="Show document metadata")
@click.option("--memory", "-m", default=None, help="Target memory system name")
def search(query: str, top_k: int, verbose: bool, memory: str):
    """Search a memory system."""
    manager = get_manager()
    store = manager.get_store(memory)
    results = store.search(query, top_k=top_k)

    if not results:
        click.secho("No results found.", fg="yellow")
        return

    target_system = memory or manager.DEFAULT_COLLECTION
    click.secho(f"\n[Memory: {target_system}] Found {len(results)} results:\n", fg="green")
    
    for i, (doc, score) in enumerate(results, 1):
        click.secho(f"[{i}] (score: {score:.4f})", fg="cyan")
        click.echo(doc.content[:300])
        if verbose and doc.metadata:
            click.echo(f"    Source: {doc.metadata.get('source', 'unknown')} | "
                       f"Type: {doc.metadata.get('source_type', 'unknown')}")
        click.echo()


# === Info ===

@main.command()
@click.option("--stats", is_flag=True, help="Show collection statistics")
@click.option("--memory", "-m", default=None, help="Target memory system name")
def info(stats: bool, memory: str):
    """Show information about the Ariadne memory system."""
    manager = get_manager()
    target = memory or manager.DEFAULT_COLLECTION
    store = manager.get_store(target)
    
    click.echo(f"Ariadne Memory System v{__version__}")
    click.echo(f"Current Memory: {target}")
    click.echo(f"Storage backend: ChromaDB")
    click.echo(f"Data directory: {store.persist_dir}")

    if stats:
        try:
            count = store.count()
            click.echo(f"Documents indexed: {count}")
        except Exception:
            click.echo("Documents indexed: (unable to retrieve)")


# === GUI ===

@main.command()
def gui():
    """Launch the graphical user interface."""
    try:
        from ariadne.gui import main as gui_main
        gui_main()
    except ImportError:
        click.secho("Error: tkinter is not available on this system.", fg="red")
        click.secho("GUI requires a graphical environment (Windows/macOS/Linux desktop).", fg="yellow")
        sys.exit(1)
    except Exception as e:
        click.secho(f"Error launching GUI: {e}", fg="red")
        sys.exit(1)


# === Config Management ===

@main.group()
def config():
    """Configuration management commands."""
    pass


@config.command("show")
def config_show():
    """Show current configuration."""
    cfg = get_config()
    print_config_info(cfg)


@config.command("list-providers")
def config_list_providers():
    """List all supported LLM providers."""
    list_supported_providers()


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str):
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
    
    click.secho(f"[OK] Set {key} = {value}", fg="green")
    click.echo(f"Config saved to: {cfg.config_dir / 'config.json'}")


@config.command("get")
@click.argument("key")
def config_get(key: str):
    """Get a configuration value."""
    cfg = get_config()
    value = cfg.get(key)
    if value is not None:
        click.echo(f"{key} = {value}")
    else:
        click.secho(f"Key '{key}' not found", fg="yellow")


@config.command("test")
def config_test():
    """Test LLM configuration."""
    cfg = get_config()
    
    click.echo("Testing LLM configuration...")
    success, message = cfg.test_llm()
    
    if success:
        click.secho(f"[OK] {message}", fg="green")
    else:
        click.secho(f"[FAIL] {message}", fg="red")
        sys.exit(1)


@config.command("set-api-key")
@click.argument("provider")
@click.argument("api_key")
@click.option("--env", "-e", is_flag=True, help="Save to environment variable instead of config file")
def config_set_api_key(provider: str, api_key: str, env: bool):
    """Set API key for a provider.
    
    Examples:
        ariadne config set-api-key deepseek sk-xxxxx
        ariadne config set-api-key openai sk-xxxxx -e
    """
    provider = provider.lower()
    
    if env:
        env_var = f"{provider.upper()}_API_KEY"
        os.environ[env_var] = api_key
        click.secho(f"[OK] Set {env_var} (will apply for this session)", fg="green")
    else:
        cfg = get_config()
        cfg.set("llm.provider", provider)
        cfg.set("llm.api_key", api_key)
        cfg.save_user()
        
        config_path = cfg.save_user()
        click.secho(f"[OK] Set API key for {provider}", fg="green")
        click.echo(f"Config saved to: {config_path}")


# === Advanced Features ===

@main.group()
def advanced():
    """Advanced features commands (requires LLM configuration)."""
    pass


@advanced.command("summarize")
@click.argument("query", required=False)
@click.option("--memory", "-m", default=None, help="Target memory system name")
@click.option("--output-lang", "-l", default=None, help="Output language (zh_CN, en, fr, etc.)")
def advanced_summarize(query: str, memory: str, output_lang: str):
    """Summarize search results or entire memory.
    
    Examples:
        ariadne advanced summarize
        ariadne advanced summarize "machine learning"
        ariadne advanced summarize -m research -l en
    """
    cfg = get_config()
    
    if not cfg.get("advanced.enable_summary"):
        click.secho("Summary feature is disabled. Enable with: ariadne config set advanced.enable_summary true", fg="yellow")
        sys.exit(1)
    
    llm = cfg.create_llm()
    if llm is None:
        click.secho("No LLM configured. Please set up your API key first.", fg="red")
        click.echo("Run 'ariadne config set-api-key <provider> <key>' to configure.")
        sys.exit(1)
    
    manager = get_manager()
    store = manager.get_store(memory)
    target = memory or manager.DEFAULT_COLLECTION
    
    if query:
        click.echo(f"Searching memory '{target}' for: {query}")
        results = store.search(query, top_k=10)
        
        if not results:
            click.secho("No results found.", fg="yellow")
            return
        
        click.echo(f"Found {len(results)} results, generating summary...")
        
        # Prepare context
        context = "\n\n".join([f"[Document {i+1}]\n{doc.content[:500]}" for i, (doc, _) in enumerate(results)])
        
        # Get output language
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
        click.echo(f"Generating summary of memory '{target}'...")
        count = store.count()
        
        if count == 0:
            click.secho("Memory is empty.", fg="yellow")
            return
        
        click.echo(f"Memory contains {count} documents. Note: Full summary requires processing all documents.")
        click.secho("Please use a search query for targeted summaries.", fg="yellow")
        return
    
    try:
        response = llm.chat(prompt)
        click.secho("\n=== Summary ===\n", fg="cyan")
        click.echo(response.content)
    except Exception as e:
        click.secho(f"Error generating summary: {e}", fg="red")
        sys.exit(1)


@advanced.command("graph")
@click.option("--memory", "-m", default=None, help="Target memory system name")
@click.option("--format", "-f", default="text", type=click.Choice(["text", "dot", "json"]), help="Output format")
def advanced_graph(memory: str, format: str):
    """Display knowledge graph or entity relationships.
    
    Examples:
        ariadne advanced graph
        ariadne advanced graph -m research -f dot
    """
    if format == "text":
        click.echo("Knowledge Graph Feature")
        click.echo("=" * 40)
        click.echo("This feature extracts entities and relationships from your memory.")
        click.echo("For visualization, use the GUI or export to DOT format.")
        click.echo("\nNote: Full graph extraction requires LLM configuration.")
        click.echo("Run 'ariadne config test' to verify your setup.")
    elif format == "dot":
        click.echo("// DOT format for knowledge graph visualization")
        click.echo("// Use with Graphviz: dot -Tpng graph.dot -o graph.png")
        click.echo("digraph KnowledgeGraph {")
        click.echo('    rankdir=LR;')
        click.echo('    node [shape=box];')
        click.echo("    // Configure LLM to enable entity extraction")
        click.echo("}")
    else:
        import json
        click.echo(json.dumps({"status": "graph_feature", "note": "Configure LLM for entity extraction"}, indent=2))


if __name__ == "__main__":
    main()
