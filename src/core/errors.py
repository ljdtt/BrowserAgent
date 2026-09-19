"""Consistent, non-empty exception descriptions for user-visible run results."""

from __future__ import annotations


def describe_exception(exc: BaseException) -> str:
    message = str(exc).strip()
    return message or f"{type(exc).__name__} (no message)"


def exception_event(exc: BaseException) -> dict[str, str]:
    return {
        "error": describe_exception(exc),
        "exception_type": type(exc).__name__,
    }
