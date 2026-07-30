# -*- coding: utf-8 -*-
"""BrowserAgent 浏览器自动化智能体 - Streamlit 面板"""

import os as _os, sys as _sys, time as _time
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import streamlit as st
from core.agent import BrowserAgent
from core.config import Config

# 页面配置
st.set_page_config(page_title="BrowserAgent", page_icon="🌐", layout="wide")

# 会话状态初始化
if "running" not in st.session_state:
    st.session_state.running = False
if "result" not in st.session_state:
    st.session_state.result = None
if "logs" not in st.session_state:
    st.session_state.logs = []
if "error" not in st.session_state:
    st.session_state.error = None

# 侧边栏
with st.sidebar:
    st.markdown("## 配置")
    api_key = st.text_input(
        "API 密钥",
        type="password",
        value=Config.DASHSCOPE_API_KEY or "",
        placeholder="sk-ws-xxx...",
        help="阿里云百炼 API 密钥（sk-ws- 格式）",
    )
    col1, col2 = st.columns(2)
    with col1:
        model = st.selectbox("模型", ["qwen-plus", "qwen-max", "qwen-turbo"], index=0)
    with col2:
        max_steps = st.number_input("最大步数", min_value=3, max_value=50, value=15)
    headless = st.checkbox("无头模式", value=False)
    model_server = st.text_input(
        "API 地址",
        value=Config.MODEL_SERVER,
        placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1",
        help="阿里云百炼 API 服务器地址",
    )
    st.divider()
    st.caption("技术栈：Qwen-Agent · Playwright · Streamlit")

# 主区域
st.title(":globe_with_meridians: BrowserAgent")
st.markdown("在下方输入任务，代理将自动打开浏览器、导航页面并执行操作。")

# 任务输入框
task = st.chat_input("描述你想要浏览器执行的任务...", disabled=st.session_state.running)

if task and not st.session_state.running:
    effective_key = api_key.strip() or Config.DASHSCOPE_API_KEY
    if not effective_key:
        st.error("请先在侧边栏输入 API 密钥")
        st.stop()

    st.session_state.running = True
    st.session_state.result = None
    st.session_state.error = None
    st.session_state.logs = []

    agent = BrowserAgent(
        api_key=effective_key, model=model, model_server=model_server,
        headless=headless, max_steps=int(max_steps),
    )

    with st.empty():
        st.markdown("### 执行中...")
        st.progress(0, text="初始化中...")
        try:
            result = agent.run(task)
            st.session_state.result = result
            st.session_state.logs = agent.get_logs()
        except Exception as e:
            st.session_state.error = str(e)
            st.session_state.logs = agent.get_logs() if hasattr(agent, "get_logs") else []
        finally:
            st.session_state.running = False
    st.rerun()

# 结果显示
if st.session_state.result is not None:
    r = st.session_state.result
    if r.get("success"):
        st.success("任务完成！")
        if r.get("result"):
            with st.expander("结果", expanded=True):
                st.markdown(r["result"])
    else:
        st.error("失败：" + str(r.get("error", "未知错误")))

elif st.session_state.error is not None:
    st.error("错误：" + str(st.session_state.error))

elif not st.session_state.running:
    st.divider()
    st.markdown("### 快速上手")
    for line in [
        "1. 在侧边栏输入你的 API 密钥（阿里云百炼）",
        "2. 在下方输入框输入任务描述",
        "3. 观看代理自动浏览、点击和输入",
        "",
        "示例任务：",
        "- 在 Google 上搜索 Python 教程",
        "- 打开维基百科，查找人工智能相关文章",
        "- 去 GitHub 搜索 streamlit 仓库",
    ]:
        st.markdown(line)

st.divider()
st.caption("BrowserAgent - 基于 Qwen-Agent + Streamlit + Playwright 构建")