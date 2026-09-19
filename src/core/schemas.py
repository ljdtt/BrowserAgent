"""Typed messages shared by the model, browser, UI, and evaluator."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


ToolName = Literal[
    "navigate",
    "observe",
    "click",
    "fill",
    "press_key",
    "scroll",
    "select_option",
    "extract",
    "finish",
]


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    MAX_STEPS_EXCEEDED = "max_steps_exceeded"
    TIMED_OUT = "timed_out"


class VerificationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_CHECKED = "not_checked"


class ElementRef(BaseModel):
    element_id: int = Field(ge=0)
    tag: str
    role: str = ""
    type: str = ""
    text: str = ""
    aria_label: str = ""
    placeholder: str = ""
    href: str = ""
    disabled: bool = False
    editable: bool = False


class Observation(BaseModel):
    snapshot_id: str
    page_id: str = "page-1"
    title: str = ""
    url: str = ""
    text: str = ""
    elements: list[ElementRef] = Field(default_factory=list)
    captured_at: datetime = Field(default_factory=datetime.now)


class ToolCall(BaseModel):
    name: ToolName
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    ok: bool
    action: str
    observation: Observation | None = None
    error_code: str | None = None
    error_message: str | None = None
    duration_ms: int = Field(default=0, ge=0)
    screenshot_path: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class RunEvent(BaseModel):
    kind: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class VerificationResult(BaseModel):
    status: VerificationStatus
    reason: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)


class RunResult(BaseModel):
    status: RunStatus
    verification_status: VerificationStatus = VerificationStatus.NOT_CHECKED
    reported_result: str | None = None
    verification_reason: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    steps: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    model_calls: int = Field(default=0, ge=0)
    events: list[RunEvent] = Field(default_factory=list)
    screenshots: list[str] = Field(default_factory=list)
    run_id: str | None = None

