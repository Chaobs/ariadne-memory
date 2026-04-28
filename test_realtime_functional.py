#!/usr/bin/env python3
"""
Functional test for real-time vectorization module.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, '.')

print("=== Functional Test for Real-time Vectorization ===\n")

# Create a temporary directory for test files
test_dir = tempfile.mkdtemp(prefix="ariadne_realtime_test_")
print(f"Test directory: {test_dir}")

# Create sample memory files
memory_file = Path(test_dir) / "MEMORY.md"
memory_file.write_text("""# Test Memory

## Ariadne Project
- Completed real-time vectorization module development
- Added CLI, Web API and MCP tool support

## Technical Decisions
- Using watchdog for file monitoring
- Observation records stored in SQLite and synced to ChromaDB

## TODO
- Test file change detection
- Verify vector storage synchronization
""", encoding='utf-8')

daily_file = Path(test_dir) / "2026-04-28.md"
daily_file.write_text("""# 2026-04-28 Work Log

## Morning
- Completed real-time vectorization architecture design
- Implemented ObservationIngestor class

## Afternoon
- Added FileWatcher monitoring functionality
- Integrated RealtimeVectorizer coordinator
""", encoding='utf-8')

print(f"Created test files:")
print(f"  - {memory_file}")
print(f"  - {daily_file}")

# Test 1: Manual ingestion
print("\n--- Test 1: Manual Ingestion ---")
try:
    from ariadne.realtime import RealtimeVectorizer
    
    vectorizer = RealtimeVectorizer()
    
    print("Ingesting memory file...")
    observations, doc_ids = vectorizer.ingest_file(memory_file)
    print(f"  Observations created: {len(observations)}")
    print(f"  Documents ingested: {len(doc_ids)}")
    
    print("Ingesting daily file...")
    observations2, doc_ids2 = vectorizer.ingest_file(daily_file)
    print(f"  Observations created: {len(observations2)}")
    print(f"  Documents ingested: {len(doc_ids2)}")
    
    # Check status
    status = vectorizer.get_status()
    print(f"\nStatus after ingestion:")
    print(f"  Files processed: {status['stats']['files_processed']}")
    print(f"  Observations created: {status['stats']['observations_created']}")
    print(f"  Documents ingested: {status['stats']['documents_ingested']}")
    
    print("[PASS] Manual ingestion test")
    
except Exception as e:
    print(f"[FAIL] Manual ingestion test: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Directory ingestion
print("\n--- Test 2: Directory Ingestion ---")
try:
    from ariadne.realtime import RealtimeVectorizer
    
    vectorizer2 = RealtimeVectorizer()
    
    print("Ingesting entire test directory...")
    observations, doc_ids = vectorizer2.ingest_directory(test_dir, pattern="*.md")
    print(f"  Observations created: {len(observations)}")
    print(f"  Documents ingested: {len(doc_ids)}")
    
    print("[PASS] Directory ingestion test")
    
except Exception as e:
    print(f"[FAIL] Directory ingestion test: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Configuration
print("\n--- Test 3: Configuration Management ---")
try:
    from ariadne.realtime import RealtimeVectorizer
    
    vectorizer3 = RealtimeVectorizer()
    
    # Get current config
    config = vectorizer3.get_config()
    print(f"Initial config:")
    print(f"  Default memory system: {config['default_memory_system']}")
    print(f"  Watch patterns: {config['watch_patterns']}")
    print(f"  Debounce seconds: {config['debounce_seconds']}")
    
    # Update config
    print("\nUpdating configuration...")
    success = vectorizer3.update_config(
        default_memory_system="test_memory",
        watch_patterns=["*.md", "*.txt"],
        debounce_seconds=1.5
    )
    
    if success:
        config2 = vectorizer3.get_config()
        print(f"Updated config:")
        print(f"  Default memory system: {config2['default_memory_system']}")
        print(f"  Watch patterns: {config2['watch_patterns']}")
        print(f"  Debounce seconds: {config2['debounce_seconds']}")
        print("[PASS] Configuration test")
    else:
        print("[FAIL] Failed to update configuration")
    
except Exception as e:
    print(f"[FAIL] Configuration test: {e}")
    import traceback
    traceback.print_exc()

# Test 4: CLI command simulation
print("\n--- Test 4: CLI Command Simulation ---")
try:
    from ariadne.realtime import RealtimeVectorizer
    
    vectorizer4 = RealtimeVectorizer()
    
    # Simulate 'ariadne memory watch' command
    print("Simulating 'ariadne memory watch' command...")
    success = vectorizer4.start_watching([test_dir], recursive=True)
    
    if success:
        status = vectorizer4.get_status()
        print(f"  Watching started: {status['is_watching']}")
        print(f"  Watched directories: {status['watch_directories']}")
        
        # Wait a moment
        time.sleep(0.5)
        
        # Create a new file to trigger watcher
        new_file = Path(test_dir) / "new_memory.md"
        new_file.write_text("# New Memory File\n\n- This should trigger the watcher", encoding='utf-8')
        
        # Wait for watcher to potentially process
        time.sleep(1)
        
        # Stop watching
        stopped = vectorizer4.stop_watching()
        print(f"  Watching stopped: {stopped}")
        
        # Check final status
        final_status = vectorizer4.get_status()
        print(f"  Final stats:")
        print(f"    Files processed: {final_status['stats']['files_processed']}")
        
        print("[PASS] CLI command simulation test")
    else:
        print("[FAIL] Failed to start watching")
    
except Exception as e:
    print(f"[FAIL] CLI command simulation test: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Web API simulation
print("\n--- Test 5: Web API Simulation ---")
try:
    from ariadne.web.api_extensions import get_realtime_vectorizer
    
    vectorizer5 = get_realtime_vectorizer()
    
    # Get status via Web API pattern
    status = vectorizer5.get_status()
    print(f"Status via Web API dependency:")
    print(f"  Is watching: {status['is_watching']}")
    print(f"  Stats: {status['stats']}")
    
    print("[PASS] Web API simulation test")
    
except Exception as e:
    print(f"[FAIL] Web API simulation test: {e}")
    import traceback
    traceback.print_exc()

# Test 6: MCP tool simulation
print("\n--- Test 6: MCP Tool Simulation ---")
try:
    from ariadne.mcp.tools import RealtimeWatchTool, RealtimeIngestTool, RealtimeStatusTool
    
    # Test RealtimeWatchTool
    watch_tool = RealtimeWatchTool()
    print(f"Watch tool name: {watch_tool.name}")
    print(f"Watch tool description: {watch_tool.description}")
    
    # Test RealtimeIngestTool
    ingest_tool = RealtimeIngestTool()
    print(f"Ingest tool name: {ingest_tool.name}")
    
    # Test RealtimeStatusTool
    status_tool = RealtimeStatusTool()
    print(f"Status tool name: {status_tool.name}")
    
    print("[PASS] MCP tool simulation test")
    
except Exception as e:
    print(f"[FAIL] MCP tool simulation test: {e}")
    import traceback
    traceback.print_exc()

# Cleanup
print("\n--- Cleanup ---")
import shutil
try:
    shutil.rmtree(test_dir)
    print(f"Cleaned up test directory: {test_dir}")
except Exception as e:
    print(f"Warning: Failed to clean up test directory: {e}")

print("\n=== Functional Test Complete ===")