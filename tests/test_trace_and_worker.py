import json
import time

from src.core.schemas import RunEvent
from src.core.trace import TraceWriter
from src.core.worker import AgentWorker


def test_trace_writer_never_serializes_sensitive_fill_text(tmp_path):
    writer = TraceWriter.create(tmp_path)
    writer.write_event(RunEvent(kind="tool_requested", data={
        "name": "fill",
        "arguments": {"text": "secret-value", "sensitive": True},
    }))

    saved = writer.events_path.read_text(encoding="utf-8")

    assert "secret-value" not in saved
    assert "[REDACTED]" in saved


def test_two_runs_use_different_directories(tmp_path):
    first = TraceWriter.create(tmp_path)
    second = TraceWriter.create(tmp_path)

    assert first.run_dir != second.run_dir
    assert first.screenshots_dir.is_dir()
    assert second.screenshots_dir.is_dir()


def test_trace_writer_persists_result_json(tmp_path):
    writer = TraceWriter.create(tmp_path)
    writer.write_result({"status": "completed", "reported_result": "done"})

    assert json.loads(writer.result_path.read_text(encoding="utf-8"))["status"] == "completed"


class CooperativeAgent:
    def run(self, task, on_event=None, cancel_event=None):
        on_event({"kind": "run_started", "data": {"task": task}})
        while not cancel_event.is_set():
            time.sleep(0.005)
        return {"status": "cancelled", "events": []}


def test_worker_streams_events_and_cancels_cooperatively(tmp_path):
    worker = AgentWorker(agent_factory=CooperativeAgent, trace_base_dir=tmp_path)
    worker.start("long task")

    deadline = time.time() + 1
    events = []
    while time.time() < deadline and not events:
        events = worker.poll()
        time.sleep(0.005)
    worker.cancel()
    result = worker.join(timeout=1)

    assert events[0]["kind"] == "run_started"
    assert result["status"] == "cancelled"
    assert worker.is_alive is False
    assert worker.trace_writer.result_path.exists()
