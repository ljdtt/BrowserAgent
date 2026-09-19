"""Deterministic success checks independent from the model's finish claim."""

from __future__ import annotations

from typing import Any

from src.core.schemas import Observation, VerificationResult


def verify_course_result(expected: dict[str, Any], actual: dict[str, Any]) -> VerificationResult:
    mismatches = [key for key in ("name", "hours", "url") if actual.get(key) != expected.get(key)]
    return VerificationResult(status="passed" if not mismatches else "failed",
                              reason="课程信息匹配" if not mismatches else f"课程字段不匹配：{', '.join(mismatches)}",
                              evidence={"expected": expected, "actual": actual})


def verify_submission(expected: dict[str, Any], actual: dict[str, Any]) -> VerificationResult:
    mismatches = [key for key in ("banner", "name", "course") if actual.get(key) != expected.get(key)]
    return VerificationResult(status="passed" if not mismatches else "failed",
                              reason="报名回执匹配" if not mismatches else f"回执字段不匹配：{', '.join(mismatches)}",
                              evidence={"expected": expected, "actual": actual})


def verify_task(task: dict[str, Any], observation: Observation | None,
                reported_result: str | None) -> VerificationResult:
    if observation is None:
        return VerificationResult(status="failed", reason="没有最终页面观察",
                                  evidence={"task_id": task["id"]})
    expected = task["expected"]
    page_text = observation.text
    report_text = reported_result or ""
    missing_page = []
    missing_report = []
    report_keys = {"name", "hours"} if task["kind"] == "course_lookup" else {"banner", "name", "course"}
    for key, value in expected.items():
        rendered = f"{value} 小时" if key == "hours" else str(value)
        if rendered not in page_text:
            missing_page.append(key)
        if key in report_keys and rendered not in report_text:
            missing_report.append(key)
    passed = not missing_page and not missing_report
    reason = "页面证据与报告分别匹配" if passed else (
        f"页面缺少：{', '.join(missing_page) or '无'}；报告缺少：{', '.join(missing_report) or '无'}"
    )
    return VerificationResult(status="passed" if passed else "failed", reason=reason,
                              evidence={"task_id": task["id"], "expected": expected,
                                        "missing_page_evidence": missing_page,
                                        "missing_report_evidence": missing_report})
