# Ariadne Auto-Save Hook Documentation

> Automatic Memory Persistence System

## Overview

Ariadne provides automatic memory saving through lifecycle hooks, inspired by MemPalace's hook system.

## Hook Types

| Hook | Trigger | Default Interval | Use Case |
|------|---------|-----------------|----------|
| Stop | N messages | 15 | Regular save |
| PreCompact | Before compression | - | Preserve before cleanup |
| SessionStart | Session begin | - | Load state |
| SessionEnd | Session end | - | Final save |
| Idle | 5 min idle | - | Background save |
| Manual | User trigger | - | Explicit save |

## Usage

### Basic Setup

```python
from ariadne.plugins.autosave import create_default_hook_manager
from ariadne.memory.layers import MemoryStack

# Create memory stack
stack = MemoryStack()

# Create hook manager with defaults
hook_manager = create_default_hook_manager(
    memory_stack=stack,
    persist_path="./data/memory_stack.json"
)

# Start hooks
hook_manager.start()

# ... use memory ...

# Stop hooks (auto-saves on end)
hook_manager.stop()
```

### Custom Configuration

```python
from ariadne.plugins.autosave import HookConfig, HookManager

config = HookConfig(
    stop_message_interval=20,     # Save after 20 messages
    pre_compact_enabled=True,      # Save before compression
    save_on_start=True,           # Load state on start
    save_on_end=True,             # Final save on end
    idle_timeout_seconds=300,     # 5 minutes idle
    idle_check_interval=60,       # Check every minute
    auto_backup=True,            # Create backups
    backup_count=3               # Keep 3 backups
)

hook_manager = HookManager(
    memory_stack=stack,
    auto_save_config=config
)
```

### Manual Trigger

```python
# Manually trigger save
hook_manager.auto_save.trigger(HookType.MANUAL)

# Trigger specific hook
hook_manager.auto_save.trigger(HookType.SESSION_END, reason="user_logout")
```

### Custom Hook Handlers

```python
from ariadne.plugins.autosave import HookEvent

def on_save_completed(event: HookEvent):
    """Custom handler after save."""
    print(f"Saved at {event.timestamp}")
    print(f"Context size: {event.context_size} tokens")
    print(f"Messages: {event.message_count}")

# Register handler
hook_manager.auto_save.register_hook(
    hook_type=HookType.STOP,
    handler=on_save_completed
)
```

## Claude Code Integration

### Overview

The ClaudeCodeHook provides integration with Claude Code sessions:

```python
from ariadne.plugins.autosave import ClaudeCodeHook

claude_hook = ClaudeCodeHook(memory_stack=stack)
```

### Tracking Tool Usage

```python
# Call after each tool use
claude_hook.on_tool_use(
    tool_name="Read",
    tool_args={"file_path": "config.json"}
)
```

### Tracking File Modifications

```python
# Call after file changes
claude_hook.on_file_modified(
    file_path="src/main.py",
    operation="modify"  # "create", "modify", "delete"
)
```

### Recording Errors

```python
# Call on error
claude_hook.on_error(
    error="File not found",
    context="Trying to read config.json"
)
```

### Project Context

```python
# Set project context
claude_hook.on_project_context(
    project_name="MyProject",
    project_type="python",
    key_files=["src/main.py", "config.json"]
)
```

### Getting Statistics

```python
# Get tool usage summary
tool_stats = claude_hook.get_tool_usage_summary()
# {"Read": 15, "Edit": 8, "Write": 3, ...}

# Get modified files
modified = claude_hook.get_modified_files()
# ["src/main.py", "config.json", "tests/test.py"]
```

## Stop Hook Details

The Stop hook is the primary auto-save mechanism:

```python
from ariadne.plugins.autosave import AutoSaveHook

hook = AutoSaveHook(memory_stack=stack)

# Call after each message in conversation
hook.on_message()  # Increments counter

# When counter reaches threshold (default 15), auto-saves
```

### Custom Message Counter

```python
config = HookConfig(stop_message_interval=10)  # Save every 10 messages
```

## PreCompact Hook

The PreCompact hook fires before context compression:

```python
from ariadne.plugins.autosave import HookType

def before_compact(event: HookEvent):
    """Save critical context before compression."""
    # Save to permanent layer
    stack.l0_identity.set_identity(
        "last_compact_time",
        event.timestamp
    )

hook_manager.auto_save.register_hook(
    hook_type=HookType.PRE_COMPACT,
    handler=before_compact
)
```

## Idle Detection

Idle hooks trigger after a period of inactivity:

```python
config = HookConfig(
    idle_timeout_seconds=600,  # 10 minutes
    idle_check_interval=120   # Check every 2 minutes
)
```

## Status Monitoring

```python
# Get hook system status
status = hook_manager.get_status()

# Output:
# {
#     "auto_save": {
#         "running": True,
#         "message_count": 12,
#         "last_save_time": 1713772800.0,
#         "idle_seconds": 45.2,
#         "hooks_registered": {
#             "stop": 1,
#             "pre_compact": 1,
#             "idle": 1
#         }
#     },
#     "claude_code": {
#         "tool_usage": {"Read": 15},
#         "modified_files_count": 3
#     }
# }
```

## Backup Management

Backups are automatically created when auto-save is enabled:

```python
config = HookConfig(
    auto_backup=True,
    backup_count=5  # Keep 5 backups
)
```

### Backup Location

```
.ariadne/backups/
├── memory_stack_20240422_143000.json
├── memory_stack_20240422_144500.json
└── memory_stack_20240422_150000.json
```

## Integration Examples

### CLI Integration

```python
# In your CLI application
from ariadne.cli import cli
from ariadne.plugins.autosave import create_default_hook_manager

@cli.command()
def chat():
    stack = MemoryStack()
    hook_manager = create_default_hook_manager(stack)
    hook_manager.start()

    try:
        # Chat loop
        for message in chat_messages:
            response = chat(message)
            hook.on_message()  # Track messages
    finally:
        hook_manager.stop()
```

### MCP Server Integration

```python
# In MCP server
from ariadne.mcp.server import AriadneMCPServer
from ariadne.plugins.autosave import create_default_hook_manager

server = AriadneMCPServer()

# Create hook manager
hook_manager = create_default_hook_manager(
    memory_stack=server.memory_stack,
    persist_path=server.persist_path
)
hook_manager.start()

# In handle_request, track messages
def handle_request(message):
    hook_manager.auto_save.on_message()  # Increment counter
    # ... handle request ...
```

## Related

- [Memory Stack](MemoryStack.md) - 4-layer memory architecture
- [Closet Index](Closet.md) - AAAK indexing
