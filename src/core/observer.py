"""Convert a live Playwright page into a compact, actionable snapshot."""

from __future__ import annotations

from uuid import uuid4

from .schemas import Observation


OBSERVE_SCRIPT = r"""
() => {
  const selector = [
    'a', 'button', 'input', 'textarea', 'select',
    '[contenteditable="true"]', '[role="button"]', '[role="link"]',
    '[role="textbox"]', '[role="searchbox"]', '[role="combobox"]'
  ].join(',');
  const output = [];
  for (const element of document.querySelectorAll(selector)) {
    const rect = element.getBoundingClientRect();
    const style = window.getComputedStyle(element);
    if (rect.width <= 0 || rect.height <= 0 || style.display === 'none' || style.visibility === 'hidden') continue;
    const elementId = output.length;
    element.setAttribute('data-browser-agent-id', String(elementId));
    const tag = element.tagName.toLowerCase();
    const labels = element.labels ? Array.from(element.labels).map(label => label.innerText.trim()).filter(Boolean) : [];
    const ariaLabel = element.getAttribute('aria-label') || '';
    const placeholder = element.getAttribute('placeholder') || '';
    const ownText = (element.innerText || element.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 160);
    output.push({
      element_id: elementId,
      tag,
      role: element.getAttribute('role') || '',
      type: element.getAttribute('type') || '',
      text: ownText || labels.join(' ') || ariaLabel || placeholder,
      aria_label: ariaLabel,
      placeholder,
      href: element.href || '',
      disabled: Boolean(element.disabled) || element.getAttribute('aria-disabled') === 'true',
      editable: tag === 'input' || tag === 'textarea' || tag === 'select' || element.isContentEditable,
    });
  }
  return {
    title: document.title || '',
    url: window.location.href,
    text: (document.body?.innerText || '').trim().slice(0, 4000),
    elements: output,
  };
}
"""


class PageObserver:
    """Creates versioned page observations and DOM element references."""

    def observe(self, page) -> Observation:
        return Observation(snapshot_id=uuid4().hex, **page.evaluate(OBSERVE_SCRIPT))
