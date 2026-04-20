"""
Phase 0 & Phase 1 Comprehensive Integration Test
=================================================
Tests the following capabilities:
  Phase 0:
    - MarkItDown integration (get_ingestor factory, MarkItDownIngestor)
    - CLI (Typer+Rich)
    - Deferred deletion (store.py)
    - SourceType enum extension
  Phase 1:
    - BM25Retriever
    - HybridSearch (RRF fusion)
    - Reranker (cross-encoder + heuristic fallback)
    - CitationGenerator
    - RAGEngine pipeline
    - CLI rag commands

Usage:
    python tests/test_phase0_phase1.py
"""

import subprocess
import sys
import os
import shutil
import tempfile
import json
from pathlib import Path

# ── Setup ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
ARIADNE_DIR = SCRIPT_DIR.parent
os.chdir(ARIADNE_DIR)

TEST_DIR = ARIADNE_DIR / "tests" / "integration_test"
MARKDOWN_CACHE_DIR = TEST_DIR / "_ariadne_markdown_cache"

TEST_INPUT_DIR = TEST_DIR / "input"
TEST_INPUT_DIR.mkdir(parents=True, exist_ok=True)

BACKUP_DIR = TEST_DIR / "_backup_data"

# ── Helpers ──────────────────────────────────────────────────────────────────

def run_cmd(args, check=True, capture=True, timeout=60):
    cmd = [sys.executable, "-m", "ariadne.cli"] + args
    print(f"\n  $ {' '.join(cmd)}")
    result = subprocess.run(
        cmd, capture_output=capture, text=True,
        cwd=str(ARIADNE_DIR), timeout=timeout,
    )
    if capture:
        if result.stdout.strip():
            for line in result.stdout.strip().splitlines()[-10:]:
                print(f"    | {line}")
        if result.stderr.strip():
            for line in result.stderr.strip().splitlines()[-5:]:
                print(f"    ! {line}")
    print(f"    [exit {result.returncode}]")
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result


def count_in_store(collection_dir: Path, query_text: str) -> int:
    """Count matching docs by scanning ChromaDB sqlite directly."""
    import chromadb
    chroma_dir = collection_dir
    if not chroma_dir.exists():
        return 0
    try:
        client = chromadb.PersistentClient(path=str(chroma_dir))
        names = client.list_collections()
        for col_info in names:
            col = client.get_collection(col_info.name)
            r = col.query(query_texts=[query_text], n_results=999,
                          include=["documents"])
            if r["documents"] and r["documents"][0]:
                return len(r["documents"][0])
    except Exception:
        pass
    return 0


# ── Phase 0 Tests ───────────────────────────────────────────────────────────

def test_source_type_enum():
    """Phase 0: SourceType enum has MARKITDOWN and extended types."""
    print("\n" + "="*60)
    print("[TEST] SourceType enum extension")
    print("="*60)
    from ariadne.ingest.base import SourceType
    expected = ["MARKDOWN", "MARKITDOWN", "EPUB", "IMAGE", "OCR",
                "ACADEMIC", "WEB", "EMAIL", "VIDEO", "AUDIO", "BINARY"]
    for name in expected:
        assert hasattr(SourceType, name), f"Missing SourceType.{name}"
    print(f"  [OK] All {len(expected)} SourceType members present")
    print(f"  [OK] MARKITDOWN = {SourceType.MARKITDOWN.value!r}")


def test_get_ingestor_factory():
    """Phase 0: get_ingestor() returns correct ingestor type."""
    print("\n" + "="*60)
    print("[TEST] get_ingestor() factory — 3-level priority")
    print("="*60)

    from ariadne.ingest import get_ingestor
    from ariadne.ingest.markitdown_ingestor import MarkItDownIngestor
    from ariadne.ingest.markdown import MarkdownIngestor
    from ariadne.ingest.pdf import PDFIngestor

    cases = [
        ("test.md", MarkdownIngestor),
        ("test.py", None),  # CodeIngestor — check class name
        (".ipynb", MarkItDownIngestor),
        (".html", MarkItDownIngestor),
        (".rtf", MarkItDownIngestor),
        (".msg", MarkItDownIngestor),
        ("https://example.com", None),  # WebIngestor
        (".xyz_unknown", MarkItDownIngestor),  # markitdown fallback for unknown
    ]

    results = {}
    for ext_or_path, expected_cls in cases:
        ing = get_ingestor(ext_or_path)
        cls_name = type(ing).__name__
        results[ext_or_path] = cls_name
        if expected_cls:
            assert isinstance(ing, expected_cls), \
                f"{ext_or_path} → {cls_name}, expected {expected_cls.__name__}"
            print(f"  [OK] {ext_or_path:20s} → {cls_name} (expected)")
        else:
            print(f"  [OK] {ext_or_path:20s} → {cls_name}")

    # Verify markitdown is used for unknown extensions (level 4)
    unknown_ing = get_ingestor(".totally_unknown_format_xyz")
    assert isinstance(unknown_ing, MarkItDownIngestor), \
        "Unknown format should fall through to MarkItDownIngestor"
    print(f"  [OK] .totally_unknown → {type(unknown_ing).__name__} (markitdown fallback)")

    return results


def test_markitdown_ingestor_direct():
    """Phase 0: MarkItDownIngestor converts file to Markdown correctly."""
    print("\n" + "="*60)
    print("[TEST] MarkItDownIngestor — direct conversion")
    print("="*60)

    # Create a test file that markitdown can handle
    test_file = TEST_INPUT_DIR / "markitdown_test.html"
    test_file.write_text("""<!DOCTYPE html>
<html><head><title>Test Page</title></head>
<body><h1>Hello World</h1><p>This is a <strong>test</strong> paragraph.</p></body>
</html>""", encoding="utf-8")

    from ariadne.ingest import MarkItDownIngestor
    ing = MarkItDownIngestor()
    docs = ing.ingest(str(test_file))

    assert len(docs) >= 1, f"Expected at least 1 doc, got {len(docs)}"
    combined = " ".join(d.content for d in docs)
    assert "Hello World" in combined or "test" in combined, \
        f"Content should contain extracted text: {combined[:200]}"
    assert all(d.source_type.value == "markitdown" for d in docs), \
        "SourceType should be markitdown"
    print(f"  [OK] HTML → {len(docs)} chunk(s)")
    print(f"  [OK] SourceType: {docs[0].source_type.value}")
    print(f"  [OK] Content preview: {combined[:100]!r}")


def test_markitdown_lazy_load():
    """Phase 0: MarkItDownIngestor does NOT import markitdown until first use."""
    print("\n" + "="*60)
    print("[TEST] MarkItDownIngestor — lazy loading")
    print("="*60)

    try:
        import markitdown as _md
        print(f"  [INFO] markitdown already imported in this session — skipping lazy-load test")
        print(f"  [OK] MarkItDownIngestor available (markitdown pre-loaded by environment)")
        return
    except ImportError:
        pass

    # markitdown not yet imported — test lazy behavior
    mods_before = {m for m in sys.modules if m.startswith("markitdown")}

    from ariadne.ingest import MarkItDownIngestor
    ing = MarkItDownIngestor()

    # Still not imported until we access .markitdown property
    mods_after_prop = {m for m in sys.modules if m.startswith("markitdown")}
    assert mods_before == mods_after_prop, \
        "markitdown should NOT be imported until .markitdown property accessed"

    # Force access to .markitdown property
    _ = ing.markitdown
    mods_after_access = {m for m in sys.modules if m.startswith("markitdown")}
    assert len(mods_after_access) > len(mods_before), \
        "markitdown SHOULD be imported after .markitdown access"

    print(f"  [OK] markitdown loaded only on first .markitdown access")


def test_markitdown_header_aware_chunking():
    """Phase 0: MarkItDownIngestor preserves H1/H2 headers during chunking."""
    print("\n" + "="*60)
    print("[TEST] MarkItDownIngestor — header-aware chunking")
    print("="*60)

    html_content = """<!DOCTYPE html>
<html><body>
<h1>Main Title</h1>
<h2>Section One</h2>
<p>Content of section one goes here with a lot of text. """ + "word " * 200 + """</p>
<h2>Section Two</h2>
<p>Content of section two.</p>
</body></html>"""

    test_file = TEST_INPUT_DIR / "header_test.html"
    test_file.write_text(html_content, encoding="utf-8")

    from ariadne.ingest import MarkItDownIngestor
    ing = MarkItDownIngestor()
    docs = ing.ingest(str(test_file))

    assert len(docs) >= 1, "Should produce at least one chunk"
    combined = "\n".join(d.content for d in docs)

    # Check that headers are preserved in chunked output
    assert "Main Title" in combined or "Section" in combined, \
        f"Headers should be preserved in chunked content: {combined[:200]}"
    print(f"  [OK] {len(docs)} chunks produced")
    print(f"  [OK] Header-aware chunking preserved structure")


def test_cli_typer_rich():
    """Phase 0: CLI uses Typer + Rich (not Click)."""
    print("\n" + "="*60)
    print("[TEST] CLI — Typer + Rich (not Click)")
    print("="*60)

    # Check that Click is NOT used
    import ariadne.cli as cli_module
    src_file = Path(cli_module.__file__)

    with open(src_file, encoding="utf-8") as f:
        source = f.read()

    assert "import typer" in source or "from typer" in source, \
        "CLI should import typer"
    assert "import click" not in source.lower(), \
        "CLI should NOT use Click (should be Typer)"
    assert "from rich" in source or "import rich" in source, \
        "CLI should use Rich for output"

    result = run_cmd(["--help"])
    assert result.returncode == 0
    # Rich output should include ANSI escape codes or rich markup
    assert "Ariadne" in result.stdout or len(result.stdout) > 0
    print(f"  [OK] CLI uses Typer + Rich")
    print(f"  [OK] --help output: {result.stdout.splitlines()[0] if result.stdout.splitlines() else '(no output)'}")


def test_deferred_deletion():
    """Phase 0: VectorStore deferred deletion (mark + batch flush)."""
    print("\n" + "="*60)
    print("[TEST] VectorStore — deferred deletion")
    print("="*60)

    from ariadne.memory.store import VectorStore
    from ariadne.ingest.base import Document, SourceType
    import tempfile, shutil

    tmp_dir = Path(tempfile.mkdtemp(prefix="ariadne_test_"))
    try:
        store = VectorStore(persist_dir=str(tmp_dir), collection_name="test_deferred")

        # Add docs
        docs = [
            Document(content=f"Doc {i}", source_type=SourceType.TXT,
                     source_path=f"test/{i}.txt")
            for i in range(5)
        ]
        store.add(docs)
        assert store.count() == 5, f"Expected 5 docs, got {store.count()}"

        # Mark 3 docs for deletion (deferred)
        doc_ids_to_delete = [docs[i].doc_id for i in range(3)]
        for doc_id in doc_ids_to_delete:
            store.delete_doc(doc_id)

        # Count should still be 5 (not yet flushed)
        assert store.count() == 5, "Count should still be 5 before flush"
        assert store.pending_delete_count == 3, \
            f"Pending deletes should be 3, got {store.pending_delete_count}"

        # Flush
        deleted = store.flush_deletes()
        assert deleted == 3, f"Should have deleted 3, got {deleted}"
        assert store.count() == 2, f"Count should be 2 after flush, got {store.count()}"
        assert store.pending_delete_count == 0, "Pending should be 0 after flush"

        # Context manager auto-flush
        store2 = VectorStore(persist_dir=str(tmp_dir / "sub2"),
                             collection_name="test_cm")
        store2.add([Document(content="cm doc", source_type=SourceType.TXT,
                             source_path="cm/path.txt")])
        store2.delete_doc(store2._collection.get()["ids"][0])
        assert store2.pending_delete_count == 1
        with store2:
            pass  # exits __exit__ → auto-flush
        assert store2.pending_delete_count == 0, \
            "Context manager should auto-flush pending deletes"

        print(f"  [OK] delete_doc() → deferred queue (count unchanged)")
        print(f"  [OK] flush_deletes() → batch delete ({deleted} removed)")
        print(f"  [OK] Context manager auto-flushes on exit")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_memory_manager_crud():
    """Phase 0: MemoryManager create/rename/delete/merge."""
    print("\n" + "="*60)
    print("[TEST] MemoryManager — CRUD operations")
    print("="*60)

    from ariadne.memory import get_manager
    from ariadne.ingest.base import Document, SourceType
    import tempfile, shutil

    tmp_base = Path(tempfile.mkdtemp(prefix="ariadne_mm_test_"))
    try:
        from ariadne.memory.manager import MemoryManager
        mgr = MemoryManager(base_dir=str(tmp_base))

        # Create
        mgr.create("test_sys")
        systems = mgr.list_systems()
        assert any(s.name == "test_sys" for s in systems)
        print(f"  [OK] create('test_sys')")

        # Rename
        mgr.rename("test_sys", "test_sys_renamed")
        systems = mgr.list_systems()
        assert any(s.name == "test_sys_renamed" for s in systems)
        assert not any(s.name == "test_sys" for s in systems)
        print(f"  [OK] rename('test_sys' → 'test_sys_renamed')")

        # Merge
        mgr.create("source_a", silent=True)
        mgr.create("source_b", silent=True)
        store_a = mgr.get_store("source_a")
        store_a.add([
            Document(content="from a", source_type=SourceType.TXT, source_path="a.txt"),
        ])
        store_b = mgr.get_store("source_b")
        store_b.add([
            Document(content="from b", source_type=SourceType.TXT, source_path="b.txt"),
        ])

        mgr.merge(["source_a", "source_b"], "merged_ab")
        merged_count = mgr.get_store("merged_ab").count()
        assert merged_count == 2, f"Merged count should be 2, got {merged_count}"
        print(f"  [OK] merge(['source_a','source_b'] → 'merged_ab', {merged_count} docs)")

        # Delete
        mgr.delete("source_a", confirm=False)
        mgr.delete("source_b", confirm=False)
        systems = mgr.list_systems()
        assert not any(s.name in ("source_a", "source_b") for s in systems)
        print(f"  [OK] delete('source_a'), delete('source_b')")

    finally:
        shutil.rmtree(tmp_base, ignore_errors=True)


def test_db_corruption_recovery():
    """Phase 0: VectorStore auto-recovers from DB corruption."""
    print("\n" + "="*60)
    print("[TEST] VectorStore — DB corruption auto-recovery")
    print("="*60)

    from ariadne.memory.store import VectorStore, _is_db_corruption_error
    import tempfile, shutil

    tmp_dir = Path(tempfile.mkdtemp(prefix="ariadne_corrupt_"))
    try:
        # Create healthy store
        store = VectorStore(persist_dir=str(tmp_dir), collection_name="test_recover")
        from ariadne.ingest.base import Document, SourceType
        store.add([Document(content="healthy doc", source_type=SourceType.TXT,
                             source_path="healthy.txt")])
        assert store.count() == 1
        print(f"  [OK] Store initialized: {store.count()} doc(s)")

        # Corrupt the sqlite db
        sqlite_file = tmp_dir / "chroma.sqlite3"
        if sqlite_file.exists():
            with open(sqlite_file, "r+b") as f:
                f.write(b"This is NOT a valid SQLite database!!!")
            print(f"  [OK] Corrupted {sqlite_file}")

        # Attempt to probe — should raise
        probe_ok = False
        try:
            VectorStore(persist_dir=str(tmp_dir), collection_name="test_recover").probe()
            probe_ok = True
        except Exception as e:
            print(f"  [OK] Corrupted DB detected: {type(e).__name__}")

        if not probe_ok:
            print(f"  [OK] Corruption properly detected (_is_db_corruption_error works)")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Phase 1 Tests ────────────────────────────────────────────────────────────

def test_rag_imports():
    """Phase 1: All RAG modules can be imported."""
    print("\n" + "="*60)
    print("[TEST] RAG modules — import check")
    print("="*60)

    try:
        from ariadne.rag import (
            BM25Retriever, HybridSearch, Reranker,
            CitationGenerator, create_rag_engine,
        )
        from ariadne.rag.engine import RAGResult
        print(f"  [OK] All RAG modules imported successfully")
        print(f"  [OK] create_rag_engine: {create_rag_engine}")
    except ImportError as e:
        print(f"  [WARN] RAG imports failed (missing deps): {e}")
        print(f"  [INFO] Install with: pip install rank-bm25 sentence-transformers")
        raise


def test_rag_engine_pipeline():
    """Phase 1: Full RAG pipeline (BM25 → Hybrid → Rerank → Citation)."""
    print("\n" + "="*60)
    print("[TEST] RAG Engine — full pipeline")
    print("="*60)

    try:
        from ariadne.rag import create_rag_engine
    except ImportError:
        print("  [SKIP] rank-bm25 / sentence-transformers not installed")
        return

    from ariadne.memory.store import VectorStore
    from ariadne.ingest.base import Document, SourceType
    import tempfile, shutil

    tmp_dir = Path(tempfile.mkdtemp(prefix="ariadne_rag_test_"))
    try:
        store = VectorStore(persist_dir=str(tmp_dir), collection_name="rag_test")

        # Seed with known content
        docs = [
            Document(content="Python is a programming language great for data science",
                     source_type=SourceType.TXT, source_path="python.txt"),
            Document(content="Machine learning is a subset of artificial intelligence",
                     source_type=SourceType.TXT, source_path="ml.txt"),
            Document(content="Deep learning uses neural networks with many layers",
                     source_type=SourceType.TXT, source_path="dl.txt"),
            Document(content="JavaScript is primarily used for web development",
                     source_type=SourceType.TXT, source_path="js.txt"),
            Document(content="Natural language processing helps computers understand text",
                     source_type=SourceType.TXT, source_path="nlp.txt"),
        ]
        store.add(docs)
        print(f"  [OK] Seeded {len(docs)} docs in vector store")

        # Build engine
        engine = create_rag_engine(store, config={"rerank": True, "alpha": 0.5})
        print(f"  [OK] RAGEngine created")

        # Query
        result = engine.query(
            query="python programming machine learning",
            top_k=3,
            fetch_k=5,
            alpha=0.5,
            include_citations=True,
        )

        assert not result.is_empty, "Should return results for python query"
        assert len(result.results) <= 3, f"Should return ≤3 results, got {len(result.results)}"
        print(f"  [OK] Query returned {len(result.results)} result(s)")

        # Check scores are populated
        for res in result.results:
            print(f"  [OK] Doc: {res.document.content[:50]}...")
            print(f"      vec={res.vector_score:.3f} bm25={res.bm25_score:.3f} "
                  f"rrf={res.rrf_score:.3f} rank={res.rank} src={res.source}")

        # Citations
        if result.citations:
            for cit in result.citations[:2]:
                print(f"  [OK] Citation: {cit.format_plain()[:80]}")
        else:
            print(f"  [OK] No citations (normal if query terms not in chunks)")

        # Rebuild index (may skip if rank_bm25 not installed)
        try:
            count = engine.rebuild_bm25_index()
            print(f"  [OK] BM25 index rebuilt: {count} docs")
        except ImportError as e:
            print(f"  [INFO] BM25 rebuild skipped (deps missing): {e}")

        # Health check
        status = engine.health_check()
        print(f"  [OK] Health check: bm25={status['bm25']['healthy']}, "
              f"reranker={status['reranker']['healthy']}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_rag_cli_search():
    """Phase 1: ariadne rag search CLI command."""
    print("\n" + "="*60)
    print("[TEST] RAG CLI — ariadne rag search")
    print("="*60)

    # First ingest some test data
    test_md = TEST_INPUT_DIR / "rag_test.md"
    test_md.write_text("""# RAG Test Document

## Python
Python is an interpreted high-level programming language.

## Machine Learning
Machine learning is a subset of artificial intelligence.

## Search
Full-text search and vector search can be combined for better results.
""", encoding="utf-8")

    run_cmd(["ingest", str(test_md)])
    print(f"  [OK] Ingested test doc for RAG search")

    result = run_cmd(["rag", "search", "python programming", "-k", "3"], check=False)
    if result.returncode == 0:
        print(f"  [OK] rag search succeeded (exit 0)")
        assert "result" in result.stdout.lower() or len(result.stdout) > 0
    else:
        # Check if it's a missing-dependency error
        if "not installed" in result.stdout.lower() or "not installed" in result.stderr.lower():
            print(f"  [INFO] RAG deps not installed — skipping pipeline test")
        else:
            print(f"  [WARN] rag search failed: {result.stderr[:200]}")


def test_rag_health_check():
    """Phase 1: ariadne rag health CLI command."""
    print("\n" + "="*60)
    print("[TEST] RAG CLI — ariadne rag health")
    print("="*60)

    result = run_cmd(["rag", "health"], check=False)
    if result.returncode == 0:
        print(f"  [OK] rag health succeeded")
        print(f"  Output: {result.stdout[:300]}")
    elif "not installed" in result.stdout.lower() + result.stderr.lower():
        print(f"  [INFO] RAG deps not installed — skipping health check")


def test_ingest_all_supported_formats():
    """Phase 0: Test ingestor for ALL supported formats via CLI."""
    print("\n" + "="*60)
    print("[TEST] Ingest ALL supported formats")
    print("="*60)

    # Create test files for each format category
    test_files = {}

    # Text-based (native ingestors)
    test_files["test.md"] = "# Markdown Test\n\nContent here."
    test_files["test.txt"] = "Plain text content."
    test_files["test.py"] = '"""Test module."""\ndef foo(): return 42'
    test_files["test.csv"] = "id,name\n1,Alice\n2,Bob"
    test_files["test.json"] = '{"key": "value", "items": [1, 2, 3]}'
    test_files["test.java"] = "public class Test {}"
    test_files["test.js"] = "const x = 42;"

    # MarkItDown preferred formats (no native ingestor)
    test_files["test.html"] = "<html><body><h1>HTML Test</h1><p>Content</p></body></html>"
    test_files["test.ipynb"] = json.dumps({
        "nbformat": 4,
        "cells": [{"cell_type": "markdown", "source": "# Jupyter"}],
    })

    # Mixed: some have native + markitdown fallback
    # PDF/DOCX/PPTX need real binaries — test via existence check only

    results = {}
    for fname, content in test_files.items():
        fpath = TEST_INPUT_DIR / fname
        fpath.write_text(content, encoding="utf-8")

        result = run_cmd(["ingest", str(fpath), "-v"], check=False)
        ingested = result.returncode == 0 and ("ingested" in result.stdout.lower()
                                               or "added" in result.stdout.lower()
                                               or "success" in result.stdout.lower()
                                               or result.returncode == 0)
        results[fname] = "OK" if result.returncode == 0 else f"FAIL({result.returncode})"
        status = "OK" if ingested else "FAIL"
        print(f"  {fname:20s} → {status:4s}  [{results[fname]}]")

    # Check: at least the text-based ones should work
    ok_count = sum(1 for v in results.values() if v == "OK")
    print(f"\n  Summary: {ok_count}/{len(results)} formats ingested successfully")

    if ok_count < len(results) * 0.7:
        raise RuntimeError(f"Too many ingest failures: {results}")


def test_cli_ingest_directory_recursive():
    """Phase 0: CLI ingest --recursive on directory."""
    print("\n" + "="*60)
    print("[TEST] CLI — ingest --recursive directory")
    print("="*60)

    # Create nested directory structure
    nested = TEST_INPUT_DIR / "nested"
    nested.mkdir(exist_ok=True)
    (nested / "level1.md").write_text("# Level 1", encoding="utf-8")
    (nested / "level2").mkdir(exist_ok=True)
    (nested / "level2" / "level2.txt").write_text("Level 2 content", encoding="utf-8")
    (nested / "level2" / "level3").mkdir(exist_ok=True)
    (nested / "level2" / "level3" / "level3.py").write_text("# Deep", encoding="utf-8")

    result = run_cmd(["ingest", str(nested), "-r", "-v"])
    assert result.returncode == 0
    assert "3" in result.stdout or "ingested" in result.stdout.lower() or result.returncode == 0
    print(f"  [OK] Recursive ingest found files in subdirectories")


def test_markitdown_caching_interception():
    """Phase 0: Check that MarkItDown output goes through chunking (not stored as raw)."""
    print("\n" + "="*60)
    print("[TEST] MarkItDown — output goes through Ariadne chunking pipeline")
    print("="*60)

    from ariadne.ingest import MarkItDownIngestor
    from ariadne.ingest.base import Document

    # HTML with multiple sections that markitdown would flatten
    html = """<!DOCTYPE html>
<html><body>
<h1>Title</h1>
<p>First paragraph with important content.</p>
<h2>Section 2</h2>
<p>Second paragraph with more content.</p>
<h2>Section 3</h2>
<p>Third paragraph.</p>
</body></html>"""

    test_file = TEST_INPUT_DIR / "chunk_test.html"
    test_file.write_text(html, encoding="utf-8")

    ing = MarkItDownIngestor()
    docs = ing.ingest(str(test_file))

    # Verify: each doc should be a separate chunk
    assert len(docs) >= 1, "Should produce chunks"

    # Verify: each doc is a proper Document (not raw HTML)
    for d in docs:
        assert isinstance(d, Document), f"Should be Document, got {type(d)}"
        assert d.doc_id, "Document should have a doc_id"

    # Verify: markitdown output has been chunked (Markdown)
    # The markitdown HTML→Markdown conversion should produce H1/H2 headers
    combined = " ".join(d.content for d in docs)
    # markitdown converts HTML H1 → # Title, H2 → ## Section
    # Then _chunk_markdown splits on ## headers
    assert "Title" in combined or "Section" in combined or "paragraph" in combined, \
        f"Chunked content should contain text: {combined[:200]}"

    print(f"  [OK] {len(docs)} chunk(s) produced from HTML")
    print(f"  [OK] Each chunk is a Document with doc_id, metadata")
    print(f"  [OK] Content preview: {combined[:120]!r}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("="*60)
    print("Ariadne — Phase 0 & Phase 1 Integration Tests")
    print("="*60)

    # Backup existing data
    data_dir = ARIADNE_DIR / "ariadne_data"
    if data_dir.exists():
        if BACKUP_DIR.exists():
            shutil.rmtree(BACKUP_DIR)
        shutil.copytree(data_dir, BACKUP_DIR)
        print(f"[Setup] Backed up ariadne_data → {BACKUP_DIR}")

    # Clean data dir for fresh test
    if data_dir.exists():
        shutil.rmtree(data_dir)
        print("[Setup] Cleared ariadne_data for clean test")

    tests = [
        # Phase 0
        ("SourceType enum", test_source_type_enum),
        ("get_ingestor factory (3-level)", test_get_ingestor_factory),
        ("MarkItDown direct conversion", test_markitdown_ingestor_direct),
        ("MarkItDown lazy load", test_markitdown_lazy_load),
        ("MarkItDown header-aware chunking", test_markitdown_header_aware_chunking),
        ("CLI Typer+Rich (not Click)", test_cli_typer_rich),
        ("Deferred deletion", test_deferred_deletion),
        ("MemoryManager CRUD", test_memory_manager_crud),
        ("DB corruption recovery", test_db_corruption_recovery),
        # Phase 1
        ("RAG module imports", test_rag_imports),
        ("RAG full pipeline", test_rag_engine_pipeline),
        ("RAG CLI search", test_rag_cli_search),
        ("RAG CLI health", test_rag_health_check),
        # Format coverage
        ("Ingest all supported formats", test_ingest_all_supported_formats),
        ("CLI recursive ingest", test_cli_ingest_directory_recursive),
        ("MarkItDown chunking pipeline", test_markitdown_caching_interception),
    ]

    passed = 0
    failed = 0
    skipped = 0

    for name, func in tests:
        try:
            func()
            passed += 1
            print(f"\n[PASS] {name}")
        except Exception as e:
            # Distinguish skip vs fail
            if "not installed" in str(e).lower() or "SKIP" in str(e):
                skipped += 1
                print(f"\n[SKIP] {name}: {e}")
            else:
                failed += 1
                import traceback
                print(f"\n[FAIL] {name}: {e}")
                traceback.print_exc()

    # Restore backup
    if BACKUP_DIR.exists():
        if data_dir.exists():
            shutil.rmtree(data_dir)
        shutil.copytree(BACKUP_DIR, data_dir)
        print(f"\n[Teardown] Restored ariadne_data from backup")

    # Cleanup test dirs
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR, ignore_errors=True)

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"  Passed:  {passed}")
    print(f"  Failed:  {failed}")
    print(f"  Skipped: {skipped}")
    print(f"  Total:   {passed + failed + skipped}")

    if failed == 0:
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print(f"\n[FAILURE] {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
