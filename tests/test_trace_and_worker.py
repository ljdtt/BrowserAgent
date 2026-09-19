import json
import time

from src.core.agent import BrowserAgent
from src.core.model_adapter import QwenModelAdapter
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


def test_worker_places_browser_screenshots_inside_the_run_trace(tmp_path):
    received = {}

    class ScreenshotAwareAgent:
        def __init__(self, screenshot_dir):
            received["screenshot_dir"] = screenshot_dir

        def run(self, task, on_event=None, cancel_event=None):
            return {"status": "completed", "events": [], "task": task}

    worker = AgentWorker(agent_factory=ScreenshotAwareAgent, trace_base_dir=tmp_path)
    worker.start("short task")
    worker.join(timeout=1)

    assert received["screenshot_dir"] == str(worker.trace_writer.screenshots_dir)


def test_real_browser_can_start_inside_worker_thread(tmp_path):
    class FinishModel:
        def chat(self, **_kwargs):
            return [{
                "role": "assistant",
                "content": "",
                "function_call": {
                    "name": "finish",
                    "arguments": '{"result":"ready","evidence":[]}',
                },
            }]

    def factory(**options):
        return BrowserAgent(
            model_adapter=QwenModelAdapter(model=FinishModel()),
            browser_type="msedge",
            **options,
        )

    worker = AgentWorker(agent_factory=factory, trace_base_dir=tmp_path)
    worker.start("检查浏览器", headless=False)
    result = worker.join(timeout=30)

    assert result["status"] == "completed"


def test_worker_preserves_type_for_an_empty_exception(tmp_path):
    def broken_factory(**_options):
        raise AssertionError()

    worker = AgentWorker(agent_factory=broken_factory, trace_base_dir=tmp_path)
    worker.start("broken")
    result = worker.join(timeout=1)

    assert result["error_message"] == "AssertionError (no message)"
    assert worker.poll()[0]["data"]["exception_type"] == "AssertionError"
