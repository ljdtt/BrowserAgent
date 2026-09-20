from pathlib import Path
import asyncio
import sys

import pytest

from src.core.browser_controller import BrowserController
from src.core.schemas import ToolCall


@pytest.fixture
def demo_url():
    return Path(__file__).parent.joinpath("fixtures", "demo_page.html").resolve().as_uri()


@pytest.fixture
def controller(tmp_path):
    browser = BrowserController(browser_type="msedge", headless=True, screenshot_dir=str(tmp_path))
    browser.start()
    try:
        yield browser
    finally:
        browser.close()


def test_observation_includes_visible_body_text(controller, demo_url):
    result = controller.navigate(demo_url)

    assert result.ok is True
    assert "课程目录" in result.observation.text


def test_fill_uses_element_id_from_the_observation(controller, demo_url):
    observation = controller.navigate(demo_url).observation
    query = next(item for item in observation.elements if item.placeholder == "课程关键词")

    result = controller.execute(ToolCall(name="fill", arguments={
        "snapshot_id": observation.snapshot_id,
        "element_id": query.element_id,
        "text": "Python",
    }))

    assert result.ok is True
    assert controller.page.locator("#query").input_value() == "Python"


def test_mutating_action_invalidates_the_previous_snapshot(controller, demo_url):
    observation = controller.navigate(demo_url).observation
    query = next(item for item in observation.elements if item.placeholder == "课程关键词")
    submit = next(item for item in observation.elements if item.text == "搜索")

    controller.execute(ToolCall(name="fill", arguments={
        "snapshot_id": observation.snapshot_id,
        "element_id": query.element_id,
        "text": "Python",
    }))
    stale = controller.execute(ToolCall(name="click", arguments={
        "snapshot_id": observation.snapshot_id,
        "element_id": submit.element_id,
    }))

    assert stale.ok is False
    assert stale.error_code == "stale_element"


def test_click_and_select_option_operate_on_fresh_snapshots(controller, demo_url):
    observation = controller.navigate(demo_url).observation
    level = next(item for item in observation.elements if item.tag == "select")
    selected = controller.execute(ToolCall(name="select_option", arguments={
        "snapshot_id": observation.snapshot_id,
        "element_id": level.element_id,
        "value": "advanced",
    }))
    submit = next(item for item in selected.observation.elements if item.text == "搜索")

    clicked = controller.execute(ToolCall(name="click", arguments={
        "snapshot_id": selected.observation.snapshot_id,
        "element_id": submit.element_id,
    }))

    assert clicked.ok is True
    assert "难度：advanced" in clicked.observation.text


def test_observer_removes_ids_from_elements_that_become_hidden(controller, demo_url):
    controller.navigate(demo_url)
    controller.page.evaluate("""() => {
        const old = document.querySelector('button');
        old.style.display = 'none';
        const fresh = document.createElement('button');
        fresh.textContent = 'Fresh action';
        document.body.appendChild(fresh);
    }""")

    current = controller.observe().observation
    fresh = next(item for item in current.elements if item.text == "Fresh action")
    result = controller.execute(ToolCall(name="click", arguments={
        "snapshot_id": current.snapshot_id, "element_id": fresh.element_id,
    }))

    assert result.ok is True


@pytest.mark.skipif(sys.platform != "win32", reason="Windows event-loop compatibility")
def test_browser_starts_when_host_uses_selector_event_loop_policy(tmp_path):
    previous_policy = asyncio.get_event_loop_policy()
    browser = None
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        browser = BrowserController(browser_type="msedge", headless=True, screenshot_dir=str(tmp_path))
        browser.start()

        assert browser.observe().ok is True
        assert isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsSelectorEventLoopPolicy)
    finally:
        if browser is not None:
            browser.close()
        asyncio.set_event_loop_policy(previous_policy)
