# -*- coding: utf-8 -*-
# BrowserAgent browser controller using Playwright

import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright


class BrowserController:
    # Browser controller using Playwright

    def __init__(self, browser_type="msedge", headless=False, screenshot_dir="screenshots"):
        self.browser_type = browser_type
        self.headless = headless
        self.screenshot_dir = screenshot_dir
        self._loop = None
        self._pw = None
        self._browser = None
        self._page = None
        self.action_log = []
        os.makedirs(screenshot_dir, exist_ok=True)

    def _exec(self, coro_func, timeout=120):
        # Run an async function on a dedicated event loop
        coro = coro_func()
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        try:
            old = asyncio.get_event_loop()
        except RuntimeError:
            old = None
        try:
            asyncio.set_event_loop(self._loop)
            return self._loop.run_until_complete(coro)
        finally:
            if old is not None:
                asyncio.set_event_loop(old)

    def start(self):
        if self._browser:
            return
        self._exec(self._async_start)
        self._log("browser started")

    async def _async_start(self):
        pw = await async_playwright().start()
        kw = {"headless": self.headless, "args": ["--no-sandbox", "--disable-gpu"]}
        if self.browser_type:
            kw["channel"] = self.browser_type
        b = await pw.chromium.launch(**kw)
        p = await b.new_page()
        await p.set_viewport_size({"width": 1280, "height": 800})
        self._pw, self._browser, self._page = pw, b, p

    def close(self):
        if self._browser:
            self._exec(self._async_close, timeout=10)
        if self._loop:
            self._loop.close()
        self._loop = None
        self._page = self._browser = self._pw = None

    async def _async_close(self):
        try:
            if self._page: await self._page.close()
            if self._browser: await self._browser.close()
            if self._pw: await self._pw.stop()
        except Exception:
            pass

    def navigate(self, url):
        return self._exec(lambda: self._async_navigate(url))

    async def _async_navigate(self, url):
        try:
            await self._page.goto(url, wait_until="load", timeout=30000)
            self._log("navigate", {"url": url})
            return await self._async_page_state()
        except Exception as e:
            return {"error": f"navigate failed: {str(e)}"}

    def get_page_state(self):
        return self._exec(self._async_page_state)

    async def _async_page_state(self):
        if not self._page:
            return {"error": "browser not started"}
        try:
            result = await self._page.evaluate("() => {"
                "const sel = \"a,button,input,textarea,select,[role=button],[role=link],[role=textbox],[role=search]\";"
                "const items = document.querySelectorAll(sel);"
                "const out = []; let idx = 0;"
                "for (const el of items) {"
                "    const r = el.getBoundingClientRect();"
                "    if (r.width === 0 || r.height === 0) continue;"
                "    const s = window.getComputedStyle(el);"
                "    if (s.display === 'none' || s.visibility === 'hidden') continue;"
                "    const t = (el.textContent || \"\").trim().slice(0, 80);"
                "    const a = el.getAttribute('aria-label') || \"\";"
                "    if (el.tagName.toLowerCase() === 'a' && !t && !a) continue;"
                "    const label = t || a || el.getAttribute('placeholder') || '<' + el.tagName.toLowerCase() + '>';"
                "    out.push({index: idx++, tag: el.tagName.toLowerCase(), text: label, href: el.getAttribute('href') || \"\"});"
                "}"
                "return {title: document.title, url: window.location.href, elements: out, preview: document.body.innerText.slice(0, 2000)};"
                "}")
            return result
        except Exception as e:
            return {"error": str(e)}



    def type_text(self, index, text):
        return self._exec(lambda: self._async_type_text(index, text))

    async def _async_type_text(self, index, text):
        if not self._page: return {"error": "no browser"}
        try:
            safe = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
            idx_str = str(index)
            js = "() => { const items = document.querySelectorAll('input,textarea,[contenteditable=true],[role=textbox]'); let idx = 0; for (const el of items) { const r = el.getBoundingClientRect(); if (r.width > 0 && r.height > 0) { if (idx++ === " + idx_str + ") { el.scrollIntoView({behavior: 'instant', block: 'center'}); el.focus(); el.value = ''; el.value = '" + safe + "'; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); return 'ok'; } } } return 'nf'; }"
            result = await self._page.evaluate(js)
            await asyncio.sleep(0.5)
            self._log("type", {"index": index, "result": result})
            return {"action": "type", "index": index, "result": result, "page": await self._async_page_state()}
        except Exception as e:
            return {"error": str(e)}

    def press_enter(self):
        return self._exec(self._async_press_enter)

    async def _async_press_enter(self):
        if not self._page: return {"error": "no browser"}
        try:
            await self._page.keyboard.press("Enter")
            await asyncio.sleep(1)
            self._log("enter")
            return {"action": "enter", "page": await self._async_page_state()}
        except Exception as e:
            return {"error": str(e)}

    def scroll(self, direction="down"):
        return self._exec(lambda: self._async_scroll(direction))

    async def _async_scroll(self, direction):
        if not self._page: return {"error": "no browser"}
        try:
            amount = 600 if direction == "down" else -600
            await self._page.evaluate("window.scrollBy({top: " + str(amount) + ", behavior: 'smooth'})")
            self._log("scroll", {"direction": direction})
            return {"action": "scroll", "direction": direction, "page": await self._async_page_state()}
        except Exception as e:
            return {"error": str(e)}

    def screenshot(self, name=None):
        return self._exec(lambda: self._async_screenshot(name))

    async def _async_screenshot(self, name):
        if not self._page: return ""
        if not name: name = datetime.now().strftime("step_%H%M%S")
        path = os.path.join(self.screenshot_dir, f"{name}.png")
        await self._page.screenshot(path=path, full_page=False)
        self._log("screenshot", {"path": path})
        return path

    def _log(self, action, detail=None):
        self.action_log.append({"time": datetime.now().strftime("%H:%M:%S"), "action": action, "detail": detail or {}})

    def get_action_log(self):
        return self.action_log

    @property
    def current_url(self):
        if self._page:
            try:
                return self._exec(self._page.evaluate("window.location.href"))
            except Exception:
                pass
        return ""

    @property
    def current_title(self):
        if self._page:
            try:
                return self._exec(self._page.title())
            except Exception:
                pass
        return ""
