"""
SSE (Server-Sent Events) routes for real-time Session Memory updates.

Provides /api/sse endpoint for Web UI to subscribe to real-time events:
- new_observation: New observation recorded
- new_summary: Session summary generated
- session_ended: Session completed
- heartbeat: Keep-alive ping

Inspired by Claude-Mem's SSE implementation.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from ariadne.session.sse_broadcaster import SSEBroadcaster, get_broadcaster

logger = logging.getLogger(__name__)

# Create router
sse_router = APIRouter(prefix="/api/sse", tags=["SSE"])


@sse_router.get("")
async def sse_stream(
    request: Request,
    session_id: Optional[str] = Query(
        None,
        description="Filter events by session ID. If not provided, receive all events.",
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


@sse_router.get("/stats")
async def sse_stats():
    """Get SSE connection statistics (for debugging/monitoring)."""
    broadcaster = get_broadcaster()
    return broadcaster.get_stats()


@sse_router.get("/dedup/stats")
async def dedup_stats():
    """Get deduplication cache statistics."""
    from ariadne.session.deduplication import get_dedup_cache
    return get_dedup_cache().get_stats()
