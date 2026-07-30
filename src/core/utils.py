# -*- coding: utf-8 -*-
"""工具函数"""

import json


def pretty_json(obj, indent=2) -> str:
    """格式化 JSON 输出"""
    try:
        return json.dumps(obj, ensure_ascii=False, indent=indent)
    except Exception:
        return str(obj)


def truncate(text: str, max_len: int = 200) -> str:
    """截断文本到指定长度"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + '...'
