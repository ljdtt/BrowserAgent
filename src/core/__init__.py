# -*- coding: utf-8 -*-
"""
BrowserAgent - 基于 Qwen-Agent 的浏览器自动化智能体

提供自然语言驱动的浏览器操作能力。
"""

from .config import Config
from .browser_controller import BrowserController
from .agent import BrowserAgent

__all__ = ['Config', 'BrowserController', 'BrowserAgent']
__version__ = '0.1.0'
