from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Awaitable, Callable


class PolicyAction(str, Enum):
    CONTINUE = "CONTINUE"
    INJECT = "INJECT"
    REGENERATE = "REGENERATE"
    ROLLBACK = "ROLLBACK"


@dataclass(slots=True)
class SignalDelta:
    sequence: int
    ts: float
    changes: dict[str, Any]


class LiveSignalStream:
    """
    Continuous, async-safe alpha/external stream.

    Insertion point A (session loop):
      call `await stream.update_internal_score(alpha)` whenever alpha mutates.

    Insertion point B (evaluator callback):
      call `stream.evaluate_external_async(<awaitable_factory>)` to run evaluator
      without blocking the active execution loop.

    Insertion point C (policy engine):
      consume `delta.changes.get("policy_action")` when present; the stream emits
      deltas only, never full snapshots.
    """

    def __init__(
        self,
        *,
        initial_alpha: float = 0.0,
        inject_threshold: float = 0.15,
        regenerate_threshold: float = 0.35,
        rollback_threshold: float = 0.60,
        stream_buffer_size: int = 2048,
    ) -> None:
        self._lock = asyncio.Lock()
        self._alpha = float(initial_alpha)
        self._external: float | None = None
        self._divergence: float | None = None
        self._policy_action = PolicyAction.CONTINUE
        self._sequence = 0
        self._delta_queue: asyncio.Queue[SignalDelta] = asyncio.Queue(maxsize=stream_buffer_size)
        self._subscribers: set[asyncio.Queue[SignalDelta]] = set()
        self._thresholds = {
            PolicyAction.INJECT: inject_threshold,
            PolicyAction.REGENERATE: regenerate_threshold,
            PolicyAction.ROLLBACK: rollback_threshold,
        }

    async def update_internal_score(self, alpha: float, *, ts: float | None = None) -> SignalDelta:
        ts = time.time() if ts is None else ts
        async with self._lock:
            changes: dict[str, Any] = {}
            alpha = float(alpha)
            if alpha != self._alpha:
                self._alpha = alpha
                changes["alpha"] = self._alpha

            self._refresh_divergence_locked(changes)
            self._maybe_update_policy_locked(changes)

            return await self._emit_locked(ts=ts, changes=changes)

    async def update_external_score(self, external: float, *, ts: float | None = None) -> SignalDelta:
        ts = time.time() if ts is None else ts
        async with self._lock:
            changes: dict[str, Any] = {}
            external = float(external)
            if self._external != external:
                self._external = external
                changes["external"] = self._external

            self._refresh_divergence_locked(changes)
            self._maybe_update_policy_locked(changes)

            return await self._emit_locked(ts=ts, changes=changes)

    def evaluate_external_async(
        self,
        evaluator: Callable[[], Awaitable[float]],
    ) -> asyncio.Task[None]:
        async def _runner() -> None:
            external = await evaluator()
            await self.update_external_score(external)

        return asyncio.create_task(_runner())

    async def subscribe(self, *, max_buffer: int = 512) -> AsyncIterator[SignalDelta]:
        queue: asyncio.Queue[SignalDelta] = asyncio.Queue(maxsize=max_buffer)
        async with self._lock:
            self._subscribers.add(queue)

        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers.discard(queue)

    async def publish_to_sqlite(
        self,
        writer: Callable[[SignalDelta], Awaitable[None]],
        *,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """
        Compatibility note: writes append-only delta events via existing writer callback,
        keeping existing SQLite schema unchanged.
        """
        async for delta in self.subscribe():
            await writer(delta)
            if stop_event is not None and stop_event.is_set():
                break

    async def stream(self) -> AsyncIterator[SignalDelta]:
        while True:
            yield await self._delta_queue.get()

    async def _emit_locked(self, *, ts: float, changes: dict[str, Any]) -> SignalDelta:
        self._sequence += 1
        delta = SignalDelta(sequence=self._sequence, ts=ts, changes=changes)

        if not changes:
            return delta

        self._put_with_backpressure(self._delta_queue, delta)

        dead_queues: list[asyncio.Queue[SignalDelta]] = []
        for queue in self._subscribers:
            if not self._put_with_backpressure(queue, delta):
                dead_queues.append(queue)

        for queue in dead_queues:
            self._subscribers.discard(queue)

        return delta

    def _refresh_divergence_locked(self, changes: dict[str, Any]) -> None:
        if self._external is None:
            if self._divergence is not None:
                self._divergence = None
                changes["divergence"] = None
            return

        # Explicit divergence definition required by policy contract.
        divergence = abs(self._alpha - self._external)
        if divergence != self._divergence:
            self._divergence = divergence
            changes["divergence"] = divergence

    def _maybe_update_policy_locked(self, changes: dict[str, Any]) -> None:
        divergence = self._divergence
        if divergence is None:
            action = PolicyAction.CONTINUE
        elif divergence >= self._thresholds[PolicyAction.ROLLBACK]:
            action = PolicyAction.ROLLBACK
        elif divergence >= self._thresholds[PolicyAction.REGENERATE]:
            action = PolicyAction.REGENERATE
        elif divergence >= self._thresholds[PolicyAction.INJECT]:
            action = PolicyAction.INJECT
        else:
            action = PolicyAction.CONTINUE

        if action != self._policy_action:
            self._policy_action = action
            changes["policy_action"] = action.value

    @staticmethod
    def _put_with_backpressure(queue: asyncio.Queue[SignalDelta], delta: SignalDelta) -> bool:
        try:
            queue.put_nowait(delta)
            return True
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(delta)
                return True
            return False
