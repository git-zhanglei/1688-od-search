#!/usr/bin/env python3
"""
统一输出工具

所有 cmd.py 通过此模块输出 JSON，保证格式一致。
"""

import json

from _errors import SkillError, AuthError


def make_output(success: bool, markdown: str, data: dict) -> dict:
    return {"success": success, "markdown": markdown, "data": data}


def print_output(success: bool, markdown: str, data: dict):
    """打印标准 JSON 输出"""
    print(json.dumps(make_output(success, markdown, data), ensure_ascii=False, indent=2))


def print_error(e: Exception, default_data: dict = None):
    """将异常转为标准错误输出并打印"""
    if isinstance(e, AuthError):
        msg = f"❌ {e.message}\n\n请运行: `cli.py configure YOUR_AK`"
    elif isinstance(e, SkillError):
        msg = f"❌ {e.message}"
    elif isinstance(e, ValueError):
        msg = f"❌ 参数错误：{e}"
    else:
        msg = f"❌ 操作失败：{e}"
    print_output(False, msg, default_data or {})


def fmt_rate(v) -> str:
    """小数转百分比，如 0.857 → 85.7%；无值返回 -"""
    if v is None:
        return "-"
    try:
        f = float(v)
        return f"{f * 100:.1f}%" if f <= 1.0 else f"{f:.1f}%"
    except (TypeError, ValueError):
        return str(v)
