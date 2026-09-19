"""Run-scoped JSON artifacts with conservative secret redaction."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .schemas import RunEvent, RunResult


REDACTED = "[REDACTED]"
SECRET_KEYS = {"api_key", "authorization", "cookie", "password", "secret", "token"}


def redact_event(event: RunEvent | dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe event copy with known secret-bearing values removed."""
    raw = event.model_dump(mode="json") if isinstance(event, RunEvent) else copy.deepcopy(event)

    def scrub(value: Any) -> Any:
        if isinstance(value, list):
            return [scrub(item) for item in value]
        if not isinstance(value, dict):
            return value
        result: dict[str, Any] = {}
        sensitive = value.get("sensitive") is True
        for key, item in value.items():
            lowered = key.lower()
            if lowered in SECRET_KEYS or (sensitive and lowered in {"text", "value"}):
                result[key] = REDACTED
            else:
                result[key] = scrub(item)
        return result

    return scrub(raw)


@dataclass(frozen=True)
class TraceWriter:
    run_dir: Path
    events_path: Path
    result_path: Path
    screenshots_dir: Path

    @classmethod
    def create(cls, base_dir: str | Path) -> "TraceWriter":
        base = Path(base_dir)
        run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
        run_dir = base / run_id
        screenshots_dir = run_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=False)
        return cls(
            run_dir=run_dir,
            events_path=run_dir / "events.jsonl",
            result_path=run_dir / "result.json",
            screenshots_dir=screenshots_dir,
        )

    def write_event(self, event: RunEvent | dict[str, Any]) -> None:
        payload = redact_event(event)
        with self.events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def write_result(self, result: RunResult | dict[str, Any]) -> None:
        payload = result.model_dump(mode="json") if isinstance(result, RunResult) else result
        safe_payload = redact_event({"kind": "result", "data": payload})["data"]
        self.result_path.write_text(
            json.dumps(safe_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
