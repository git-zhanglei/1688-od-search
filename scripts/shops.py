#!/usr/bin/env python3
"""
店铺管理模块 - 查询和展示绑定店铺

Usage:
    python3 shops.py
"""

import json
import os
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _api import list_bound_shops, Shop


def format_shop_list(shops: List[Shop]) -> str:
    """
    格式化店铺列表为 Markdown 表格

    Args:
        shops: 店铺列表

    Returns:
        Markdown 格式字符串
    """
    if not shops:
        return "暂无绑定的店铺。"

    lines = [f"你共绑定了 **{len(shops)}** 个店铺：\n"]

    lines.append("| # | 店铺 | 平台 | 状态 | 店铺代码 |")
    lines.append("| --- | --- | --- | --- | --- |")

    for i, s in enumerate(shops, 1):
        status = "✅ 正常" if s.is_authorized else "⚠️ 授权过期"
        name = s.name.replace("|", "\\|")
        channel = s.channel.replace("|", "\\|")
        lines.append(f"| {i} | **{name}** | {channel} | {status} | `{s.code}` |")

    return "\n".join(lines)


def get_valid_shops() -> List[Shop]:
    """
    获取授权有效的店铺列表
    
    Returns:
        有效店铺列表
    """
    all_shops = list_bound_shops()
    return [s for s in all_shops if s.is_authorized]


def check_shop_status() -> dict:
    """
    检查店铺状态（便捷函数）
    
    Returns:
        {
            "all": List[Shop],
            "valid": List[Shop],
            "expired": List[Shop],
            "markdown": str
        }
    """
    all_shops = list_bound_shops()
    valid_shops = [s for s in all_shops if s.is_authorized]
    expired_shops = [s for s in all_shops if not s.is_authorized]
    
    return {
        "all": all_shops,
        "valid": valid_shops,
        "expired": expired_shops,
        "markdown": format_shop_list(all_shops)
    }


if __name__ == "__main__":
    try:
        status = check_shop_status()
        output = {
            "total": len(status["all"]),
            "valid_count": len(status["valid"]),
            "expired_count": len(status["expired"]),
            "shops": [
                {"code": s.code, "name": s.name, "channel": s.channel, "is_authorized": s.is_authorized}
                for s in status["all"]
            ],
            "markdown": status["markdown"],
        }
    except Exception as e:
        output = {
            "total": 0,
            "valid_count": 0,
            "expired_count": 0,
            "shops": [],
            "markdown": f"查询店铺失败（网络异常，已重试3次）：{e}",
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))