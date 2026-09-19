"""Run reproducible scripted evaluation or an optional live Qwen evaluation."""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.agent import BrowserAgent
from src.core.browser_controller import BrowserController
from src.core.config import Config
from src.core.schemas import Observation, ToolCall

from .verifiers import verify_task


ROOT = Path(__file__).parents[1]


def load_tasks(split: str = "all") -> list[dict[str, Any]]:
    tasks = json.loads((Path(__file__).with_name("tasks.json")).read_text(encoding="utf-8"))
    return tasks if split == "all" else [task for task in tasks if task["split"] == split]


def _find(observation: Observation, *, text: str | None = None,
          placeholder: str | None = None, tag: str | None = None):
    return next(item for item in observation.elements if
                (text is None or item.text == text) and
                (placeholder is None or item.placeholder == placeholder) and
                (tag is None or item.tag == tag))


def _execute(controller: BrowserController, observation: Observation, name: str,
             element, **arguments: Any) -> Observation:
    result = controller.execute(ToolCall(name=name, arguments={
        "snapshot_id": observation.snapshot_id,
        "element_id": element.element_id,
        **arguments,
    }))
    if not result.ok or result.observation is None:
        raise RuntimeError(result.error_message or f"{name} failed")
    return result.observation


def run_scripted_task(controller: BrowserController, task: dict[str, Any], base_url: str) -> dict[str, Any]:
    started = time.perf_counter()
    observation = controller.navigate(base_url).observation
    steps = 0
    script = task["script"]
    if task["kind"] == "course_lookup":
        field = _find(observation, placeholder="输入课程关键词")
        observation = _execute(controller, observation, "fill", field, text=script["query"])
        button = _find(observation, text="搜索课程")
        observation = _execute(controller, observation, "click", button)
        expected = task["expected"]
        detail = _find(observation, text=f"查看 {expected['name']}详情")
        observation = _execute(controller, observation, "click", detail)
        steps = 3
        reported = f"找到 {expected['name']}，时长 {expected['hours']} 小时，链接 {expected['url']}"
    else:
        for placeholder, value in (("报名人姓名", script["name"]), ("联系邮箱", script["email"])):
            field = _find(observation, placeholder=placeholder)
            observation = _execute(controller, observation, "fill", field, text=value)
        select = _find(observation, tag="select")
        observation = _execute(controller, observation, "select_option", select, value=script["course"])
        submit = _find(observation, text="提交报名")
        observation = _execute(controller, observation, "click", submit)
        steps = 4
        reported = f"提交成功：{script['name']} 已报名 {script['course']}"
    verification = verify_task(task, observation, reported)
    return {
        "task_id": task["id"], "split": task["split"], "status": "completed",
        "verification_status": verification.status.value, "verification_reason": verification.reason,
        "steps": steps, "model_calls": 0,
        "duration_ms": int((time.perf_counter() - started) * 1000), "error_code": None,
    }


def run_qwen_task(task: dict[str, Any], base_url: str) -> dict[str, Any]:
    agent = BrowserAgent(headless=True)
    prompt = f"先打开 {base_url}，然后完成任务：{task['task']}"
    result = agent.run(prompt, verifier=lambda observation, reported: verify_task(task, observation, reported))
    return {"task_id": task["id"], "split": task["split"], **result}


def aggregate(results: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    durations = sorted(result["duration_ms"] for result in results)
    passed = sum(result["verification_status"] == "passed" for result in results)
    errors = Counter(result.get("error_code") or "none" for result in results)
    p95_index = max(0, math.ceil(len(durations) * .95) - 1)
    return {
        "mode": mode, "task_count": len(results), "passed": passed,
        "pass_rate": passed / len(results) if results else 0,
        "average_steps": sum(r["steps"] for r in results) / len(results) if results else 0,
        "average_duration_ms": sum(durations) / len(durations) if durations else 0,
        "p95_duration_ms": durations[p95_index] if durations else 0,
        "model_calls": sum(r.get("model_calls", 0) for r in results),
        "error_categories": dict(errors), "results": results,
    }


def run_evaluation(mode: str = "scripted", split: str = "all", base_url: str | None = None,
                   output_dir: str | Path | None = None) -> tuple[dict[str, Any], Path]:
    tasks = load_tasks(split)
    base_url = base_url or (ROOT / "demo_site" / "index.html").resolve().as_uri()
    if mode == "scripted":
        controller = BrowserController(headless=True, browser_type=Config.BROWSER_TYPE,
                                       screenshot_dir=str(Path(Config.ARTIFACT_DIR) / "eval-screenshots"))
        try:
            results = [run_scripted_task(controller, task, base_url) for task in tasks]
        finally:
            controller.close()
    else:
        results = [run_qwen_task(task, base_url) for task in tasks]
    report = aggregate(results, mode)
    destination = Path(output_dir or Config.ARTIFACT_DIR) / "evaluations" / f"{datetime.now():%Y%m%d-%H%M%S}"
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report, report_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("scripted", "qwen"), default="scripted")
    parser.add_argument("--split", choices=("all", "dev", "holdout"), default="all")
    parser.add_argument("--base-url")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    report, path = run_evaluation(args.mode, args.split, args.base_url, args.output_dir)
    print(json.dumps({**report, "report_path": str(path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
