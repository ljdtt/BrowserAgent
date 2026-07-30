# -*- coding: utf-8 -*-
"""
BrowserAgent - 浏览器自动化智能体

基于 Qwen-Agent 的 LLM 能力驱动浏览器操作。
核心流程：
1. 接收自然语言任务
2. LLM 分析当前页面状态，决定下一步操作
3. 通过 BrowserController 执行操作（导航/点击/输入等）
4. 将操作结果反馈给 LLM，继续推理
5. 直到任务完成
"""

import json
import os
import re
import time
from datetime import datetime
from typing import Optional

from qwen_agent.llm import get_chat_model
from qwen_agent.llm.schema import Message

from .browser_controller import BrowserController
from .config import Config


# ── 系统提示词 ──────────────────────────────────────────────

SYSTEM_PROMPT = """你是一个浏览器自动化智能体（BrowserAgent）。你的任务是根据用户的需求，通过操作浏览器来完成实际任务。

## 可执行的操作

每次回复时，你必须用以下格式之一告诉系统要做什么：

1. **导航到网页**
   ```
   ACTION: navigate
   URL: https://www.example.com
   ```

2. **点击页面元素**（通过元素列表中的 index 编号）
   ```
   ACTION: click
   INDEX: 5
   ```

3. **在输入框中输入文字**（通过 index 编号）
   ```
   ACTION: type
   INDEX: 3
   TEXT: 搜索关键词
   ```

4. **按回车键**（常用于提交搜索/表单）
   ```
   ACTION: enter
   ```

5. **滚动页面**
   ```
   ACTION: scroll
   DIRECTION: down
   ```
   DIRECTION 可以是 down 或 up

6. **完成任务并输出结果**
   ```
   ACTION: done
   RESULT: 任务完成！最终结果是...
   ```

## 语言规则

全程使用中文回答。你的所有思考、分析和操作说明均需要用中文输出。

## 重要规则

1. 系统每次操作后会告诉你当前页面状态，包括：
   - 页面标题和 URL
   - 所有可见的可交互元素及其 index 编号
   - 页面正文预览

2. 你必须根据页面状态中的元素列表来引用元素，不要猜测 index。

3. 每次只执行一个操作，等待结果后再决定下一步。

4. 如果执行搜索，通常流程是：
   a. 导航到搜索引擎
   b. 找到搜索输入框（通常是 tag=input 的元素），输入关键词
   c. 找到搜索按钮点击，或按回车
   d. 查看搜索结果页面

5. 如果操作失败，尝试备选方案。

6. 完成用户的任务后，用 ACTION: done 输出最终结果。
"""


# ── 操作解析 ──────────────────────────────────────────────

def parse_action(text: str) -> dict:
    """从 LLM 回复中解析出要执行的操作

    支持的格式:
    - ACTION: navigate / URL: ...
    - ACTION: click / INDEX: ...
    - ACTION: type / INDEX: ... / TEXT: ...
    - ACTION: enter
    - ACTION: scroll / DIRECTION: ...
    - ACTION: done / RESULT: ...
    """
    if not text:
        return {'action': 'none'}

    action_match = re.search(r'ACTION:\s*(\w+)', text, re.IGNORECASE)
    if not action_match:
        return {'action': 'none'}

    action = action_match.group(1).lower()
    result = {'action': action}

    if action == 'navigate':
        url_match = re.search(r'URL:\s*(https?://[^\s]+)', text, re.IGNORECASE)
        if url_match:
            result['url'] = url_match.group(1)

    elif action == 'click':
        idx_match = re.search(r'INDEX:\s*(\d+)', text, re.IGNORECASE)
        if idx_match:
            result['index'] = int(idx_match.group(1))

    elif action == 'type':
        idx_match = re.search(r'INDEX:\s*(\d+)', text, re.IGNORECASE)
        txt_match = re.search(r'TEXT:\s*(.+)', text, re.IGNORECASE)
        if idx_match:
            result['index'] = int(idx_match.group(1))
        if txt_match:
            result['text'] = txt_match.group(1).strip()

    elif action == 'scroll':
        dir_match = re.search(r'DIRECTION:\s*(\w+)', text, re.IGNORECASE)
        result['direction'] = dir_match.group(1).lower() if dir_match else 'down'

    elif action == 'done':
        res_match = re.search(r'RESULT:\s*(.+)', text, re.IGNORECASE)
        result['result'] = res_match.group(1).strip() if res_match else '任务完成'

    return result


def action_to_string(action: dict) -> str:
    """将操作字典转为描述文本"""
    if action['action'] == 'navigate':
        return f"导航到 {action.get('url', '')}"
    elif action['action'] == 'click':
        return f"点击元素 #{action.get('index', '?')}"
    elif action['action'] == 'type':
        return f"在元素 #{action.get('index', '?')} 输入 '{action.get('text', '')}'"
    elif action['action'] == 'enter':
        return "按下回车键"
    elif action['action'] == 'scroll':
        return f"向{action.get('direction', '下')}滚动"
    elif action['action'] == 'done':
        return "完成任务"
    return "未知操作"


# ── 页面状态格式化 ──────────────────────────────────────────

def format_page_state(state: dict) -> str:
    """将页面状态格式化为 LLM 易于理解的文本"""
    if not state:
        return "[当前页面状态获取失败]"

    if 'error' in state:
        return f"[错误] {state['error']}"

    lines = []
    lines.append(f"当前页面：{state.get('title', '无标题')}")
    lines.append(f"当前 URL：{state.get('url', '未知')}")

    elements = state.get('elements', [])
    if elements:
        lines.append("\n可交互元素列表：")
        for el in elements[:30]:  # 最多显示30个元素
            desc = f"  [{el['index']}] <{el['tag']}>"
            if el.get('text'):
                desc += f" \"{el['text']}\""
            if el.get('href'):
                desc += f" → {el['href'][:60]}"
            if el.get('type') and el['type'] not in ('text', ''):
                desc += f" (type={el['type']})"
            lines.append(desc)
    else:
        lines.append("\n[页面上没有发现可交互元素]")

    preview = state.get('body_preview', '')
    if preview:
        lines.append(f"\n页面正文摘要（前2000字）：\n{preview}")

    return '\n'.join(lines)


# ── 智能体主类 ──────────────────────────────────────────────

class BrowserAgent:
    """浏览器自动化智能体

    基于 Qwen-Agent 框架的 LLM，通过 Playwright 控制浏览器，
    实现自然语言驱动的网页自动化操作。
    """

    def __init__(self, api_key: str = None, model: str = None, model_server: str = None,
                 browser_type: str = None, headless: bool = None,
                 max_steps: int = None):
        # 使用 Qwen-Agent 的 LLM
        model = model or Config.MODEL_NAME
        api_key = api_key or Config.DASHSCOPE_API_KEY
        model_server = model_server or Config.MODEL_SERVER
        cfg = {
            'model': model,
            'model_server': model_server,
        }
        if api_key:
            cfg['api_key'] = api_key

        self._llm_cfg = cfg
        self.llm = None
        self.browser = BrowserController(
            browser_type=browser_type or Config.BROWSER_TYPE,
            headless=headless if headless is not None else Config.HEADLESS,
            screenshot_dir=Config.SCREENSHOT_DIR
        )
        self.max_steps = max_steps or Config.MAX_STEPS

        # 对话历史（包含系统提示、用户任务、LLM 思考、系统反馈）
        self.messages: list = [Message(role='system', content=SYSTEM_PROMPT)]

        # 运行状态
        self.screenshot_paths: list = []
        self.executed_actions: list = []
        self.final_result: Optional[str] = None
        self.error: Optional[str] = None

    # ── 公开接口 ──────────────────────────────────────────

    def run(self, task: str) -> dict:
        """执行一个自然语言任务

        Args:
            task: 用户的任务描述，如"搜索今天的天气"、"登录某某网站"

        Returns:
            包含执行结果的字典
        """
        # 延迟初始化 LLM（在 browser.start 之后，避免 httpx 连接池污染）
        self.browser.start()
        if self.llm is None:
            from qwen_agent.llm import get_chat_model
            self.llm = get_chat_model(self._llm_cfg)

        # 添加用户任务
        self.messages.append(Message(role='user', content=f"任务：{task}"))

        self._log_step('user', task)

        for step in range(1, self.max_steps + 1):
            try:
                # ── 调用 LLM ──────────────────────────
                self._log_step('thinking', f"第 {step}/{self.max_steps} 步：正在推理...")

                response_batch = None
                for rsp in self.llm.chat(
                    messages=self.messages,
                    functions=None,
                    stream=False,
                    extra_generate_cfg={
                        'temperature': 0.3,
                        'top_p': 0.9,
                        'max_input_tokens': 8000,
                    }
                ):
                    response_batch = rsp

                if not response_batch:
                    self._log_step('error', 'LLM 返回为空')
                    continue

                last_msg = response_batch[-1]
                content = last_msg.get('content', '')
                if not content:
                    self._log_step('error', 'LLM 返回内容为空')
                    continue

                self.messages.append(last_msg)
                self._log_step('llm', content[:300])

                # ── 解析操作 ──────────────────────────
                action = parse_action(content)

                # ── 执行操作 ──────────────────────────
                if action['action'] == 'done':
                    self.final_result = action.get('result', '任务完成')
                    self._log_step('done', self.final_result)
                    break

                exec_result = self._execute_action(action)
                self.executed_actions.append({
                    'step': step,
                    'action': action,
                    'result': exec_result
                })

                # ── 截图 ─────────────────────────────
                ss_path = self.browser.screenshot(name=f'step_{step:02d}')
                if ss_path:
                    self.screenshot_paths.append(ss_path)

                # ── 反馈给 LLM ───────────────────────
                feedback = self._build_feedback(action, exec_result)
                self.messages.append(Message(role='user', content=feedback))
                self._log_step('feedback', feedback[:200])

            except Exception as e:
                error_msg = f"步骤 {step} 执行出错：{str(e)}"
                self._log_step('error', error_msg)
                # 尝试继续，不直接崩溃

        self.browser.close()

        success = self.final_result is not None
        return {
            'success': success,
            'result': self.final_result,
            'error': self.error,
            'steps': len(self.executed_actions),
            'screenshots': self.screenshot_paths,
            'actions': self.executed_actions,
            'logs': getattr(self, '_step_logs', []),
        }

    # ── 内部方法 ──────────────────────────────────────────

    def _execute_action(self, action: dict) -> dict:
        """执行单个浏览器操作"""
        action_type = action.get('action')

        if action_type == 'navigate':
            url = action.get('url', '')
            if not url:
                return {'error': '缺少 URL 参数'}
            state = self.browser.navigate(url)
            return {'state': state}

        elif action_type == 'click':
            index = action.get('index')
            if index is None:
                return {'error': '缺少 INDEX 参数'}
            return self.browser.click(index)

        elif action_type == 'type':
            index = action.get('index')
            text = action.get('text', '')
            if index is None:
                return {'error': '缺少 INDEX 或 TEXT 参数'}
            return self.browser.type_text(index, text)

        elif action_type == 'enter':
            return self.browser.press_enter()

        elif action_type == 'scroll':
            return self.browser.scroll(action.get('direction', 'down'))

        else:
            return {'error': f'未知操作: {action_type}'}

    def _build_feedback(self, action: dict, exec_result: dict) -> str:
        """构建操作结果反馈，供 LLM 继续推理"""
        parts = ["## 操作结果\n"]

        # 操作描述
        parts.append(f"已执行：{action_to_string(action)}")

        # 是否有错误
        if 'error' in exec_result:
            parts.append(f"\n⚠️ 执行出错：{exec_result['error']}")
            parts.append("\n请尝试其他操作方法或备选方案。")
            return '\n'.join(parts)

        # 页面状态
        if 'state' in exec_result:
            parts.append('\n' + format_page_state(exec_result['state']))
        elif 'page' in exec_result:
            parts.append('\n' + format_page_state(exec_result['page']))

        # 点击结果
        if 'result' in exec_result:
            parts.append(f"\n操作返回值：{exec_result['result']}")

        parts.append("\n请根据当前页面状态决定下一步操作。如果任务已完成，请输出 ACTION: done。")
        return '\n'.join(parts)

    def _log_step(self, step_type: str, content: str):
        """记录步骤日志"""
        if not hasattr(self, '_step_logs'):
            self._step_logs = []
        self._step_logs.append({
            'time': datetime.now().strftime('%H:%M:%S'),
            'type': step_type,
            'content': content
        })

    def get_logs(self) -> list:
        """获取完整日志"""
        return getattr(self, '_step_logs', [])


# ── 便捷 CLI 入口 ──────────────────────────────────────────

def main():
    """命令行入口"""
    import sys
    from .config import Config

    if len(sys.argv) < 2:
        print("用法：python -m src.demo.run_demo \"你的任务描述\"")
        print("示例：python -m src.demo.run_demo \"搜索 Python 教程\"")
        sys.exit(1)

    task = ' '.join(sys.argv[1:])
    agent = BrowserAgent()
    result = agent.run(task)

    print("\n" + "=" * 60)
    print("任务执行结果")
    print("=" * 60)
    if result['success']:
        print(f"\n✅ 完成！结果：{result['result']}")
    else:
        print(f"\n❌ 失败：{result.get('error', '未知错误')}")
    print(f"总步数：{result.get('steps', 0)}")
    print(f"截图：{len(result.get('screenshots', []))} 张")
    print("\n操作记录：")
    for a in result.get('actions', []):
        print(f"  Step {a['step']}: {action_to_string(a['action'])}")


if __name__ == '__main__':
    main()
