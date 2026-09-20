import json
import threading

from src.core.agent import BrowserAgent
from src.core.model_adapter import QwenModelAdapter
from src.core.schemas import Observation, ToolResult, VerificationResult


def function_call(name, arguments):
    return {
        "role": "assistant",
        "content": "",
        "function_call": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
    }


class ScriptedModel:
    def __init__(self, messages):
        self.messages = list(messages)

    def chat(self, **_kwargs):
        return [self.messages.pop(0)]


class FakeBrowser:
    def __init__(self):
        self.closed = False
        self.executed = []
        self.observation = Observation(
            snapshot_id="snap-1", title="Demo", url="https://example.test", text="演示页面"
        )

    def start(self):
        pass

    def observe(self):
        return ToolResult(ok=True, action="observe", observation=self.observation)

    def execute(self, call):
        self.executed.append(call)
        self.observation = self.observation.model_copy(update={"snapshot_id": f"snap-{len(self.executed) + 1}"})
        return ToolResult(ok=True, action=call.name, observation=self.observation)

    def screenshot(self, name=None):
        return f"screenshots/{name}.png"

    def close(self):
        self.closed = True


class EmptyErrorBrowser(FakeBrowser):
    def start(self):
        raise AssertionError()


def make_agent(messages, browser=None, **options):
    browser = browser or FakeBrowser()
    adapter = QwenModelAdapter(model=ScriptedModel(messages))
    return BrowserAgent(model_adapter=adapter, browser=browser, **options), browser


def test_agent_marks_reported_finish_unverified():
    agent, browser = make_agent([
        function_call("finish", {"success": True, "result": "任务完成", "evidence": ["演示页面"]})
    ])

    result = agent.run("检查演示页面")

    assert result["status"] == "completed"
    assert result["verification_status"] == "not_checked"
    assert result["reported_result"] == "任务完成"
    assert browser.closed is True


def test_agent_marks_model_reported_blocker_as_failed():
    agent, browser = make_agent([
        function_call("finish", {
            "success": False,
            "result": "连接被拒绝，任务无法继续",
            "evidence": [],
        })
    ])

    result = agent.run("访问不可用页面")

    assert result["status"] == "failed"
    assert result["error_code"] == "model_reported_failure"
    assert result["reported_result"] == "连接被拒绝，任务无法继续"
    assert browser.closed is True


def test_agent_stops_after_repeated_invalid_model_calls():
    unknown = function_call("delete_everything", {})
    agent, _browser = make_agent([unknown, unknown], max_invalid_calls=2)

    result = agent.run("do something")

    assert result["status"] == "failed"
    assert result["error_code"] == "invalid_model_output"
    assert result["model_calls"] == 2


def test_agent_executes_tool_and_records_function_feedback():
    agent, browser = make_agent([
        function_call("navigate", {"url": "https://example.test/course"}),
        function_call("finish", {"success": True, "result": "已打开课程", "evidence": ["course"]}),
    ])

    result = agent.run("打开课程")

    assert [call.name for call in browser.executed] == ["navigate"]
    assert result["steps"] == 1
    assert result["screenshots"] == ["screenshots/step_01.png"]


def test_agent_keeps_verifier_failure_separate_from_completion():
    agent, _browser = make_agent([
        function_call("finish", {"success": True, "result": "完成", "evidence": []})
    ])

    result = agent.run(
        "提交表单",
        verifier=lambda _observation, _reported: VerificationResult(
            status="failed", reason="提交内容不匹配"
        ),
    )

    assert result["status"] == "completed"
    assert result["verification_status"] == "failed"
    assert result["verification_reason"] == "提交内容不匹配"


def test_agent_reports_max_steps_and_closes_browser():
    agent, browser = make_agent([
        function_call("navigate", {"url": "https://example.test/1"}),
        function_call("navigate", {"url": "https://example.test/2"}),
    ], max_steps=2)

    result = agent.run("继续导航")

    assert result["status"] == "max_steps_exceeded"
    assert result["steps"] == 2
    assert browser.closed is True


def test_agent_honors_a_preexisting_cancellation_request():
    cancelled = threading.Event()
    cancelled.set()
    agent, browser = make_agent([])

    result = agent.run("不要执行", cancel_event=cancelled)

    assert result["status"] == "cancelled"
    assert result["model_calls"] == 0
    assert browser.closed is True


def test_sensitive_fill_is_not_exposed_or_screenshotted():
    secret = "private-password"
    agent, _browser = make_agent([
        function_call("fill", {
            "snapshot_id": "snap-1", "element_id": 0, "text": secret, "sensitive": True,
        }),
        function_call("finish", {"success": True, "result": f"已填写 {secret}", "evidence": [secret]}),
    ])

    result = agent.run("填写密码")

    assert secret not in json.dumps(result, ensure_ascii=False)
    assert result["screenshots"] == []


def test_different_actions_on_unchanged_page_are_progress():
    agent, _browser = make_agent([
        function_call("fill", {
            "snapshot_id": "snap-1", "element_id": 0, "text": "李雷", "sensitive": False,
        }),
        function_call("fill", {
            "snapshot_id": "snap-2", "element_id": 1, "text": "lilei@example.com", "sensitive": False,
        }),
        function_call("finish", {"success": True, "result": "填写完成", "evidence": []}),
    ], max_no_progress=1)

    result = agent.run("填写两个字段")

    assert result["status"] == "completed"
    assert result["steps"] == 2


def test_repeated_equivalent_actions_ignore_ephemeral_snapshot_ids():
    agent, _browser = make_agent([
        function_call("fill", {
            "snapshot_id": "snap-1", "element_id": 0, "text": "same", "sensitive": False,
        }),
        function_call("fill", {
            "snapshot_id": "snap-2", "element_id": 0, "text": "same", "sensitive": False,
        }),
    ], max_no_progress=1)

    result = agent.run("重复填写")

    assert result["status"] == "failed"
    assert result["error_code"] == "no_progress"


def test_empty_exception_still_produces_actionable_error_message():
    browser = EmptyErrorBrowser()
    agent, _browser = make_agent([], browser=browser)

    result = agent.run("启动浏览器")

    assert result["status"] == "failed"
    assert result["error_message"] == "AssertionError (no message)"
    assert result["events"][0]["data"]["exception_type"] == "AssertionError"
