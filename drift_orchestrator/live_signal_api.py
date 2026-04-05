from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from drift_live_signal import LiveSignalStream, SignalDelta


class LiveSignalAPI:
    """Minimal API integration that wraps LiveSignalStream.stream()."""

    def __init__(self, stream: LiveSignalStream, *, client_buffer_size: int = 256) -> None:
        self._stream = stream
        self._client_buffer_size = client_buffer_size
        self._clients: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()
        self._broadcaster_task: asyncio.Task[None] | None = None
        self._latest_state: dict[str, Any] = {
            "sequence": 0,
            "timestamp": None,
            "alpha": None,
            "external": None,
            "divergence": None,
            "policy_action": None,
        }

    def ensure_started(self) -> None:
        if self._broadcaster_task is None or self._broadcaster_task.done():
            self._broadcaster_task = asyncio.create_task(self._broadcast_loop())

    async def _broadcast_loop(self) -> None:
        async for delta in self._stream.stream():
            event = self._to_event(delta)
            async with self._lock:
                dead: list[asyncio.Queue[dict[str, Any]]] = []
                for queue in self._clients:
                    if not self._put_nowait_with_backpressure(queue, event):
                        dead.append(queue)
                for queue in dead:
                    self._clients.discard(queue)

    def _to_event(self, delta: SignalDelta) -> dict[str, Any]:
        self._latest_state["sequence"] = delta.sequence
        self._latest_state["timestamp"] = delta.ts
        self._latest_state.update(delta.changes)
        state = {
            "sequence": self._latest_state["sequence"],
            "timestamp": self._latest_state["timestamp"],
            "alpha": self._latest_state.get("alpha"),
            "external": self._latest_state.get("external"),
            "divergence": self._latest_state.get("divergence"),
        }
        if self._latest_state.get("policy_action") is not None:
            state["policy_action"] = self._latest_state["policy_action"]
        return {
            "type": "state",
            "delta": delta.changes,
            "state": state,
        }

    def _latest_state_event(self) -> dict[str, Any]:
        state = {
            "sequence": self._latest_state["sequence"],
            "timestamp": self._latest_state["timestamp"],
            "alpha": self._latest_state.get("alpha"),
            "external": self._latest_state.get("external"),
            "divergence": self._latest_state.get("divergence"),
        }
        if self._latest_state.get("policy_action") is not None:
            state["policy_action"] = self._latest_state["policy_action"]
        return {
            "type": "state",
            "delta": {},
            "state": state,
        }

    @staticmethod
    def _put_nowait_with_backpressure(queue: asyncio.Queue[dict[str, Any]], item: dict[str, Any]) -> bool:
        try:
            queue.put_nowait(item)
            return True
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                return False
            try:
                queue.put_nowait(item)
                return True
            except asyncio.QueueFull:
                return False

    async def _register_client(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._client_buffer_size)
        async with self._lock:
            self._clients.add(queue)
        return queue

    async def _remove_client(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._clients.discard(queue)

    async def sse_generator(self):
        client_queue = await self._register_client()
        try:
            self._put_nowait_with_backpressure(client_queue, self._latest_state_event())
            while True:
                event = await client_queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            await self._remove_client(client_queue)


def build_live_signal_router(stream: LiveSignalStream) -> APIRouter:
    api = LiveSignalAPI(stream)
    api.ensure_started()

    router = APIRouter()

    @router.get("/stream")
    async def stream_live_signals() -> StreamingResponse:
        return StreamingResponse(api.sse_generator(), media_type="text/event-stream")

    return router
