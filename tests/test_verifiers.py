from src.core.schemas import Observation
from evals.verifiers import verify_course_result, verify_submission, verify_task


def test_course_result_requires_matching_name_hours_and_link():
    passed = verify_course_result(
        {"name": "Python 入门", "hours": 18, "url": "/courses/python-intro"},
        {"name": "Python 入门", "hours": 18, "url": "/courses/python-intro"},
    )
    failed = verify_course_result(
        {"name": "Python 入门", "hours": 18, "url": "/courses/python-intro"},
        {"name": "Python 入门", "hours": 12, "url": "/courses/python-intro"},
    )

    assert passed.status.value == "passed"
    assert failed.status.value == "failed"


def test_form_task_rejects_success_banner_with_wrong_payload():
    result = verify_submission(
        {"banner": "提交成功", "name": "李雷", "course": "Python 入门"},
        {"banner": "提交成功", "name": "李雷", "course": "错误课程"},
    )

    assert result.status.value == "failed"


def test_task_verifier_checks_observed_evidence_and_reported_result():
    task = {
        "id": "lookup-python",
        "kind": "course_lookup",
        "expected": {"name": "Python 入门", "hours": 18, "url": "/courses/python-intro"},
    }
    observation = Observation(
        snapshot_id="s1",
        url="http://demo.test/",
        text="Python 入门 18 小时 /courses/python-intro",
    )

    result = verify_task(task, observation, "找到 Python 入门，时长 18 小时")

    assert result.status.value == "passed"
    assert result.evidence["task_id"] == "lookup-python"
