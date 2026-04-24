# Session Memory Hook 系统架构设计

> **作者**: Ariadne Agent
> **日期**: 2026-04-24
> **目的**: 为 Ariadne Session Memory Hook 系统提供详细技术设计

---

## 1. 设计目标

### 1.1 核心目标

1. **5钩子生命周期完整实现** — SessionStart, UserPromptSubmit, PostToolUse, Stop, SessionEnd
2. **SSE 实时推送** — 观察/摘要实时推送到 Web UI
3. **Content-Hash 去重** — 30秒窗口内避免重复观察
4. **多平台适配** — OpenClaw, Claude Code, Cursor, 通用
5. **向后兼容** — 现有 Ariadne Hook 系统无缝集成

### 1.2 非目标

- 不改变现有 Ariadne 记忆/RAG 架构
- 不替换现有 MCP Server 实现
- 不添加独立 Worker Service（复用现有 FastAPI）

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Agent Platform                              │
│   (OpenClaw / Claude Code / Cursor / Generic)                        │
├─────────────────────────────────────────────────────────────────────┤
│                          Hook Events                                  │
│  SessionStart │ UserPromptSubmit │ PostToolUse │ Stop │ SessionEnd  │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    HookRunner (ariadne/hooks/runner.py)               │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │                    Platform Adapters                           │   │
│  │  OpenClawAdapter │ ClaudeCodeAdapter │ CursorAdapter │ ...   │   │
│  └───────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   SessionManager (ariadne/session/)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ SSEBroadcaster│  │ Deduplication │  │  LLM Analyzer │           │
│  │  (实时推送)   │  │     Cache     │  │   (观察生成)  │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
├─────────────────────────────────────────────────────────────────────┤
│                          Data Layer                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ SessionStore │  │ObservationStore│ │Summarizer    │             │
│  │   (SQLite)   │  │(SQLite+Chroma)│  │   (LLM)      │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Web Layer                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  SSE Route   │  │ REST API     │  │   React UI   │             │
│  │ /api/sse     │  │ /api/sessions│  │ /observations│             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
┌──────────────────────────────────────────────────────────────────────┐
│                        PostToolUse 事件处理流程                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. Platform Adapter                                                 │
│     └─→ NormalizedHookInput                                          │
│                                                                       │
│  2. HookRunner                                                       │
│     └─→ SessionManager.record_observation()                          │
│                                                                       │
│  3. SessionManager                                                    │
│     ├─→ DeduplicationCache.check()  ──→ [重复] 跳过                  │
│     └─→ Summarizer.analyze_tool_use()                                │
│                                                                       │
│  4. ObservationStore                                                 │
│     ├─→ SQLite: add_observation()                                    │
│     └─→ ChromaDB: sync_to_chroma()  (异步)                           │
│                                                                       │
│  5. SSEBroadcaster                                                   │
│     └─→ push(new_observation)  ──→ Web UI 实时更新                    │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心组件详细设计

### 3.1 SSEBroadcaster

**文件**: `ariadne/session/sse_broadcaster.py`

```python
"""
SSE Broadcaster — real-time event streaming for Web UI updates.

Provides EventEmitter-style pub/sub for:
- new_observation: 新观察被记录
- new_summary: 新摘要生成
- session_ended: 会话结束
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from typing import Callable, Dict, Set, Optional, Any
from enum import Enum
import weakref

logger = logging.getLogger(__name__)


class SSEEventType(str, Enum):
    """SSE event types broadcast to Web UI clients."""
    NEW_OBSERVATION = "new_observation"
    NEW_SUMMARY = "new_summary"
    SESSION_ENDED = "session_ended"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class SSEEvent:
    """A single SSE event."""
    type: SSEEventType
    session_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None

    def to_sse_line(self) -> str:
        """Format as SSE data line."""
        payload = {
            "type": self.type.value,
            "session_id": self.session_id,
            "data": self.data,
        }
        return f"data: {json.dumps(payload)}\n\n"


class SSEClient:
    """Represents a single SSE client connection."""

    def __init__(
        self,
        client_id: str,
        send_fn: Callable[[str], Any],
        session_filter: Optional[str] = None,
    ):
        self.client_id = client_id
        self.send_fn = send_fn
        self.session_filter = session_filter  # None = subscribe to all
        self.is_connected = True

    async def send(self, message: str) -> None:
        """Send message to client."""
        if self.is_connected:
            try:
                await self.send_fn(message)
            except Exception as e:
                logger.warning(f"SSE send failed for {self.client_id}: {e}")
                self.is_connected = False


class SSEBroadcaster:
    """
    Manages SSE connections and broadcasts events to subscribed clients.

    Thread-safety: All operations are protected by asyncio.Lock.

    Usage:
        broadcaster = SSEBroadcaster()

        # Client connects
        await broadcaster.connect(
            client_id="abc123",
            send_fn=send_function,
            session_filter="session-uuid-1"  # Optional filter
        )

        # Events are broadcast
        await broadcaster.broadcast(SSEEvent(
            type=SSEEventType.NEW_OBSERVATION,
            session_id="session-uuid-1",
            data={"id": "obs1", "summary": "Fixed bug"}
        ))

        # Client disconnects
        await broadcaster.disconnect("abc123")
    """

    def __init__(self):
        self._clients: Dict[str, SSEClient] = {}  # client_id -> SSEClient
        self._session_subscribers: Dict[str, Set[str]] = {}  # session_id -> set of client_ids
        self._global_clients: Set[str] = set()  # client_ids subscribing to all
        self._lock = asyncio.Lock()
        self._heartbeat_task: Optional[asyncio.Task] = None

    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------

    async def connect(
        self,
        client_id: str,
        send_fn: Callable[[str], Any],
        session_filter: Optional[str] = None,
    ) -> None:
        """
        Register a new SSE client connection.

        Args:
            client_id: Unique identifier for this client
            send_fn: Async function to send SSE messages
            session_filter: If provided, only receive events for this session
        """
        async with self._lock:
            client = SSEClient(
                client_id=client_id,
                send_fn=send_fn,
                session_filter=session_filter,
            )
            self._clients[client_id] = client

            if session_filter:
                if session_filter not in self._session_subscribers:
                    self._session_subscribers[session_filter] = set()
                self._session_subscribers[session_filter].add(client_id)
            else:
                self._global_clients.add(client_id)

            logger.debug(f"SSE client connected: {client_id} (filter={session_filter})")

    async def disconnect(self, client_id: str) -> None:
        """Unregister a SSE client."""
        async with self._lock:
            if client_id not in self._clients:
                return

            client = self._clients.pop(client_id)
            client.is_connected = False
            self._global_clients.discard(client_id)

            for subscribers in self._session_subscribers.values():
                subscribers.discard(client_id)

            # Cleanup empty session filters
            self._session_subscribers = {
                k: v for k, v in self._session_subscribers.items() if v
            }

            logger.debug(f"SSE client disconnected: {client_id}")

    # -------------------------------------------------------------------------
    # Broadcasting
    # -------------------------------------------------------------------------

    async def broadcast(self, event: SSEEvent) -> None:
        """
        Broadcast an event to all subscribed clients.

        Args:
            event: The SSE event to broadcast
        """
        message = event.to_sse_line()
        dead_clients: Set[str] = set()

        async with self._lock:
            # Collect clients to notify
            target_clients: Set[str] = set(self._global_clients)

            if event.session_id and event.session_id in self._session_subscribers:
                target_clients.update(self._session_subscribers[event.session_id])

            # Send to each client
            for client_id in target_clients:
                client = self._clients.get(client_id)
                if client and client.is_connected:
                    try:
                        await client.send(message)
                    except Exception as e:
                        logger.warning(f"SSE send failed: {client_id}: {e}")
                        dead_clients.add(client_id)

        # Cleanup dead clients (outside lock)
        for client_id in dead_clients:
            await self.disconnect(client_id)

    async def broadcast_observation(self, observation: dict, session_id: str) -> None:
        """Convenience method to broadcast a new observation."""
        await self.broadcast(SSEEvent(
            type=SSEEventType.NEW_OBSERVATION,
            session_id=session_id,
            data=observation,
        ))

    async def broadcast_summary(self, summary: dict, session_id: str) -> None:
        """Convenience method to broadcast a new summary."""
        await self.broadcast(SSEEvent(
            type=SSEEventType.NEW_SUMMARY,
            session_id=session_id,
            data=summary,
        ))

    async def broadcast_session_end(self, session_id: str) -> None:
        """Convenience method to broadcast session end."""
        await self.broadcast(SSEEvent(
            type=SSEEventType.SESSION_ENDED,
            session_id=session_id,
        ))

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return connection statistics."""
        return {
            "total_clients": len(self._clients),
            "global_subscribers": len(self._global_clients),
            "session_subscriptions": len(self._session_subscribers),
            "active_clients": sum(1 for c in self._clients.values() if c.is_connected),
        }
```

---

### 3.2 DeduplicationCache

**文件**: `ariadne/session/deduplication.py`

```python
"""
Content-hash deduplication for observation deduplication.

Mirrors Claude-Mem's SHA256 content hash with 30-second window.
Prevents duplicate observations when the same action is recorded multiple times.
"""

from __future__ import annotations

import hashlib
import time
import logging
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger(__name__)


class DeduplicationCache:
    """
    Time-windowed content hash deduplication cache.

    Uses a sliding window to track recently seen content hashes.
    Duplicate detection prevents the same observation from being recorded
    multiple times within the configured time window.

    Usage:
        cache = DeduplicationCache(window_seconds=30.0)

        # Check if content is a duplicate
        if not cache.is_duplicate(session_id="s1", title="Fixed bug", narrative="..."):
            # Not a duplicate, proceed to store
            cache.mark_seen(session_id="s1", title="Fixed bug", narrative="...")
            store_observation(...)
    """

    def __init__(self, window_seconds: float = 30.0):
        """
        Initialize the deduplication cache.

        Args:
            window_seconds: Time window for duplicate detection.
                           Default 30 seconds matches Claude-Mem.
        """
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._window = window_seconds
        self._cache: OrderedDict[str, float] = OrderedDict()  # hash -> timestamp
        self._hits = 0
        self._misses = 0

    def _compute_hash(
        self,
        session_id: str,
        title: str,
        narrative: str,
    ) -> str:
        """
        Compute SHA256 content hash.

        Matches Claude-Mem's implementation:
        crypto.createHash('sha256')
            .update(`${sessionId}|${title}|${narrative}`)
            .digest('hex')
        """
        content = f"{session_id}|{title}|{narrative}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _cleanup_expired(self, current_time: float) -> None:
        """Remove expired entries from cache."""
        while self._cache and current_time - list(self._cache.values())[0] > self._window:
            self._cache.popitem(last=False)

    def is_duplicate(
        self,
        session_id: str,
        title: str,
        narrative: str,
    ) -> bool:
        """
        Check if content is a duplicate within the time window.

        Args:
            session_id: Session identifier
            title: Observation title (maps to summary in Ariadne)
            narrative: Observation narrative (maps to detail in Ariadne)

        Returns:
            True if content is a duplicate, False otherwise.
            If False, caller should call mark_seen() after storing.
        """
        current_time = time.time()
        self._cleanup_expired(current_time)

        hash_key = self._compute_hash(session_id, title, narrative)

        if hash_key in self._cache:
            self._hits += 1
            logger.debug(f"Duplicate detected: {title[:50]}...")
            return True

        return False

    def mark_seen(
        self,
        session_id: str,
        title: str,
        narrative: str,
    ) -> None:
        """
        Mark content as seen (after successful storage).

        Args:
            session_id: Session identifier
            title: Observation title
            narrative: Observation narrative
        """
        current_time = time.time()
        hash_key = self._compute_hash(session_id, title, narrative)
        self._cache[hash_key] = current_time
        self._misses += 1

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> dict:
        """Return deduplication statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "window_seconds": self._window,
            "cached_entries": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_dedup_cache: Optional[DeduplicationCache] = None


def get_dedup_cache() -> DeduplicationCache:
    """Get or create the module-level deduplication cache."""
    global _dedup_cache
    if _dedup_cache is None:
        _dedup_cache = DeduplicationCache()
    return _dedup_cache
```

---

### 3.3 SSE Web 路由

**文件**: `ariadne/web/routes/sse.py`

```python
"""
SSE (Server-Sent Events) routes for real-time updates.

Provides /api/sse endpoint for Web UI to subscribe to real-time events.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from ariadne.session.sse_broadcaster import SSEBroadcaster, SSEEvent, SSEEventType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["sse"])

# Module-level broadcaster (initialized by main.py)
_broadcaster: Optional[SSEBroadcaster] = None


def set_broadcaster(b: SSEBroadcaster) -> None:
    """Set the SSE broadcaster (called from main.py)."""
    global _broadcaster
    _broadcaster = b


def get_broadcaster() -> SSEBroadcaster:
    """Get the SSE broadcaster."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = SSEBroadcaster()
    return _broadcaster


@router.get("/sse")
async def sse_stream(
    request: Request,
    session_id: Optional[str] = Query(
        None,
        description="Filter events by session ID. If not provided, receive all events."
    ),
):
    """
    SSE endpoint for real-time event streaming.

    Clients connect to this endpoint and receive events as they occur.

    Event types:
    - new_observation: New observation recorded
    - new_summary: Session summary generated
    - session_ended: Session completed
    - heartbeat: Keep-alive ping

    Query Parameters:
        session_id: Optional filter to only receive events for a specific session

    Headers:
        Accept: text/event-stream
    """

    broadcaster = get_broadcaster()
    client_id = str(uuid.uuid4())

    async def event_generator():
        """Generate SSE events for the client."""

        async def send_fn(message: str):
            """Send function that yields SSE data."""
            yield message

        # Register client
        await broadcaster.connect(
            client_id=client_id,
            send_fn=send_fn,
            session_filter=session_id,
        )

        logger.info(f"SSE client connected: {client_id} (session_filter={session_id})")

        try:
            # Send initial connection event
            yield f"data: {{'type': 'connected', 'client_id': '{client_id}'}}\n\n"

            # Keep connection alive with heartbeats
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                # Send heartbeat every 30 seconds
                yield f"data: {{'type': 'heartbeat', 'timestamp': ''}}\n\n"
                await asyncio.sleep(30)

        except asyncio.CancelledError:
            pass
        finally:
            await broadcaster.disconnect(client_id)
            logger.info(f"SSE client disconnected: {client_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/sse/stats")
async def sse_stats():
    """Get SSE connection statistics (for debugging/monitoring)."""
    broadcaster = get_broadcaster()
    return broadcaster.get_stats()
```

---

## 4. Hook 事件增强设计

### 4.1 SessionManager 集成 SSE

**文件**: `ariadne/session/manager.py` (增强)

```python
# 在 SessionManager.__init__ 中添加:
self._sse_broadcaster: Optional[SSEBroadcaster] = None

def set_sse_broadcaster(self, broadcaster: SSEBroadcaster) -> None:
    """Set SSE broadcaster for real-time updates."""
    self._sse_broadcaster = broadcaster

# 在 record_observation 末尾添加:
if observations and self._sse_broadcaster:
    for obs in observations:
        await self._sse_broadcaster.broadcast_observation(
            observation=obs.to_dict(),
            session_id=session_id,
        )

# 在 end_session 末尾添加:
if summary_obj and self._sse_broadcaster:
    await self._sse_broadcaster.broadcast_summary(
        summary={
            "session_id": session_id,
            "narrative": summary_obj.narrative,
            "key_decisions": summary_obj.key_decisions,
        },
        session_id=session_id,
    )
```

### 4.2 Stop 钩子增强

**目标**: 实现 Claude-Mem 的每 N 条消息触发 Stop 钩子

```python
# ariadne/hooks/runner.py 增强

@dataclass
class HookConfig:
    """Configuration for hook behavior."""
    stop_interval: int = 15  # Trigger Stop hook every N messages
    enable_sse: bool = True   # Enable SSE broadcasting
    dedup_window: float = 30.0  # Deduplication window in seconds


class HookRunner:
    """Enhanced HookRunner with Stop hook support."""

    def __init__(self, config: Optional[HookConfig] = None):
        self.config = config or HookConfig()
        self._message_count: Dict[str, int] = {}  # session_id -> count

    async def handle_event(self, event: str, raw_input: dict) -> Optional[str]:
        """Handle hook event with Stop interval support."""

        # Parse session ID
        session_id = raw_input.get("session_id") or "default"

        # Track message count for PostToolUse events
        if event == "post_tool":
            self._message_count[session_id] = self._message_count.get(session_id, 0) + 1

            # Check if Stop hook should trigger
            if self._message_count[session_id] % self.config.stop_interval == 0:
                # Trigger Stop hook (for mid-session save)
                await self._handle_stop_hook(session_id, raw_input)

        # Continue with normal event handling...
        return await self._dispatch_event(event, raw_input)

    async def _handle_stop_hook(self, session_id: str, raw_input: dict) -> None:
        """Handle Stop hook for mid-session save."""
        logger.info(f"Stop hook triggered for session {session_id}")

        # Get context for injection (without ending session)
        manager = get_manager()
        context = manager.get_semantic_context(
            query=raw_input.get("user_message", ""),
            project_path=raw_input.get("project_path", ""),
        )

        # Emit response (if needed for some platforms)
        return context  # Caller decides how to use this
```

---

## 5. Web UI 组件设计

### 5.1 前端 SSE 客户端

**文件**: `ariadne/web/static/js/sse-client.js`

```javascript
/**
 * SSE Client for real-time observation updates.
 *
 * Connects to /api/sse endpoint and handles events.
 */

class SSEClient {
    constructor(options = {}) {
        this.sessionId = options.sessionId || null;
        this.eventHandlers = new Map();
        this.connection = null;
        this.reconnectDelay = options.reconnectDelay || 1000;
        this.maxReconnectDelay = options.maxReconnectDelay || 30000;
        this.shouldReconnect = true;
    }

    /**
     * Connect to SSE endpoint.
     */
    connect() {
        const url = this.sessionId
            ? `/api/sse?session_id=${encodeURIComponent(this.sessionId)}`
            : '/api/sse';

        this.connection = new EventSource(url);

        this.connection.onopen = () => {
            console.log('SSE connected');
            this.reconnectDelay = 1000; // Reset delay on successful connection
        };

        this.connection.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this._dispatch(data.type, data);
            } catch (e) {
                console.error('SSE parse error:', e);
            }
        };

        this.connection.onerror = (error) => {
            console.error('SSE error:', error);

            if (this.shouldReconnect) {
                setTimeout(() => this.connect(), this.reconnectDelay);
                this.reconnectDelay = Math.min(
                    this.reconnectDelay * 2,
                    this.maxReconnectDelay
                );
            }
        };
    }

    /**
     * Disconnect from SSE endpoint.
     */
    disconnect() {
        this.shouldReconnect = false;
        if (this.connection) {
            this.connection.close();
            this.connection = null;
        }
    }

    /**
     * Register event handler.
     */
    on(eventType, handler) {
        if (!this.eventHandlers.has(eventType)) {
            this.eventHandlers.set(eventType, []);
        }
        this.eventHandlers.get(eventType).push(handler);
    }

    /**
     * Unregister event handler.
     */
    off(eventType, handler) {
        const handlers = this.eventHandlers.get(eventType);
        if (handlers) {
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }

    /**
     * Dispatch event to handlers.
     */
    _dispatch(eventType, data) {
        const handlers = this.eventHandlers.get(eventType);
        if (handlers) {
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (e) {
                    console.error(`SSE handler error (${eventType}):`, e);
                }
            });
        }
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SSEClient;
}
```

### 5.2 观察列表组件

**文件**: `ariadne/web/static/js/components/observations.js`

```javascript
/**
 * Observations list component with SSE real-time updates.
 */

class ObservationsList {
    constructor(containerSelector, options = {}) {
        this.container = document.querySelector(containerSelector);
        this.options = options;
        this.observations = [];
        this.sseClient = new SSEClient({
            sessionId: options.sessionId
        });

        this._init();
    }

    _init() {
        // Register SSE event handlers
        this.sseClient.on('new_observation', (data) => {
            this.addObservation(data.data);
        });

        this.sseClient.on('new_summary', (data) => {
            this.showSummary(data.data);
        });

        // Connect
        this.sseClient.connect();

        // Initial load
        this.loadObservations();
    }

    async loadObservations() {
        try {
            const response = await fetch(
                `/api/sessions/${this.options.sessionId}/observations`
            );
            const data = await response.json();
            this.observations = data.observations || [];
            this.render();
        } catch (e) {
            console.error('Failed to load observations:', e);
        }
    }

    addObservation(obs) {
        this.observations.unshift(obs);

        // Animate new observation
        this.render();

        // Flash effect for new items
        const newItem = this.container.querySelector(`[data-obs-id="${obs.id}"]`);
        if (newItem) {
            newItem.classList.add('highlight');
            setTimeout(() => newItem.classList.remove('highlight'), 2000);
        }
    }

    showSummary(summary) {
        // Show summary toast or update UI
        console.log('Session summary:', summary);
    }

    render() {
        // Simple render - replace with React/Vue in production
        this.container.innerHTML = this.observations
            .map(obs => this._renderObservation(obs))
            .join('');
    }

    _renderObservation(obs) {
        const typeColors = {
            bugfix: '#dc3545',
            feature: '#28a745',
            refactor: '#ffc107',
            general: '#6c757d'
        };
        const color = typeColors[obs.obs_type] || typeColors.general;

        return `
            <div class="observation-item" data-obs-id="${obs.id}">
                <div class="obs-header">
                    <span class="obs-type" style="background: ${color}">
                        ${obs.obs_type}
                    </span>
                    <span class="obs-time">${this._formatTime(obs.created_at)}</span>
                </div>
                <div class="obs-summary">${obs.summary}</div>
                ${obs.detail ? `<div class="obs-detail">${obs.detail}</div>` : ''}
                ${obs.files?.length ? `
                    <div class="obs-files">
                        ${obs.files.map(f => `<span class="file-tag">${f}</span>`).join('')}
                    </div>
                ` : ''}
            </div>
        `;
    }

    _formatTime(isoString) {
        const date = new Date(isoString);
        return date.toLocaleTimeString();
    }

    destroy() {
        this.sseClient.disconnect();
    }
}
```

---

## 6. 文件结构总览

```
ariadne/
├── session/
│   ├── __init__.py
│   ├── manager.py           # 核心管理器 (已存在)
│   ├── models.py             # 数据模型 (已存在)
│   ├── observation_store.py  # 观察存储 (已存在)
│   ├── summarizer.py         # 摘要生成 (已存在)
│   ├── context_builder.py    # 上下文构建 (已存在)
│   ├── store.py              # 会话存储 (已存在)
│   ├── privacy.py            # 隐私过滤 (已存在)
│   ├── sse_broadcaster.py    # 🆕 SSE 实时推送
│   └── deduplication.py      # 🆕 Content-Hash 去重
│
├── hooks/
│   ├── __init__.py
│   ├── base.py               # 基础适配器 (已存在)
│   ├── runner.py             # 钩子执行器 (增强)
│   ├── claude_code.py        # Claude Code (已存在)
│   ├── cursor.py             # Cursor (已存在)
│   ├── openclaw.py          # OpenClaw (已存在)
│   └── generic.py           # 通用适配器 (已存在)
│
└── web/
    ├── main.py               # FastAPI 主入口 (增强)
    ├── routes/
    │   ├── __init__.py
    │   ├── sessions.py        # 会话 API (已存在)
    │   ├── observations.py    # 观察 API (已存在)
    │   ├── search.py          # 搜索 API (已存在)
    │   └── sse.py             # 🆕 SSE 路由
    └── static/
        └── js/
            ├── sse-client.js  # 🆕 SSE 客户端
            └── components/
                └── observations.js  # 🆕 观察列表组件
```

---

## 7. 实现优先级

| 优先级 | 组件 | 工作量 | 依赖 |
|--------|------|--------|------|
| 🔴 P0 | SSEBroadcaster | 2h | 无 |
| 🔴 P0 | SSE 路由 | 1h | SSEBroadcaster |
| 🔴 P0 | 前端 SSE 客户端 | 2h | SSE 路由 |
| 🟡 P1 | DeduplicationCache | 1h | 无 |
| 🟡 P1 | 集成到 SessionManager | 1h | SSEBroadcaster |
| 🟡 P1 | 观察列表组件 | 3h | SSE 客户端 |
| 🟢 P2 | Stop 钩子增强 | 2h | HookRunner |
| 🟢 P2 | 单元测试 | 3h | 所有组件 |

**预计总工时**: ~15 小时

---

## 8. 测试策略

### 8.1 单元测试

```python
# tests/test_sse_broadcaster.py
import pytest
import asyncio

from ariadne.session.sse_broadcaster import (
    SSEBroadcaster, SSEEvent, SSEEventType
)

class TestSSEBroadcaster:
    @pytest.fixture
    def broadcaster(self):
        return SSEBroadcaster()

    @pytest.mark.asyncio
    async def test_connect_disconnect(self, broadcaster):
        messages = []

        async def send_fn(msg):
            messages.append(msg)

        await broadcaster.connect("c1", send_fn)
        assert len(broadcaster._clients) == 1

        await broadcaster.disconnect("c1")
        assert len(broadcaster._clients) == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_session(self, broadcaster):
        messages = []

        async def send_fn(msg):
            messages.append(msg)

        await broadcaster.connect("c1", send_fn, session_filter="s1")

        await broadcaster.broadcast(SSEEvent(
            type=SSEEventType.NEW_OBSERVATION,
            session_id="s1",
            data={"id": "obs1"},
        ))

        assert len(messages) == 1
        assert "obs1" in messages[0]

    @pytest.mark.asyncio
    async def test_global_subscription(self, broadcaster):
        messages = []

        async def send_fn(msg):
            messages.append(msg)

        await broadcaster.connect("c1", send_fn)  # No filter = global

        await broadcaster.broadcast(SSEEvent(
            type=SSEEventType.NEW_SUMMARY,
            session_id="any-session",
            data={"summary": "test"},
        ))

        assert len(messages) == 1


# tests/test_deduplication.py
import pytest
from ariadne.session.deduplication import DeduplicationCache

class TestDeduplicationCache:
    def test_same_content_is_duplicate(self):
        cache = DeduplicationCache(window_seconds=30.0)
        assert cache.is_duplicate("s1", "title", "narrative") == False
        assert cache.is_duplicate("s1", "title", "narrative") == True

    def test_different_content_not_duplicate(self):
        cache = DeduplicationCache(window_seconds=30.0)
        assert cache.is_duplicate("s1", "title1", "narrative") == False
        assert cache.is_duplicate("s1", "title2", "narrative") == False

    def test_different_session_not_duplicate(self):
        cache = DeduplicationCache(window_seconds=30.0)
        assert cache.is_duplicate("s1", "title", "narrative") == False
        assert cache.is_duplicate("s2", "title", "narrative") == False

    def test_window_expiry(self):
        cache = DeduplicationCache(window_seconds=0.1)  # 100ms
        assert cache.is_duplicate("s1", "title", "narrative") == False
        import time; time.sleep(0.2)
        assert cache.is_duplicate("s1", "title", "narrative") == False  # Expired
```

### 8.2 集成测试

```python
# tests/test_sse_integration.py
import pytest
import asyncio

from ariadne.session.sse_broadcaster import SSEBroadcaster, SSEEventType
from ariadne.session.manager import SessionManager

@pytest.mark.asyncio
async def test_observation_triggers_sse():
    """Test that recording observation broadcasts SSE event."""
    broadcaster = SSEBroadcaster()
    manager = SessionManager()
    manager.set_sse_broadcaster(broadcaster)

    received = []

    async def capture_send(msg):
        received.append(msg)

    await broadcaster.connect("test-client", capture_send)

    # Record observation (would normally create session first)
    # This is a simplified test
    await broadcaster.broadcast_observation(
        observation={"id": "obs1", "summary": "Test"},
        session_id="test-session",
    )

    assert len(received) == 1
    assert "new_observation" in received[0]
```

---

**文档版本**: 1.0  
**下次更新**: Phase 3 实现后  
**反馈**: 请提交 Issue 到 GitHub
