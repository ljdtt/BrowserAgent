import pytest

from src.core.schemas import RunResult, RunStatus, VerificationStatus
from src.core.tools import ToolProtocolError, parse_tool_call


def test_parse_tool_call_rejects_unknown_tool():
    with pytest.raises(ToolProtocolError, match="unknown tool"):
        parse_tool_call({
            "function_call": {
                "name": "delete_everything",
                "arguments": "{}",
            }
        })


def test_parse_tool_call_validates_snapshot_bound_click():
    call = parse_tool_call({
        "function_call": {
            "name": "click",
            "arguments": '{"snapshot_id":"snap-1","element_id":3}',
        }
    })

    assert call.arguments == {"snapshot_id": "snap-1", "element_id": 3}


def test_parse_tool_call_rejects_invalid_arguments():
    with pytest.raises(ToolProtocolError, match="invalid arguments"):
        parse_tool_call({
            "function_call": {
                "name": "scroll",
                "arguments": '{"direction":"sideways"}',
            }
        })


def test_run_result_separates_completion_from_verification():
    result = RunResult(
        status="completed",
        verification_status="failed",
        reported_result="done",
    )

    assert result.status == RunStatus.COMPLETED
    assert result.verification_status == VerificationStatus.FAILED
