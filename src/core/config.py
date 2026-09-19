# -*- coding: utf-8 -*-
"""
配置管理：从环境变量加载 API Key、模型名等
"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))


class Config:
    """全局配置，从环境变量读取"""

    # DashScope API 密钥（阿里云通义千问）
    DASHSCOPE_API_KEY: str = os.getenv('DASHSCOPE_API_KEY', '')

    # 使用的 Qwen 模型名称
    MODEL_NAME: str = os.getenv('MODEL_NAME', 'qwen-plus')
    # ?? API ???DashScope ?????????????
    MODEL_SERVER: str = os.getenv('MODEL_SERVER', 'https://dashscope.aliyuncs.com/compatible-mode/v1')

    # 浏览器类型：msedge / chrome
    BROWSER_TYPE: str = os.getenv('BROWSER_TYPE', 'msedge')

    # 是否无头模式（不显示浏览器窗口）
    HEADLESS: bool = os.getenv('HEADLESS', 'false').lower() == 'true'

    # 智能体最大步数
    MAX_STEPS: int = int(os.getenv('MAX_STEPS', '15'))

    # 连续无效模型调用、无进展操作及单任务执行时间限制
    MAX_INVALID_CALLS: int = int(os.getenv('MAX_INVALID_CALLS', '2'))
    MAX_NO_PROGRESS: int = int(os.getenv('MAX_NO_PROGRESS', '3'))
    TASK_TIMEOUT_SECONDS: int = int(os.getenv('TASK_TIMEOUT_SECONDS', '180'))

    # 截图保存目录
    SCREENSHOT_DIR: str = os.getenv('SCREENSHOT_DIR',
                                     os.path.join(os.path.dirname(__file__), '..', '..', 'screenshots'))

    # 日志保存目录
    LOG_DIR: str = os.getenv('LOG_DIR',
                             os.path.join(os.path.dirname(__file__), '..', '..', 'logs'))

    # 每次运行的事件、结果和截图目录
    ARTIFACT_DIR: str = os.getenv(
        'ARTIFACT_DIR', os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts')
    )

    @classmethod
    def validate(cls):
        """检查必要配置是否就绪"""
        if not cls.DASHSCOPE_API_KEY:
            raise ValueError(
                "DASHSCOPE_API_KEY 未设置！\n"
                "请在项目根目录创建 .env 文件，添加一行:\n"
                "  DASHSCOPE_API_KEY=你的密钥\n"
                "获取密钥: https://help.aliyun.com/zh/dashscope/developer-reference/activate-dashscope-and-create-an-api-key"
            )
        return True
