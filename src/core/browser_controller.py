"""Playwright browser lifecycle and deterministic browser tools."""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Callable

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .observer import PageObserver
from .schemas import Observation, ToolCall, ToolResult


class BrowserController:
    """Own one Playwright browser and execute validated tool calls on it."""

    def __init__(
        self,
        browser_type: str = "msedge",
        headless: bool = False,
        screenshot_dir: str = "screenshots",
        navigation_timeout_ms: int = 30_000,
        action_timeout_ms: int = 10_000,
    ):
        self.browser_type = browser_type
        self.headless = headless
        self.screenshot_dir = screenshot_dir
        self.navigation_timeout_ms = navigation_timeout_ms
        self.action_timeout_ms = action_timeout_ms
        self._pw = None
        self._browser = None
        self._page = None
        self._observer = PageObserver()
        self._observation: Observation | None = None
        self.action_log: list[dict] = []
        os.makedirs(screenshot_dir, exist_ok=True)

    @property
    def page(self):
        if self._page is None:
            raise RuntimeError("browser not started")
        return self._page

    def start(self) -> None:
        if self._browser is not None:
            return
        self._pw = sync_playwright().start()
        launch_options = {"headless": self.headless, "args": ["--no-sandbox", "--disable-gpu"]}
        if self.browser_type:
            launch_options["channel"] = self.browser_type
        self._browser = self._pw.chromium.launch(**launch_options)
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 800})
        self._page.set_default_timeout(self.action_timeout_ms)
        self._page.set_default_navigation_timeout(self.navigation_timeout_ms)
        self._log("browser_started")

    def close(self) -> None:
        try:
            if self._page is not None:
                self._page.close()
            if self._browser is not None:
                self._browser.close()
        finally:
            if self._pw is not None:
                self._pw.stop()
            self._page = self._browser = self._pw = None
            self._observation = None

    def navigate(self, url: str) -> ToolResult:
        self.start()
        return self._timed("navigate", lambda: self._navigate(url))

    def _navigate(self, url: str) -> Observation:
        self.page.goto(url, wait_until="load", timeout=self.navigation_timeout_ms)
        return self._refresh_observation()

    def observe(self) -> ToolResult:
        self.start()
        return self._timed("observe", self._refresh_observation)

    def execute(self, call: ToolCall) -> ToolResult:
        self.start()
        handlers: dict[str, Callable] = {
            "navigate": lambda: self._navigate(call.arguments["url"]),
            "observe": self._refresh_observation,
            "click": lambda: self._element_action(call, lambda locator: locator.click()),
            "fill": lambda: self._element_action(call, lambda locator: locator.fill(call.arguments["text"])),
            "press_key": lambda: self._page_action(lambda: self.page.keyboard.press(call.arguments["key"])),
            "scroll": lambda: self._page_action(lambda: self.page.mouse.wheel(
                0, 600 if call.arguments["direction"] == "down" else -600
            )),
            "select_option": lambda: self._element_action(
                call, lambda locator: locator.select_option(call.arguments["value"])
            ),
            "extract": lambda: self._extract(call.arguments["fields"]),
        }
        handler = handlers.get(call.name)
        if handler is None:
            return ToolResult(ok=False, action=call.name, error_code="unsupported_tool",
                              error_message=f"BrowserController cannot execute {call.name}")
        return self._timed(call.name, handler)

    def _element_action(self, call: ToolCall, operation: Callable) -> Observation:
        if self._observation is None or call.arguments["snapshot_id"] != self._observation.snapshot_id:
            raise StaleElementError("element belongs to an expired page snapshot")
        element_id = call.arguments["element_id"]
        locator = self.page.locator(f'[data-browser-agent-id="{element_id}"]')
        if locator.count() != 1:
            raise ElementNotFoundError(f"element {element_id} is no longer available")
        operation(locator)
        self.page.wait_for_timeout(100)
        return self._refresh_observation()

    def _page_action(self, operation: Callable[[], None]) -> Observation:
        operation()
        self.page.wait_for_timeout(100)
        return self._refresh_observation()

    def _extract(self, fields: list[str]) -> tuple[Observation, dict]:
        observation = self._refresh_observation()
        return observation, {"requested_fields": fields, "page_text": observation.text}

    def _refresh_observation(self) -> Observation:
        self._observation = self._observer.observe(self.page)
        return self._observation

    def _timed(self, action: str, operation: Callable) -> ToolResult:
        started = time.perf_counter()
        try:
            outcome = operation()
            observation, data = outcome if isinstance(outcome, tuple) else (outcome, {})
            result = ToolResult(ok=True, action=action, observation=observation, data=data,
                                duration_ms=int((time.perf_counter() - started) * 1000))
        except StaleElementError as exc:
            result = self._failure(action, "stale_element", str(exc), started)
        except ElementNotFoundError as exc:
            result = self._failure(action, "element_not_found", str(exc), started)
        except PlaywrightTimeoutError as exc:
            code = "navigation_timeout" if action == "navigate" else "action_timeout"
            result = self._failure(action, code, str(exc), started)
        except Exception as exc:
            result = self._failure(action, "browser_error", str(exc), started)
        self._log(action, result.model_dump(mode="json", exclude={"observation"}))
        return result

    def _failure(self, action: str, code: str, message: str, started: float) -> ToolResult:
        return ToolResult(ok=False, action=action, observation=self._observation, error_code=code,
                          error_message=message, duration_ms=int((time.perf_counter() - started) * 1000))

    def get_page_state(self) -> dict:
        result = self.observe()
        return result.observation.model_dump(mode="json") if result.ok else {"error": result.error_message}

    def click(self, index: int, snapshot_id: str | None = None) -> ToolResult:
        return self.execute(ToolCall(name="click", arguments={
            "snapshot_id": snapshot_id or self._current_snapshot_id(), "element_id": index
        }))

    def type_text(self, index: int, text: str, snapshot_id: str | None = None) -> ToolResult:
        return self.execute(ToolCall(name="fill", arguments={
            "snapshot_id": snapshot_id or self._current_snapshot_id(), "element_id": index, "text": text
        }))

    def press_enter(self) -> ToolResult:
        return self.execute(ToolCall(name="press_key", arguments={"key": "Enter"}))

    def scroll(self, direction: str = "down") -> ToolResult:
        return self.execute(ToolCall(name="scroll", arguments={"direction": direction}))

    def select_option(self, index: int, value: str, snapshot_id: str | None = None) -> ToolResult:
        return self.execute(ToolCall(name="select_option", arguments={
            "snapshot_id": snapshot_id or self._current_snapshot_id(), "element_id": index, "value": value
        }))

    def _current_snapshot_id(self) -> str:
        if self._observation is None:
            raise RuntimeError("page has not been observed")
        return self._observation.snapshot_id

    def screenshot(self, name: str | None = None) -> str:
        self.start()
        name = name or datetime.now().strftime("step_%H%M%S_%f")
        path = os.path.abspath(os.path.join(self.screenshot_dir, f"{name}.png"))
        self.page.screenshot(path=path, full_page=False)
        self._log("screenshot", {"path": path})
        return path

    def _log(self, action: str, detail: dict | None = None) -> None:
        self.action_log.append({"time": datetime.now().strftime("%H:%M:%S"),
                                "action": action, "detail": detail or {}})

    def get_action_log(self) -> list[dict]:
        return self.action_log

    @property
    def current_url(self) -> str:
        return self._page.url if self._page is not None else ""

    @property
    def current_title(self) -> str:
        return self._page.title() if self._page is not None else ""


class StaleElementError(RuntimeError):
    pass


class ElementNotFoundError(RuntimeError):
    pass
