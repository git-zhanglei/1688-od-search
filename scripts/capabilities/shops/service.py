#!/usr/bin/env python3
"""店铺服务 — 查询和管理绑定店铺"""

from dataclasses import dataclass
from typing import List

from _http import api_post


@dataclass
class Shop:
    """店铺信息"""
    code: str
    name: str
    channel: str
    is_authorized: bool


def list_bound_shops() -> List[Shop]:
    """
    查询已绑定的店铺列表

    Returns:
        Shop 列表

    Raises:
        SkillError 子类: API 调用失败
    """
    model = api_post("/1688claw/skill/searchshop", {})

    shops_data = model.get("data", [])
    if not isinstance(shops_data, list):
        return []

    shops = []
    for s in shops_data:
        shops.append(Shop(
            code=s.get("shopCode", ""),
            name=s.get("shopName", "未知店铺"),
            channel=s.get("channel") or "",
            is_authorized=not (s.get("toolExpired", False) or s.get("shopExpired", False)),
        ))
    return shops


def format_shop_list(shops: List[Shop]) -> str:
    """格式化店铺列表为 Markdown 表格"""
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


def check_shop_status() -> dict:
    """
    检查店铺状态

    Returns:
        {"all": List[Shop], "valid": List[Shop], "expired": List[Shop], "markdown": str}
    """
    all_shops = list_bound_shops()
    valid_shops = [s for s in all_shops if s.is_authorized]
    expired_shops = [s for s in all_shops if not s.is_authorized]

    return {
        "all": all_shops,
        "valid": valid_shops,
        "expired": expired_shops,
        "markdown": format_shop_list(all_shops),
    }
