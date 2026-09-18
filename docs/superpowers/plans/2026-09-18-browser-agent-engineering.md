# BrowserAgent Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible Qwen-powered browser agent with schema-validated tools, snapshot-bound element references, controlled recovery, trace artifacts, a deterministic demo site, evaluation, and a visible Streamlit execution timeline.

**Architecture:** Keep the existing `src/core` entry points and introduce focused modules beside them. `BrowserAgent` owns the observe-decide-execute loop, a model adapter normalizes Qwen-Agent responses, `BrowserController` owns one Playwright lifecycle, and trace/evaluation modules distinguish model-reported completion from verified task success.

**Tech Stack:** Python 3.12+, Qwen-Agent 0.0.34+, Playwright 1.61+, Pydantic 2, Streamlit 1.30+, pytest.

**Spec:** `docs/research/2026-09-18-browser-agent-comparison-and-proposal.md`, refining `docs/superpowers/specs/2026-09-18-browser-agent-engineering-design.md`

## Global Constraints

- Preserve Python, Qwen-Agent, Playwright, and Streamlit as the primary stack.
- Use Qwen-Agent `functions` / `function_call` as the default model action protocol.
- Bind `element_id` values to a specific `snapshot_id`; never reuse them after a mutating action.
- Keep model-reported completion separate from deterministic verification.
- Do not log API keys or input values whose tool schema marks them sensitive.
- Tests and local demo scenarios must run without a real model API call.
- Treat public websites as demonstrations, not deterministic evaluation fixtures.

---

### Task 1: Typed Protocol and Tool Registry

**Files:**
- Create: `src/core/schemas.py`
- Create: `src/core/tools.py`
- Create: `tests/test_schemas_and_tools.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `ElementRef`, `Observation`, `ToolCall`, `ToolResult`, `RunEvent`, `RunResult`, `RunStatus`, and `VerificationStatus` Pydantic models.
- Produces: `TOOL_SCHEMAS: list[dict]` and `parse_tool_call(message: dict) -> ToolCall`.
- `ToolCall` fields are `name: Literal[...]` and `arguments: dict[str, Any]`.

- [ ] **Step 1: Add dependency and write failing protocol tests**

```python
def test_parse_tool_call_rejects_unknown_tool():
    with pytest.raises(ToolProtocolError, match="unknown tool"):
        parse_tool_call({"function_call": {"name": "delete_everything", "arguments": "{}"}})

def test_parse_tool_call_validates_snapshot_bound_click():
    call = parse_tool_call({"function_call": {
        "name": "click",
        "arguments": '{"snapshot_id":"snap-1","element_id":3}'
    }})
    assert call.arguments == {"snapshot_id": "snap-1", "element_id": 3}

def test_run_result_separates_completion_from_verification():
    result = RunResult(status="completed", verification_status="failed", reported_result="done")
    assert result.status == RunStatus.COMPLETED
    assert result.verification_status == VerificationStatus.FAILED
```

- [ ] **Step 2: Run `python -m pytest tests/test_schemas_and_tools.py -v` and verify import failures**

- [ ] **Step 3: Implement Pydantic models and JSON-schema-backed tool validation**

```python
class ToolCall(BaseModel):
    name: ToolName
    arguments: dict[str, Any]

def parse_tool_call(message: dict[str, Any]) -> ToolCall:
    raw = message.get("function_call")
    if not raw:
        raise ToolProtocolError("missing function_call")
    name = raw.get("name")
    if name not in TOOL_ARGUMENT_MODELS:
        raise ToolProtocolError(f"unknown tool: {name}")
    arguments = json.loads(raw.get("arguments") or "{}")
    validated = TOOL_ARGUMENT_MODELS[name].model_validate(arguments)
    return ToolCall(name=name, arguments=validated.model_dump())
```

- [ ] **Step 4: Run the focused test, then `python -m pytest -q`**

- [ ] **Step 5: Commit `feat: add typed browser tool protocol`**

### Task 2: Snapshot-Bound Observation and Playwright Actions

**Files:**
- Create: `src/core/observer.py`
- Modify: `src/core/browser_controller.py`
- Create: `tests/fixtures/demo_page.html`
- Create: `tests/test_browser_controller.py`

**Interfaces:**
- Consumes: `Observation`, `ElementRef`, `ToolCall`, and `ToolResult` from Task 1.
- Produces: `PageObserver.observe(page) -> Observation`.
- Produces: `BrowserController.execute(call: ToolCall) -> ToolResult`, plus compatible `navigate`, `click`, `type_text`, `press_enter`, `scroll`, `select_option`, `get_page_state`, and `screenshot` entry points.

- [ ] **Step 1: Write browser integration tests against a local fixture**

```python
def test_click_and_fill_use_ids_from_the_same_snapshot(controller, demo_url):
    observation = controller.navigate(demo_url).observation
    query = next(item for item in observation.elements if item.placeholder == "课程关键词")
    submit = next(item for item in observation.elements if item.text == "搜索")
    filled = controller.execute(ToolCall(name="fill", arguments={
        "snapshot_id": observation.snapshot_id, "element_id": query.element_id, "text": "Python"
    }))
    assert filled.ok is True
    stale = controller.execute(ToolCall(name="click", arguments={
        "snapshot_id": observation.snapshot_id, "element_id": submit.element_id
    }))
    assert stale.error_code == "stale_element"

def test_observation_includes_visible_body_text(controller, demo_url):
    observation = controller.navigate(demo_url).observation
    assert "课程目录" in observation.text
```

- [ ] **Step 2: Run `python -m pytest tests/test_browser_controller.py -v` and verify missing API failures**

- [ ] **Step 3: Implement one selector map per observation**

```javascript
elements.forEach((element, index) => {
  element.setAttribute("data-browser-agent-id", String(index));
  output.push({element_id: index, tag: element.tagName.toLowerCase(), ...});
});
```

`PageObserver` creates a UUID `snapshot_id`. `BrowserController` stores only the current snapshot, rejects a mismatched ID, locates `[data-browser-agent-id="N"]`, and uses `locator.click()`, `locator.fill()`, `locator.select_option()`, and `page.keyboard.press()`.

- [ ] **Step 4: Make every mutating action invalidate the old snapshot and return a fresh observation**

- [ ] **Step 5: Run focused tests and the full suite**

- [ ] **Step 6: Commit `feat: add snapshot-bound browser actions`**

### Task 3: Qwen Adapter and Controlled Agent Loop

**Files:**
- Create: `src/core/model_adapter.py`
- Modify: `src/core/agent.py`
- Modify: `src/core/config.py`
- Create: `tests/test_model_adapter.py`
- Create: `tests/test_agent_loop.py`

**Interfaces:**
- Consumes: `TOOL_SCHEMAS`, `parse_tool_call`, protocol models, and `BrowserController.execute`.
- Produces: `QwenModelAdapter.next(messages: list[dict], functions: list[dict]) -> dict`.
- Produces: `BrowserAgent.run(task: str, verifier: Callable | None = None, on_event: Callable | None = None) -> dict` while preserving the existing dictionary result boundary.

- [ ] **Step 1: Write adapter contract tests for Qwen's non-stream return shape**

```python
def test_adapter_returns_last_assistant_message():
    model = FakeQwenModel([[{"role": "assistant", "content": "", "function_call": {
        "name": "finish", "arguments": '{"result":"完成","evidence":[]}'
    }}]])
    assert QwenModelAdapter(model).next([], TOOL_SCHEMAS)["function_call"]["name"] == "finish"
```

- [ ] **Step 2: Run adapter test and verify the missing class failure**

- [ ] **Step 3: Implement adapter without iterating `stream=False` as a generator**

```python
responses = self.model.chat(messages=messages, functions=functions, stream=False)
if not responses:
    raise ModelResponseError("empty model response")
return dict(responses[-1])
```

- [ ] **Step 4: Write failing loop tests using a scripted model and fake browser**

```python
def test_agent_stops_repeated_invalid_calls(scripted_agent):
    result = scripted_agent([unknown_call] * 3).run("do something")
    assert result["status"] == "failed"
    assert result["error_code"] == "invalid_model_output"

def test_agent_marks_reported_finish_unverified(scripted_agent):
    result = scripted_agent([finish_call]).run("task")
    assert result["status"] == "completed"
    assert result["verification_status"] == "not_checked"
```

- [ ] **Step 5: Implement observe-decide-execute loop with max steps, elapsed timeout, invalid-call limit, and no-progress fingerprint**

The fingerprint is `(tool_name, normalized_arguments, observation.url, observation.text[:500])`. Two invalid calls or three unchanged fingerprints terminate with explicit codes. The loop adds assistant tool calls and `role=function` results to message history. `finally` always closes the browser.

- [ ] **Step 6: Keep `parse_action` only as a deprecated compatibility helper; the main loop must use function calls**

- [ ] **Step 7: Run focused tests and full suite**

- [ ] **Step 8: Commit `feat: run browser agent through validated tool calls`**

### Task 4: Run Artifacts, Redaction, and Worker Events

**Files:**
- Create: `src/core/trace.py`
- Create: `src/core/worker.py`
- Modify: `src/core/config.py`
- Create: `tests/test_trace_and_worker.py`

**Interfaces:**
- Consumes: `RunEvent` and `RunResult`.
- Produces: `TraceWriter.create(base_dir)`, `TraceWriter.write_event(event)`, `TraceWriter.write_result(result)`, and `redact_event(event)`.
- Produces: `AgentWorker.start(task, **options)`, `poll()`, `cancel()`, and `join(timeout)`.

- [ ] **Step 1: Write tests for isolated run paths and redaction**

```python
def test_trace_writer_never_serializes_sensitive_fill_text(tmp_path):
    writer = TraceWriter.create(tmp_path)
    writer.write_event(RunEvent(kind="tool", data={
        "name": "fill", "arguments": {"text": "secret", "sensitive": True}
    }))
    assert "secret" not in writer.events_path.read_text(encoding="utf-8")

def test_two_runs_use_different_directories(tmp_path):
    assert TraceWriter.create(tmp_path).run_dir != TraceWriter.create(tmp_path).run_dir
```

- [ ] **Step 2: Run the focused test and verify missing implementations**

- [ ] **Step 3: Implement JSONL events, result JSON, run-scoped screenshots, and allowlist-based redaction**

- [ ] **Step 4: Add a worker thread whose browser and event loop stay inside that thread; expose only queues and a cancellation event**

- [ ] **Step 5: Test cancellation and resource cleanup with a scripted agent, then run the full suite**

- [ ] **Step 6: Commit `feat: persist browser agent run traces`**

### Task 5: Deterministic Demo Site and Evaluation

**Files:**
- Create: `demo_site/index.html`
- Create: `demo_site/app.js`
- Create: `demo_site/styles.css`
- Create: `evals/tasks.json`
- Create: `evals/verifiers.py`
- Create: `evals/run.py`
- Create: `tests/test_verifiers.py`
- Create: `tests/test_demo_scenarios.py`

**Interfaces:**
- Consumes: `BrowserAgent.run(..., verifier=...)` and run results.
- Produces: `verify_task(task_id: str, observation: Observation, reported_result: str | None) -> VerificationResult`.
- Produces CLI: `python -m evals.run --mode scripted --base-url URL` and optional `--mode qwen`.

- [ ] **Step 1: Write verifier tests from literal expected course and submission records**

```python
def test_course_task_requires_matching_name_duration_and_link():
    result = verify_course_result({
        "name": "Python 入门", "hours": 18, "url": "/courses/python-intro"
    })
    assert result.passed is True

def test_form_task_rejects_success_banner_with_wrong_payload():
    result = verify_submission({"banner": "提交成功", "name": "李雷", "course": "错误课程"})
    assert result.passed is False
```

- [ ] **Step 2: Run verifier tests and verify missing implementation failures**

- [ ] **Step 3: Implement the static site with course search, detail navigation, and a local submission receipt**

- [ ] **Step 4: Implement 15 tasks split into six development and nine holdout tasks; keep split metadata in `tasks.json`**

- [ ] **Step 5: Add scripted end-to-end scenarios and metric aggregation for pass count, average steps, average and P95 duration, model calls, and error categories**

- [ ] **Step 6: Run unit and browser scenario tests; run scripted evaluation and save its report under a run artifact directory**

- [ ] **Step 7: Commit `feat: add deterministic browser agent evaluation`**

### Task 6: Streamlit Timeline, CLI, and Documentation

**Files:**
- Modify: `src/app/streamlit_app.py`
- Modify: `src/demo/run_demo.py`
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `.gitignore`
- Modify: `resume_text.txt`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `AgentWorker`, trace files, and the existing `BrowserAgent` result dictionary.
- Produces: a live Streamlit timeline, cancellation control, trace download, and a CLI JSON output option.

- [ ] **Step 1: Write a CLI behavior test that runs a scripted scenario and parses the JSON result**

```python
def test_cli_scripted_mode_returns_verification_status():
    completed = subprocess.run(
        [sys.executable, "-m", "src.demo.run_demo", "--scripted", "course-search", "--json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["verification_status"] == "passed"
```

- [ ] **Step 2: Run the CLI test and verify argument parsing fails**

- [ ] **Step 3: Update CLI and Streamlit to use workers, display reported and verified states separately, and expose trace download**

- [ ] **Step 4: Document installation, architecture, demo, tests, evaluation protocol, privacy limits, and public-site limitations**

- [ ] **Step 5: Replace resume claims with only features supported by fresh tests and evaluation output; leave measured values blank if real Qwen evaluation cannot run**

- [ ] **Step 6: Run `python -m pytest -q`, `python -m compileall -q src evals`, scripted evaluation, and a Streamlit startup smoke test**

- [ ] **Step 7: Commit `docs: document verified BrowserAgent capabilities`**

## Completion Review

- [ ] Re-read both spec documents and map every included requirement to an implementation or an explicitly documented limitation.
- [ ] Confirm every new behavior had a failing test before production code.
- [ ] Inspect `git diff --check`, ensure `.env` and run artifacts are ignored, and scan tracked files for API-key patterns.
- [ ] Run the full verification set from Task 6 with fresh output.
