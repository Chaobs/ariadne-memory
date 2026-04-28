#!/usr/bin/env python3
"""
Test script to verify real-time vectorization module imports correctly.
"""
import sys
sys.path.insert(0, '.')

print("Testing real-time vectorization module imports...")

try:
    from ariadne.realtime import ObservationIngestor, FileWatcher, RealtimeVectorizer
    print("[OK] All classes imported successfully")
    
    # Test instantiation
    print("\nTesting class instantiation...")
    
    try:
        ingestor = ObservationIngestor()
        print("[OK] ObservationIngestor instantiated")
    except Exception as e:
        print(f"[FAIL] ObservationIngestor failed: {e}")
    
    try:
        # FileWatcher requires watchdog, may fail if not installed
        watcher = FileWatcher()
        print("[OK] FileWatcher instantiated")
    except ImportError as e:
        print(f"[WARN] FileWatcher requires watchdog: {e}")
    except Exception as e:
        print(f"[FAIL] FileWatcher failed: {e}")
    
    try:
        vectorizer = RealtimeVectorizer()
        print("[OK] RealtimeVectorizer instantiated")
    except Exception as e:
        print(f"[FAIL] RealtimeVectorizer failed: {e}")
    
    # Test CLI command registration
    print("\nTesting CLI command imports...")
    try:
        from ariadne.cli import app, memory_app
        print("[OK] CLI app imported")
        
        # Check if realtime commands are registered under memory_app
        import typer
        from typer.core import TyperCommand, TyperGroup
        
        def find_command(typer_app, name):
            # typer_app.registered_commands returns List[CommandInfo]
            for cmd in typer_app.registered_commands:
                if cmd.name == name:
                    return cmd
            return None
        
        commands_to_check = ["watch", "ingest-observation", "realtime-status", "realtime-config"]
        for cmd_name in commands_to_check:
            cmd = find_command(memory_app, cmd_name)
            if cmd:
                print(f"[OK] CLI command 'memory {cmd_name}' found")
            else:
                # Also check app for direct commands
                cmd = find_command(app, cmd_name)
                if cmd:
                    print(f"[OK] CLI command '{cmd_name}' found (direct)")
                else:
                    print(f"[FAIL] CLI command 'memory {cmd_name}' not found")
                
    except Exception as e:
        print(f"[FAIL] CLI test failed: {e}")
    
    # Test Web API imports
    print("\nTesting Web API imports...")
    try:
        from ariadne.web.api_extensions import get_realtime_vectorizer
        vectorizer = get_realtime_vectorizer()
        print("[OK] Web API get_realtime_vectorizer works")
    except Exception as e:
        print(f"[FAIL] Web API test failed: {e}")
    
    # Test MCP tool imports
    print("\nTesting MCP tool imports...")
    try:
        from ariadne.mcp.tools import RealtimeWatchTool, RealtimeStopTool, RealtimeIngestTool, RealtimeStatusTool, RealtimeConfigTool
        print("[OK] All MCP tool classes imported")
        
        # Check if tools are registered in AriadneToolHandler
        from ariadne.mcp.tools import AriadneToolHandler
        handler = AriadneToolHandler()
        tools = handler.list()
        realtime_tools = [t for t in tools if "realtime" in t.get("name", "")]
        print(f"[OK] Found {len(realtime_tools)} real-time tools in handler")
        
    except Exception as e:
        print(f"[FAIL] MCP tool test failed: {e}")
    
    print("\n[OK] All tests completed!")
    
except ImportError as e:
    print(f"[FAIL] Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)