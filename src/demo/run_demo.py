# -*- coding: utf-8 -*-
"""
CLI 演示脚本

用法：
  python src/demo/run_demo.py "搜索今天的新闻"
  python src/demo/run_demo.py "打开百度，搜索 Python 教程"
"""

import sys
import os

# 确保能找到 src 包
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.agent import BrowserAgent, action_to_string
from core.config import Config


def print_header(text: str):
    """打印带分隔线的标题"""
    print()
    print('=' * 60)
    print(f'  {text}')
    print('=' * 60)


def run_interactive():
    """交互式任务输入"""
    print_header('BrowserAgent - 浏览器自动化智能体 (CLI)')
    print('输入你的任务，或输入 "exit" 退出')
    print()

    # 检查配置
    try:
        Config.validate()
        print('✅ 配置检查通过')
    except ValueError as e:
        print(f'❌ {e}')
        return

    while True:
        task = input('\n🎯 任务 > ').strip()
        if not task:
            continue
        if task.lower() in ('exit', 'quit', 'q'):
            break

        agent = BrowserAgent(headless=False)
        print(f'\n🤖 开始执行任务: "{task}"')
        print(f'📋 最大步数: {agent.max_steps}')
        print()

        result = agent.run(task)

        print()
        if result['success']:
            print(f'✅ 任务完成！')
            print(f'📝 结果: {result["result"]}')
        else:
            print(f'❌ 任务失败')
            if result.get('error'):
                print(f'  错误: {result["error"]}')

        print(f'📊 统计: {result.get("steps", 0)} 步, '
              f'{len(result.get("screenshots", []))} 张截图')

        # 打印操作摘要
        print('\n操作记录:')
        for a in result.get('actions', []):
            print(f'  Step {a["step"]}: {action_to_string(a["action"])}')

        # 打印详细日志
        print('\n详细日志:')
        for log in agent.get_logs():
            icon = {'user': '👤', 'thinking': '🤖', 'llm': '🧠', 'feedback': '📋',
                    'done': '✅', 'error': '❌', 'warning': '⚠️'}.get(log['type'], '•')
            print(f'  [{log["time"]}] {icon} {log["content"][:120]}')


def main():
    if len(sys.argv) > 1:
        # 从命令行参数读取任务
        task = ' '.join(sys.argv[1:])
        print_header(f'BrowserAgent - 任务: {task[:50]}...')
        agent = BrowserAgent(headless=False)
        result = agent.run(task)

        print()
        if result['success']:
            print(f'✅ 结果: {result["result"]}')
        else:
            print(f'❌ 失败: {result.get("error", "未知错误")}')
        print(f'📊 {result.get("steps", 0)} 步, '
              f'{len(result.get("screenshots", []))} 张截图')
    else:
        run_interactive()


def cli_main():
    """Argument-based CLI supporting deterministic and live model runs."""
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="BrowserAgent CLI")
    parser.add_argument("task", nargs="?", help="自然语言浏览器任务")
    parser.add_argument("--scripted", metavar="TASK_ID", help="运行 evals/tasks.json 中的确定性任务")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON")
    parser.add_argument("--output-dir", default="artifacts", help="结果文件目录")
    parser.add_argument("--headful", action="store_true", help="显示浏览器窗口")
    args = parser.parse_args()

    if args.scripted:
        from evals.run import load_tasks, run_scripted_task
        from core.browser_controller import BrowserController

        task = next((item for item in load_tasks() if item["id"] == args.scripted), None)
        if task is None:
            parser.error(f"unknown scripted task: {args.scripted}")
        base_url = (Path(__file__).parents[2] / "demo_site" / "index.html").resolve().as_uri()
        controller = BrowserController(
            headless=not args.headful,
            browser_type=Config.BROWSER_TYPE,
            screenshot_dir=str(Path(args.output_dir) / "screenshots"),
        )
        try:
            result = run_scripted_task(controller, task, base_url)
        finally:
            controller.close()
        output = Path(args.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        (output / f"{task['id']}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        if not args.task:
            parser.error("provide a task or --scripted TASK_ID")
        result = BrowserAgent(headless=not args.headful).run(args.task)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    cli_main()
