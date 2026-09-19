"""Thread boundary used by interactive clients to run a browser agent."""

from __future__ import annotations

import queue
import inspect
import threading
from pathlib import Path
from typing import Any, Callable

from .agent import BrowserAgent
from .config import Config
from .trace import TraceWriter, redact_event


class AgentWorker:
    def __init__(
        self,
        agent_factory: Callable[..., Any] = BrowserAgent,
        trace_base_dir: str | Path | None = None,
    ):
        self.agent_factory = agent_factory
        self.trace_base_dir = Path(trace_base_dir or Config.ARTIFACT_DIR)
        self.cancel_event = threading.Event()
        self._events: queue.Queue[dict[str, Any]] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._result: dict[str, Any] | None = None
        self.trace_writer: TraceWriter | None = None

    def start(self, task: str, **agent_options: Any) -> None:
        if self.is_alive:
            raise RuntimeError("worker is already running")
        self.cancel_event.clear()
        self._result = None
        self.trace_writer = TraceWriter.create(self.trace_base_dir)
        self._thread = threading.Thread(
            target=self._run,
            args=(task, agent_options),
            name="browser-agent-worker",
            daemon=True,
        )
        self._thread.start()

    def _run(self, task: str, agent_options: dict[str, Any]) -> None:
        def handle_event(event: dict[str, Any]) -> None:
            safe_event = redact_event(event)
            self.trace_writer.write_event(safe_event)
            self._events.put(safe_event)

        try:
            parameters = inspect.signature(self.agent_factory).parameters
            accepts_options = any(item.kind == inspect.Parameter.VAR_KEYWORD
                                  for item in parameters.values())
            if "screenshot_dir" in parameters or accepts_options:
                agent_options.setdefault("screenshot_dir", str(self.trace_writer.screenshots_dir))
            agent = self.agent_factory(**agent_options)
            self._result = agent.run(
                task,
                on_event=handle_event,
                cancel_event=self.cancel_event,
            )
        except Exception as exc:
            self._result = {
                "status": "failed",
                "error_code": "worker_error",
                "error_message": str(exc),
                "events": [],
            }
            handle_event({"kind": "worker_error", "data": {"error": str(exc)}})
        finally:
            self.trace_writer.write_result(self._result)

    def poll(self) -> list[dict[str, Any]]:
        events = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                return events

    def cancel(self) -> None:
        self.cancel_event.set()

    def join(self, timeout: float | None = None) -> dict[str, Any] | None:
        if self._thread is not None:
            self._thread.join(timeout)
        return self._result if not self.is_alive else None

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
