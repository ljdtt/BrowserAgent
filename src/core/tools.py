"""Browser tool schemas and validation for Qwen function calls."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from .schemas import ToolCall


class ToolProtocolError(ValueError):
    """Raised when a model response cannot be executed safely."""


class NavigateArguments(BaseModel):
    url: str = Field(min_length=1)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://", "file://", "data:")):
            raise ValueError("url must use http, https, file, or data")
        return value


class ObserveArguments(BaseModel):
    query: str | None = None


class ElementArguments(BaseModel):
    snapshot_id: str = Field(min_length=1)
    element_id: int = Field(ge=0)


class ClickArguments(ElementArguments):
    pass


class FillArguments(ElementArguments):
    text: str
    sensitive: bool = False


class PressKeyArguments(BaseModel):
    key: Literal["Enter"] = "Enter"


class ScrollArguments(BaseModel):
    direction: Literal["up", "down"] = "down"


class SelectOptionArguments(ElementArguments):
    value: str


class ExtractArguments(BaseModel):
    fields: list[str] = Field(min_length=1)


class FinishArguments(BaseModel):
    success: bool
    result: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)


TOOL_ARGUMENT_MODELS: dict[str, type[BaseModel]] = {
    "navigate": NavigateArguments,
    "observe": ObserveArguments,
    "click": ClickArguments,
    "fill": FillArguments,
    "press_key": PressKeyArguments,
    "scroll": ScrollArguments,
    "select_option": SelectOptionArguments,
    "extract": ExtractArguments,
    "finish": FinishArguments,
}


TOOL_DESCRIPTIONS = {
    "navigate": "打开指定网页。",
    "observe": "重新读取当前页面，可用 query 提示关注的内容。",
    "click": "点击当前页面快照中的元素。",
    "fill": "填写当前页面快照中的输入元素。敏感值需设置 sensitive=true。",
    "press_key": "按下键盘按键，当前只支持 Enter。",
    "scroll": "向上或向下滚动页面。",
    "select_option": "选择下拉框选项。",
    "extract": "从当前页面提取指定字段。",
    "finish": "结束任务。任务确实完成时 success=true；因页面不可用或其他阻碍无法完成时 success=false，并说明原因。",
}


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": name,
        "description": TOOL_DESCRIPTIONS[name],
        "parameters": argument_model.model_json_schema(),
    }
    for name, argument_model in TOOL_ARGUMENT_MODELS.items()
]


def parse_tool_call(message: dict[str, Any]) -> ToolCall:
    raw_call = message.get("function_call")
    if not raw_call:
        raise ToolProtocolError("missing function_call")

    name = raw_call.get("name")
    argument_model = TOOL_ARGUMENT_MODELS.get(name)
    if argument_model is None:
        raise ToolProtocolError(f"unknown tool: {name}")

    raw_arguments = raw_call.get("arguments") or "{}"
    try:
        arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
        validated = argument_model.model_validate(arguments)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise ToolProtocolError(f"invalid arguments for {name}: {exc}") from exc

    return ToolCall(name=name, arguments=validated.model_dump(mode="json"))
