from pathlib import Path

import pytest

from src.core.browser_controller import BrowserController
from src.core.schemas import ToolCall


@pytest.fixture
def demo_controller(tmp_path):
    controller = BrowserController(headless=True, screenshot_dir=str(tmp_path), browser_type="msedge")
    controller.start()
    yield controller
    controller.close()


def demo_url():
    return (Path(__file__).parents[1] / "demo_site" / "index.html").resolve().as_uri()


def element(observation, *, text=None, placeholder=None):
    return next(item for item in observation.elements if (
        (text is None or item.text == text) and
        (placeholder is None or item.placeholder == placeholder)
    ))


def test_local_demo_filters_course_catalog(demo_controller):
    observation = demo_controller.navigate(demo_url()).observation
    search = element(observation, placeholder="输入课程关键词")
    result = demo_controller.execute(ToolCall(name="fill", arguments={
        "snapshot_id": observation.snapshot_id,
        "element_id": search.element_id,
        "text": "Python 入门",
    }))
    button = element(result.observation, text="搜索课程")
    result = demo_controller.execute(ToolCall(name="click", arguments={
        "snapshot_id": result.observation.snapshot_id,
        "element_id": button.element_id,
    }))

    assert "Python 入门" in result.observation.text
    assert "18 小时" in result.observation.text
    assert "1 门课程" in result.observation.text


def test_local_demo_creates_submission_receipt(demo_controller):
    observation = demo_controller.navigate(demo_url()).observation
    for placeholder, value in [("报名人姓名", "李雷"), ("联系邮箱", "lilei@example.com")]:
        field = element(observation, placeholder=placeholder)
        result = demo_controller.execute(ToolCall(name="fill", arguments={
            "snapshot_id": observation.snapshot_id,
            "element_id": field.element_id,
            "text": value,
        }))
        observation = result.observation
    course = next(item for item in observation.elements if item.tag == "select")
    result = demo_controller.execute(ToolCall(name="select_option", arguments={
        "snapshot_id": observation.snapshot_id,
        "element_id": course.element_id,
        "value": "Python 入门",
    }))
    submit = element(result.observation, text="提交报名")
    result = demo_controller.execute(ToolCall(name="click", arguments={
        "snapshot_id": result.observation.snapshot_id,
        "element_id": submit.element_id,
    }))

    assert "提交成功" in result.observation.text
    assert "李雷" in result.observation.text
    assert "Python 入门" in result.observation.text
