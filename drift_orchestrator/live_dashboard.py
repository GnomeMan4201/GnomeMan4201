#!/usr/bin/env python3
from __future__ import annotations

import argparse
import curses
import json
import queue
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.execute_with_policy import execute


SPARK_CHARS = "▁▂▃▄▅▆▇█"
DEGRADE_THRESHOLD = 0.35
ROLLBACK_ACTION = "ROLLBACK"
INJECT_ACTION = "INJECT"
REGENERATE_ACTION = "REGENERATE"


@dataclass
class DashboardState:
    sequence: int | None = None
    timestamp: float | None = None
    alpha: float | None = None
    external: float | None = None
    divergence: float | None = None
    policy_action: str | None = None
    connected: bool = False
    status_text: str = "disconnected"


@dataclass
class StreamPanel:
    source_id: str
    label: str
    state: DashboardState = field(default_factory=DashboardState)
    alpha_hist: deque[float] = field(default_factory=lambda: deque(maxlen=60))
    external_hist: deque[float] = field(default_factory=lambda: deque(maxlen=60))
    divergence_hist: deque[float] = field(default_factory=lambda: deque(maxlen=60))
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=50))
    seq_state: dict[int, DashboardState] = field(default_factory=dict)
    seq_order: deque[int] = field(default_factory=lambda: deque(maxlen=200))


class SSEClientThread(threading.Thread):
    def __init__(self, source_id: str, url: str, events: queue.Queue[dict[str, Any]], stop_event: threading.Event) -> None:
        super().__init__(daemon=True)
        self.source_id = source_id
        self.url = url
        self.events = events
        self.stop_event = stop_event

    def run(self) -> None:
        backoff = 1.0
        while not self.stop_event.is_set():
            self.events.put(
                {
                    "kind": "status",
                    "source_id": self.source_id,
                    "connected": False,
                    "status": f"connecting to {self.url}",
                }
            )
            try:
                req = urllib.request.Request(self.url, headers={"Accept": "text/event-stream"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    self.events.put({"kind": "status", "source_id": self.source_id, "connected": True, "status": "connected"})
                    backoff = 1.0
                    for raw in resp:
                        if self.stop_event.is_set():
                            return
                        line = raw.decode("utf-8", errors="replace").rstrip("\n")
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data:
                            continue
                        try:
                            payload = json.loads(data)
                        except json.JSONDecodeError as exc:
                            self.events.put({"kind": "log", "source_id": self.source_id, "message": f"bad json: {exc}"})
                            continue

                        self.events.put({"kind": "event", "source_id": self.source_id, "payload": payload})
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                self.events.put(
                    {
                        "kind": "status",
                        "source_id": self.source_id,
                        "connected": False,
                        "status": f"disconnected: {exc}. reconnecting in {backoff:.1f}s",
                    }
                )
                self.events.put({"kind": "log", "source_id": self.source_id, "message": f"disconnect: {exc}"})
                for _ in range(int(backoff * 10)):
                    if self.stop_event.is_set():
                        return
                    time.sleep(0.1)
                backoff = min(backoff * 2, 10.0)


def normalize_event(payload: dict[str, Any]) -> dict[str, Any]:
    if "state" in payload and isinstance(payload["state"], dict):
        event = payload["state"].copy()
        if isinstance(payload.get("meta"), dict):
            event.update(payload["meta"])
        return event
    return payload


def to_sparkline(values: list[float], width: int) -> str:
    if width <= 0:
        return ""
    if not values:
        return " " * width

    data = values[-width:]
    min_v = min(data)
    max_v = max(data)
    if max_v == min_v:
        return SPARK_CHARS[0] * len(data)

    out = []
    for value in data:
        idx = int((value - min_v) / (max_v - min_v) * (len(SPARK_CHARS) - 1))
        out.append(SPARK_CHARS[idx])
    return "".join(out)


def _fit(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


def _copy_state(state: DashboardState) -> DashboardState:
    return DashboardState(
        sequence=state.sequence,
        timestamp=state.timestamp,
        alpha=state.alpha,
        external=state.external,
        divergence=state.divergence,
        policy_action=state.policy_action,
        connected=state.connected,
        status_text=state.status_text,
    )


def _resolve_alignment_sequence(panels: list[StreamPanel]) -> int | None:
    valid_sets = []
    for panel in panels:
        if panel.seq_order:
            valid_sets.append(set(panel.seq_order))
    if not valid_sets:
        return None
    common = set.intersection(*valid_sets)
    if common:
        return max(common)
    return None


def _state_for_render(panel: StreamPanel, aligned_seq: int | None) -> DashboardState:
    if aligned_seq is not None and aligned_seq in panel.seq_state:
        aligned = _copy_state(panel.seq_state[aligned_seq])
        aligned.connected = panel.state.connected
        aligned.status_text = panel.state.status_text
        return aligned
    return panel.state


def render(
    stdscr,
    panels: list[StreamPanel],
    first_degrade: str | None,
    first_inject: str | None,
    first_regenerate: str | None,
    first_rollback: str | None,
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()

    title = "Live Drift Dashboard (Multi-Stream)"
    stdscr.addstr(0, max(0, (width - len(title)) // 2), title, curses.A_BOLD)

    aligned_seq = _resolve_alignment_sequence(panels)
    render_states = [(p, _state_for_render(p, aligned_seq)) for p in panels]
    divergences = [(p.label, state.divergence) for p, state in render_states if isinstance(state.divergence, (int, float))]
    if divergences:
        highest = max(divergences, key=lambda item: float(item[1]))
        lowest = min(divergences, key=lambda item: float(item[1]))
        spread = float(highest[1]) - float(lowest[1])
        compare = (
            f"Highest: {highest[0]}={highest[1]:.4f} | Lowest: {lowest[0]}={lowest[1]:.4f} | "
            f"Spread: {spread:.4f} | Leader: {lowest[0]} | Laggard: {highest[0]}"
        )
    else:
        highest = ("-", None)
        lowest = ("-", None)
        compare = "Highest: - | Lowest: - | Spread: - | Leader: - | Laggard: -"
    stdscr.addstr(2, 2, _fit(compare, width - 4), curses.A_BOLD)

    firsts = (
        f"First degrade: {first_degrade or '-'} | First inject: {first_inject or '-'} | "
        f"First regenerate: {first_regenerate or '-'} | First rollback: {first_rollback or '-'}"
    )
    stdscr.addstr(3, 2, _fit(firsts, width - 4), curses.color_pair(1) | curses.A_BOLD)
    seq_line = f"Aligned sequence: {aligned_seq if aligned_seq is not None else 'latest (mismatch)'}"
    stdscr.addstr(4, 2, _fit(seq_line, width - 4), curses.A_DIM)

    n = max(1, len(panels))
    col_w = max(24, width // n)
    col_start_y = 6

    for idx, (panel, view_state) in enumerate(render_states):
        x = idx * col_w
        if x >= width:
            break
        usable_w = min(col_w - 1, width - x - 1)
        if usable_w < 8:
            continue

        label_attr = curses.A_BOLD
        if panel.label == first_degrade:
            label_attr |= curses.color_pair(1)
        if panel.label == first_rollback:
            label_attr |= curses.A_REVERSE

        status_attr = curses.color_pair(2 if view_state.connected else 1)
        div_attr = curses.A_NORMAL
        if panel.label == highest[0]:
            div_attr = curses.color_pair(1) | curses.A_BOLD
        elif panel.label == lowest[0]:
            div_attr = curses.color_pair(2) | curses.A_BOLD

        row = col_start_y
        stdscr.addstr(row, x, _fit(panel.label, usable_w), label_attr)
        row += 1
        stdscr.addstr(row, x, _fit(f"status: {view_state.status_text}", usable_w), status_attr)
        row += 1
        stdscr.addstr(row, x, _fit(f"alpha: {view_state.alpha if view_state.alpha is not None else '-'}", usable_w))
        row += 1
        stdscr.addstr(row, x, _fit(f"external: {view_state.external if view_state.external is not None else '-'}", usable_w))
        row += 1
        stdscr.addstr(
            row,
            x,
            _fit(f"divergence: {view_state.divergence if view_state.divergence is not None else '-'}", usable_w),
            div_attr,
        )
        row += 1
        policy_attr = curses.A_NORMAL
        if str(view_state.policy_action or "") == ROLLBACK_ACTION:
            policy_attr = curses.color_pair(1) | curses.A_BOLD
        stdscr.addstr(row, x, _fit(f"policy: {view_state.policy_action or '-'}", usable_w), policy_attr)
        row += 1

        spark_w = max(5, usable_w - 4)
        spark = to_sparkline(list(panel.divergence_hist), spark_w)
        stdscr.addstr(row, x, _fit(f"spark: {spark}", usable_w))
        row += 1

        if row < height:
            stdscr.addstr(row, x, _fit("recent:", usable_w), curses.A_BOLD)
            row += 1

        for line in list(panel.logs)[-max(1, height - row - 1):]:
            if row >= height - 1:
                break
            stdscr.addstr(row, x, _fit(line, usable_w))
            row += 1

    stdscr.addstr(height - 1, 2, _fit("Press q to quit", width - 4))
    stdscr.refresh()


def run_dashboard(stdscr, urls: list[str], labels: list[str], history_size: int) -> None:
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    stdscr.nodelay(True)

    events: queue.Queue[dict[str, Any]] = queue.Queue()
    stop_event = threading.Event()

    panels: list[StreamPanel] = []
    workers: list[SSEClientThread] = []
    for i, url in enumerate(urls):
        source_id = f"stream_{i}"
        panel_label = labels[i] if i < len(labels) else f"model_{i+1}"
        panel = StreamPanel(source_id=source_id, label=panel_label)
        panel.logs = deque(maxlen=50)
        panel.alpha_hist = deque(maxlen=history_size)
        panel.external_hist = deque(maxlen=history_size)
        panel.divergence_hist = deque(maxlen=history_size)
        panels.append(panel)

        worker = SSEClientThread(source_id, url, events, stop_event)
        workers.append(worker)
        worker.start()

    panel_by_source = {p.source_id: p for p in panels}
    first_degrade: str | None = None
    first_inject: str | None = None
    first_regenerate: str | None = None
    first_rollback: str | None = None

    try:
        for _ in range(max_steps):
            key = stdscr.getch()
            if key in (ord("q"), ord("Q")):
                break

            while True:
                try:
                    message = events.get_nowait()
                except queue.Empty:
                    break

                source_id = message.get("source_id")
                panel = panel_by_source.get(source_id)
                if panel is None:
                    continue

                if message["kind"] == "status":
                    panel.state.connected = bool(message["connected"])
                    panel.state.status_text = str(message["status"])
                elif message["kind"] == "log":
                    panel.logs.append(f"[{time.strftime('%H:%M:%S')}] {message['message']}")
                elif message["kind"] == "event":
                    event = normalize_event(message["payload"])
                    incoming_label = event.get("model_id") or event.get("label")
                    if isinstance(incoming_label, str) and incoming_label.strip():
                        panel.label = incoming_label.strip()

                    panel.state.sequence = event.get("sequence", panel.state.sequence)
                    panel.state.timestamp = event.get("timestamp", panel.state.timestamp)
                    panel.state.alpha = event.get("alpha", panel.state.alpha)
                    panel.state.external = event.get("external", panel.state.external)
                    panel.state.divergence = event.get("divergence", panel.state.divergence)
                    panel.state.policy_action = event.get("policy_action", panel.state.policy_action)
                    seq = panel.state.sequence

                    if isinstance(panel.state.alpha, (int, float)):
                        panel.alpha_hist.append(float(panel.state.alpha))
                    if isinstance(panel.state.external, (int, float)):
                        panel.external_hist.append(float(panel.state.external))
                    if isinstance(panel.state.divergence, (int, float)):
                        panel.divergence_hist.append(float(panel.state.divergence))

                    if (
                        first_degrade is None
                        and isinstance(panel.state.divergence, (int, float))
                        and float(panel.state.divergence) >= DEGRADE_THRESHOLD
                    ):
                        first_degrade = panel.label

                    if first_inject is None and str(panel.state.policy_action or "") == INJECT_ACTION:
                        first_inject = panel.label

                    if first_regenerate is None and str(panel.state.policy_action or "") == REGENERATE_ACTION:
                        first_regenerate = panel.label

                    if first_rollback is None and str(panel.state.policy_action or "") == ROLLBACK_ACTION:
                        first_rollback = panel.label

                    if isinstance(seq, int):
                        panel.seq_state[seq] = _copy_state(panel.state)
                        panel.seq_order.append(seq)
                        valid = set(panel.seq_order)
                        for stale_seq in list(panel.seq_state):
                            if stale_seq not in valid:
                                panel.seq_state.pop(stale_seq, None)

                    panel.logs.append(
                        _fit(
                            f"[{time.strftime('%H:%M:%S')}] seq={panel.state.sequence} α={panel.state.alpha} ext={panel.state.external} div={panel.state.divergence} p={panel.state.policy_action}",
                            120,
                        )
                    )

            render(stdscr, panels, first_degrade, first_inject, first_regenerate, first_rollback)
            time.sleep(0.08)
    finally:
        stop_event.set()
        for worker in workers:
            worker.join(timeout=2)


def main() -> None:

    result = execute("drift_orchestrator", "live_dashboard")
    if not result["executed"]:
        raise SystemExit(result["reason"])

    mode = result["mode"]
    allow_network = mode["allow_network"]
    allow_writeback = mode["allow_writeback"]
    max_steps = mode["max_steps"]

    if not allow_network:
        print("network disabled by control plane")
        return
    parser = argparse.ArgumentParser(description="Live terminal dashboard for drift telemetry SSE stream")
    parser.add_argument(
        "--url",
        action="append",
        dest="urls",
        default=[],
        help="SSE stream URL (repeat for multiple streams)",
    )
    parser.add_argument(
        "--label",
        action="append",
        dest="labels",
        default=[],
        help="Display label for stream column (repeat in same order as --url)",
    )
    parser.add_argument("--history", type=int, default=60, help="sparkline/history window size")
    args = parser.parse_args()

    urls = args.urls or ["http://127.0.0.1:8000/stream"]
    labels = args.labels or []
    if labels and len(labels) > len(urls):
        raise SystemExit("--label count cannot exceed --url count")
    curses.wrapper(run_dashboard, urls, labels, args.history)


if __name__ == "__main__":
    main()
