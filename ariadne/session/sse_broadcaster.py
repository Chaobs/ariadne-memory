"""
SSE Broadcaster — real-time event streaming for Web UI updates.

Provides EventEmitter-style pub/sub for:
- new_observation: 新观察被记录
- new_summary: 新摘要生成
- session_ended: 会话结束
- error: 错误事件
- heartbeat: 心跳保活

Inspired by Claude-Mem's SSEBroadcaster and SessionManager EventEmitter pattern.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, Set, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event Types
# ---------------------------------------------------------------------------


class SSEEventType(str, Enum):
    """SSE event types broadcast to Web UI clients."""
    NEW_OBSERVATION = "new_observation"
    NEW_SUMMARY = "new_summary"
    SESSION_ENDED = "session_ended"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


# ---------------------------------------------------------------------------
# SSE Event
# ---------------------------------------------------------------------------


@dataclass
class SSEEvent:
    """A single SSE event."""
    type: SSEEventType
    session_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            from datetime import datetime, timezone
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_sse_line(self) -> str:
        """Format as SSE data line."""
        payload = {
            "type": self.type.value,
            "session_id": self.session_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }
        return f"data: {json.dumps(payload)}\n\n"


# ---------------------------------------------------------------------------
# SSE Client
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# SSE Broadcaster
# ---------------------------------------------------------------------------


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

    async def broadcast_error(self, error: str, session_id: Optional[str] = None) -> None:
        """Convenience method to broadcast an error."""
        await self.broadcast(SSEEvent(
            type=SSEEventType.ERROR,
            session_id=session_id,
            data={"error": error},
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


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_broadcaster: Optional[SSEBroadcaster] = None


def get_broadcaster() -> SSEBroadcaster:
    """Get or create the module-level SSE broadcaster singleton."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = SSEBroadcaster()
    return _broadcaster
