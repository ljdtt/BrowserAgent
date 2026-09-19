"""Streamlit presentation layer for BrowserAgent workers and trace artifacts."""

from __future__ import annotations

import io
import json
import time
import zipfile

import streamlit as st

from core.config import Config
from core.worker import AgentWorker


def _trace_zip(worker: AgentWorker) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in worker.trace_writer.run_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(worker.trace_writer.run_dir))
    return buffer.getvalue()


def render() -> None:
    st.set_page_config(page_title="BrowserAgent", page_icon="🌐", layout="wide")
    defaults = {"worker": None, "events": [], "result": None, "task": ""}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    with st.sidebar:
        st.header("运行配置")
        api_key = st.text_input("DashScope API Key", type="password", value=Config.DASHSCOPE_API_KEY)
        model = st.selectbox("模型", ["qwen-plus", "qwen-max", "qwen-turbo"])
        max_steps = st.number_input("最大浏览器动作", 1, 50, Config.MAX_STEPS)
        headless = st.checkbox("无头模式", value=True,
                               help="默认启用，更适合 Streamlit 后台 Worker；取消勾选会显示浏览器窗口。")
        st.caption("API Key 只传给模型客户端，不写入运行轨迹。")

    st.title("BrowserAgent")
    st.caption("Qwen function calling · snapshot-bound Playwright tools · deterministic verification")
    worker: AgentWorker | None = st.session_state.worker
    running = worker is not None and worker.is_alive
    task = st.chat_input("描述浏览器任务", disabled=running)
    if task:
        if not api_key.strip():
            st.error("请先配置 DashScope API Key")
        else:
            worker = AgentWorker()
            worker.start(task, api_key=api_key.strip(), model=model,
                         max_steps=int(max_steps), headless=headless)
            st.session_state.worker = worker
            st.session_state.events = []
            st.session_state.result = None
            st.session_state.task = task
            st.rerun()

    if worker is not None:
        st.session_state.events.extend(worker.poll())
        top_left, top_right = st.columns([4, 1])
        top_left.markdown(f"**任务：** {st.session_state.task}")
        if worker.is_alive and top_right.button("取消任务", type="secondary"):
            worker.cancel()

        st.subheader("执行时间线")
        for index, event in enumerate(st.session_state.events, 1):
            with st.expander(f"{index:02d} · {event['kind']}", expanded=index == len(st.session_state.events)):
                st.json(event.get("data", {}))

        if worker.is_alive:
            st.info("Agent 正在执行，页面会自动刷新。")
            time.sleep(.35)
            st.rerun()
        elif st.session_state.result is None:
            st.session_state.result = worker.join(timeout=0)

        result = st.session_state.result
        if result:
            st.subheader("运行结果")
            status_col, verify_col, steps_col = st.columns(3)
            status_col.metric("执行状态", result["status"])
            verify_col.metric("验证状态", result["verification_status"])
            steps_col.metric("浏览器动作", result["steps"])
            if result.get("reported_result"):
                st.markdown(result["reported_result"])
            if result.get("verification_reason"):
                st.caption(result["verification_reason"])
            st.download_button("下载运行轨迹", _trace_zip(worker),
                               file_name=f"{worker.trace_writer.run_dir.name}.zip",
                               mime="application/zip")
            with st.expander("完整结果 JSON"):
                st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")
