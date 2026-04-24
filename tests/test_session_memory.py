"""Test session memory module"""
import sys
sys.path.insert(0, ".")

from ariadne.session import get_manager, Platform
from ariadne.session.privacy import strip_private_tags, contains_private_content
from ariadne.session.summarizer import parse_observations, parse_session_summary
from ariadne.hooks import run_hook
import json

def test_session_lifecycle():
    mgr = get_manager()
    
    # Test 1: Start session
    session, ctx = mgr.start_session(project_path='D:/TestProject', platform=Platform.GENERIC)
    assert session.id, "Session should have an ID"
    print(f"[PASS] Session started: {session.id[:8]}...")

    # Test 2: Add direct observation
    obs = mgr.add_observation_direct(
        session_id=session.id,
        obs_type='feature',
        summary='Added login form validation',
        files=['auth/login.py'],
        concepts=['authentication', 'validation'],
    )
    assert obs.id, "Observation should have an ID"
    print(f"[PASS] Observation added: {obs.id[:8]}...")

    # Test 3: Get stats
    stats = mgr.stats()
    assert stats['sessions'] >= 1
    assert stats['observations'] >= 1
    print(f"[PASS] Stats OK: sessions={stats['sessions']}, observations={stats['observations']}")

    # Test 4: Search
    results = mgr.search_observations('login validation', project_path='D:/TestProject')
    assert len(results) >= 1
    print(f"[PASS] Search found {len(results)} results")

    # Test 5: Get timeline
    timeline = mgr.get_timeline(session.id)
    assert timeline['observation_count'] >= 1
    print(f"[PASS] Timeline: {timeline['observation_count']} observations")

    # Test 6: List sessions
    sessions = mgr.list_sessions(project_path='D:/TestProject')
    assert len(sessions) >= 1
    print(f"[PASS] List sessions: {len(sessions)}")

    # Test 7: End session (no LLM for test)
    mgr.end_session(session.id, generate_summary=False)
    print("[PASS] Session ended")


def test_privacy():
    # Test private tag stripping
    text = "Hello <private>secret stuff</private> world"
    result = strip_private_tags(text)
    assert "secret stuff" not in result
    assert "Hello" in result
    assert "world" in result
    print("[PASS] Privacy: private tag stripped")
    
    # Test contains_private_content
    assert contains_private_content(text) == True
    assert contains_private_content("Hello world") == False
    print("[PASS] Privacy: contains_private_content works")
    
    # Test wrap/unwrap ariadne-context
    from ariadne.session.privacy import wrap_context_injection
    wrapped = wrap_context_injection("test content")
    assert "<ariadne-context>" in wrapped
    stripped = strip_private_tags(wrapped)
    assert "test content" not in stripped
    print("[PASS] Privacy: ariadne-context stripped")


def test_observation_parser():
    # Test parsing observations from LLM response
    llm_response = """
<observation>
  <type>feature</type>
  <summary>Added JWT authentication middleware</summary>
  <detail>Implemented Bearer token validation with RS256 signing</detail>
  <files>middleware/auth.py, tests/test_auth.py</files>
  <concepts>authentication, JWT, middleware</concepts>
</observation>
"""
    observations = parse_observations(llm_response, session_id="test-session-123")
    assert len(observations) == 1
    obs = observations[0]
    assert obs.summary == "Added JWT authentication middleware"
    assert "middleware/auth.py" in obs.files
    assert "authentication" in obs.concepts
    print(f"[PASS] Parser: parsed {len(observations)} observation(s)")

    # Test parsing session summary
    summary_response = """
<session_summary>
  <narrative>Implemented authentication system with JWT tokens</narrative>
  <key_decisions>Use RS256 over HS256, Store refresh tokens in Redis</key_decisions>
  <files_changed>middleware/auth.py, config/jwt.py</files_changed>
  <concepts_covered>authentication, JWT, Redis, middleware</concepts_covered>
</session_summary>
"""
    summary = parse_session_summary(summary_response, session_id="test-session-123")
    assert summary is not None
    assert "JWT" in summary.narrative
    assert "middleware/auth.py" in summary.files_changed
    print(f"[PASS] Parser: session summary parsed")


def test_hook_runner():
    # Test SessionStart hook
    stdin_data = json.dumps({
        "session_id": "hook-test-session",
        "cwd": "D:/TestProject"
    })
    result = run_hook(event="session_start", platform="claude_code", stdin_data=stdin_data)
    assert result.exit_code == 0
    print(f"[PASS] Hook: session_start exit_code={result.exit_code}")

    # Test PostToolUse hook
    stdin_data = json.dumps({
        "session_id": "hook-test-session",
        "cwd": "D:/TestProject",
        "tool_name": "write_file",
        "tool_input": {"path": "src/auth.py", "content": "def login(): pass"},
        "tool_response": {"output": "File written successfully"}
    })
    result = run_hook(event="post_tool", platform="claude_code", stdin_data=stdin_data, use_llm=False)
    assert result.exit_code == 0
    print(f"[PASS] Hook: post_tool exit_code={result.exit_code}")


def test_mcp_session_tools():
    from ariadne.mcp.session_tools import (
        SessionStartTool, SessionObserveTool, SessionSearchTool,
        SessionListTool,
    )
    
    # Start session via MCP
    tool = SessionStartTool()
    result = tool.execute({"project_path": "D:/TestProject", "platform": "mcp"})
    assert "session_id" in result
    session_id = result["session_id"]
    print(f"[PASS] MCP: session_start OK, id={session_id[:8]}...")

    # Observe via MCP
    observe_tool = SessionObserveTool()
    result = observe_tool.execute({
        "session_id": session_id,
        "tool_name": "edit_file",
        "tool_input": {"path": "main.py"},
        "tool_output": "Successfully edited",
        "use_llm": False,
    })
    assert "observations_created" in result
    print(f"[PASS] MCP: session_observe OK, obs={result['observations_created']}")

    # Search via MCP
    search_tool = SessionSearchTool()
    result = search_tool.execute({"query": "edit file", "project_path": "D:/TestProject"})
    assert "results" in result
    print(f"[PASS] MCP: session_search OK, results={result['count']}")

    # List via MCP
    list_tool = SessionListTool()
    result = list_tool.execute({"project_path": "D:/TestProject"})
    assert "sessions" in result
    print(f"[PASS] MCP: session_list OK, sessions={result['count']}")


if __name__ == "__main__":
    print("=" * 50)
    print("Ariadne Session Memory — Test Suite")
    print("=" * 50)
    
    tests = [
        ("Session Lifecycle", test_session_lifecycle),
        ("Privacy Tags", test_privacy),
        ("Observation Parser", test_observation_parser),
        ("Hook Runner", test_hook_runner),
        ("MCP Session Tools", test_mcp_session_tools),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        print(f"\n--- {name} ---")
        try:
            test_fn()
            passed += 1
        except Exception as e:
            import traceback
            print(f"[FAIL] {name}: {e}")
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    if failed > 0:
        sys.exit(1)
