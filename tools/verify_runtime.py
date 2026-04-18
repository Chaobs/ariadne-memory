#!/usr/bin/env python3
"""
Runtime verification script for Ariadne.

Tests all core components:
- ChromaDB connection
- Ingestors
- Vector store operations
- Search functionality

Run with: python tools/verify_runtime.py
"""

import sys
import tempfile
import os
import io
from pathlib import Path

# Fix Windows Unicode output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_chromadb():
    """Test ChromaDB connection and basic operations."""
    print("\n" + "="*50)
    print("Testing ChromaDB...")
    print("="*50)

    try:
        from ariadne.memory import VectorStore

        # Create temporary store
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(persist_dir=tmpdir)

            print(f"✓ VectorStore initialized")
            print(f"  Persist dir: {store.persist_dir}")

            # Test add and search
            from ariadne.ingest.base import Document, SourceType

            doc = Document(
                content="This is a test document for verification.",
                source_type=SourceType.TXT,
                source_path="/test/file.txt"
            )

            store.add([doc])
            print(f"✓ Document added (count: {store.count()})")

            # Test search
            results = store.search("test document", top_k=5)
            print(f"✓ Search completed (results: {len(results)})")

            if results:
                doc, score = results[0]
                print(f"  Best match score: {score:.4f}")

        print("\n✓ ChromaDB: ALL TESTS PASSED")
        return True

    except Exception as e:
        print(f"\n✗ ChromaDB: TEST FAILED")
        print(f"  Error: {e}")
        return False


def test_ingestors():
    """Test all document ingestors."""
    print("\n" + "="*50)
    print("Testing Ingestors...")
    print("="*50)

    from ariadne.ingest import (
        MarkdownIngestor,
        TxtIngestor,
        ExcelIngestor,
        CsvIngestor,
    )

    results = []

    # Test TxtIngestor (most reliable)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write("Test content for verification.\n\nSecond paragraph.")
        txt_path = f.name

    try:
        docs = TxtIngestor().ingest(txt_path)
        print(f"✓ TxtIngestor: {len(docs)} docs extracted")
        results.append(("TxtIngestor", True))
    except Exception as e:
        print(f"✗ TxtIngestor: {e}")
        results.append(("TxtIngestor", False))
    finally:
        os.unlink(txt_path)

    # Test MarkdownIngestor
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write("# Test\n\nContent here.\n\n## Section\n\nMore content.")
        md_path = f.name

    try:
        docs = MarkdownIngestor().ingest(md_path)
        print(f"✓ MarkdownIngestor: {len(docs)} docs extracted")
        results.append(("MarkdownIngestor", True))
    except Exception as e:
        print(f"✗ MarkdownIngestor: {e}")
        results.append(("MarkdownIngestor", False))
    finally:
        os.unlink(md_path)

    # Test ExcelIngestor (if openpyxl available)
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Name", "Age"])
        ws.append(["Alice", 30])
        ws.append(["Bob", 25])
        fd, xlsx_path = tempfile.mkstemp(suffix='.xlsx')
        os.close(fd)
        wb.save(xlsx_path)
        wb.close()

        docs = ExcelIngestor().ingest(xlsx_path)
        print(f"✓ ExcelIngestor: {len(docs)} docs extracted")
        results.append(("ExcelIngestor", True))
        os.unlink(xlsx_path)
    except ImportError:
        print("⊘ ExcelIngestor: skipped (openpyxl not installed)")
        results.append(("ExcelIngestor", None))
    except Exception as e:
        print(f"✗ ExcelIngestor: {e}")
        results.append(("ExcelIngestor", False))

    # Test CsvIngestor
    fd, csv_path = tempfile.mkstemp(suffix='.csv')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write("Name,Age,City\n")
        f.write("Alice,30,Beijing\n")
        f.write("Bob,25,Shanghai\n")

    try:
        docs = CsvIngestor().ingest(csv_path)
        print(f"✓ CsvIngestor: {len(docs)} docs extracted")
        results.append(("CsvIngestor", True))
    except Exception as e:
        print(f"✗ CsvIngestor: {e}")
        results.append(("CsvIngestor", False))
    finally:
        os.unlink(csv_path)

    # Summary
    passed = sum(1 for _, r in results if r is True)
    skipped = sum(1 for _, r in results if r is None)
    failed = sum(1 for _, r in results if r is False)

    print(f"\nIngestor Summary: {passed} passed, {skipped} skipped, {failed} failed")

    if failed == 0:
        print("✓ All ingestors: TESTS PASSED")
        return True
    else:
        print("✗ Some ingestors: TESTS FAILED")
        return False


def test_cli():
    """Test CLI commands."""
    print("\n" + "="*50)
    print("Testing CLI...")
    print("="*50)

    import subprocess

    try:
        result = subprocess.run(
            [sys.executable, "-m", "ariadne", "--version"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        if result.returncode == 0:
            print(f"✓ CLI version check passed")
            print(f"  Version: {result.stdout.strip()}")
        else:
            print(f"✗ CLI version check failed")
            print(f"  Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ CLI test failed: {e}")
        return False

    print("\n✓ CLI: TEST PASSED")
    return True


def main():
    """Run all verification tests."""
    print("="*60)
    print("Ariadne Runtime Verification")
    print("="*60)
    print(f"Python: {sys.version}")
    print(f"CWD: {os.getcwd()}")

    results = []

    results.append(("ChromaDB", test_chromadb()))
    results.append(("Ingestors", test_ingestors()))
    results.append(("CLI", test_cli()))

    # Summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("="*60)

    if all_passed:
        print("\n🎉 All verifications PASSED! Ariadne is ready to use.")
        return 0
    else:
        print("\n⚠️  Some verifications FAILED. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
