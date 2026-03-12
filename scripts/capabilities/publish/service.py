#!/usr/bin/env python3
"""铺货服务 — 商品铺货到下游店铺"""

import json
import os
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from _http import api_post
from _const import CHANNEL_MAP, DATA_DIR, PUBLISH_LIMIT
from _errors import SkillError
from capabilities.shops.service import list_bound_shops


@dataclass
class PublishResult:
    """铺货结果"""
    success: bool
    published_count: int
    failed_items: List[Dict[str, Any]]
    submitted_count: int = 0
    fail_count: int = 0
    all_count: int = 0


def load_products_by_data_id(data_id: str) -> Optional[List[str]]:
    """根据 data_id 加载商品ID列表，未找到返回 None"""
    filepath = os.path.join(DATA_DIR, f"1688_{data_id}.json")
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        products = data.get("products", {})
        if isinstance(products, dict):
            return list(products.keys())
        elif isinstance(products, list):
            return [p.get("id") for p in products if p.get("id")]
        return []
    except Exception:
        return None


def normalize_item_ids(raw_item_ids: List[str]) -> List[str]:
    """清洗并去重商品ID，保留顺序"""
    seen = set()
    cleaned = []
    for item_id in raw_item_ids:
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        cleaned.append(item_id)
    return cleaned


def publish_items(item_ids: List[str], shop_code: str,
                  channel: Optional[str] = None) -> PublishResult:
    """
    铺货到指定店铺

    写操作内部捕获 API 异常并返回 PublishResult(success=False)，
    因为铺货有"部分成功"语义，调用方需要统一结构。
    """
    if not channel:
        shops = list_bound_shops()
        target_shop = next((s for s in shops if s.code == shop_code), None)
        if not target_shop:
            return PublishResult(success=False, published_count=0,
                                failed_items=[{"error": "店铺不存在"}])
        if not target_shop.is_authorized:
            return PublishResult(success=False, published_count=0,
                                failed_items=[{"error": "店铺授权已过期"}])
        channel = CHANNEL_MAP.get(target_shop.channel)
        if not channel:
            return PublishResult(success=False, published_count=0,
                                failed_items=[{"error": f"未知渠道: {target_shop.channel}"}])

    submitted_count = len(item_ids[:PUBLISH_LIMIT])

    try:
        model = api_post("/1688claw/skill/distributingoffer", {
            "offerIdList": ",".join(item_ids[:PUBLISH_LIMIT]),
            "channel": channel,
            "shopCode": shop_code,
        }, timeout=60)
    except SkillError as e:
        return PublishResult(
            success=False, published_count=0,
            failed_items=[{"error": e.message}],
            submitted_count=submitted_count,
            fail_count=submitted_count, all_count=submitted_count,
        )

    model_data = model.get("data", {})
    parsed = model_data if isinstance(model_data, dict) else {}

    success_count = parsed.get("successCount")
    fail_count_val = parsed.get("failCount")
    all_count_val = parsed.get("allCount")

    if success_count is None:
        return PublishResult(
            success=False, published_count=0,
            failed_items=[{"error": "铺货结果未知（平台未返回结果计数），请登录平台后台确认"}],
            submitted_count=submitted_count,
            fail_count=0, all_count=submitted_count,
        )

    published_count = int(success_count)

    return PublishResult(
        success=True,
        published_count=published_count,
        failed_items=[],
        submitted_count=submitted_count,
        fail_count=(int(fail_count_val) if fail_count_val is not None
                    else max(submitted_count - published_count, 0)),
        all_count=int(all_count_val) if all_count_val is not None else submitted_count,
    )


def format_publish_result(result: PublishResult, shop_name: str = "",
                          origin_count: int = 0) -> str:
    """格式化铺货结果为 Markdown"""
    lines = ["## 铺货结果\n"]
    if shop_name:
        lines.append(f"**目标店铺**: {shop_name}\n")

    if result.success:
        lines.append(f"✅ **成功铺货 {result.published_count} 个商品**")
        if result.submitted_count:
            lines.append(f"- 本次提交：{result.submitted_count} 个")
        if result.fail_count:
            lines.append(f"- 失败：{result.fail_count} 个")
        if origin_count > PUBLISH_LIMIT:
            lines.append(f"- ⚠️ 检测到商品总数 {origin_count}，按接口限制仅提交前 {PUBLISH_LIMIT} 个")
        lines.append("")
        lines.append("请登录对应平台后台查看已发布的商品。")
    else:
        lines.append("❌ **铺货失败**\n")
        if result.submitted_count:
            lines.append(f"- 本次提交：{result.submitted_count} 个")
        if result.fail_count:
            lines.append(f"- 失败：{result.fail_count} 个")
        if origin_count > PUBLISH_LIMIT:
            lines.append(f"- ⚠️ 检测到商品总数 {origin_count}，按接口限制仅提交前 {PUBLISH_LIMIT} 个")
        lines.append("")
        if result.failed_items:
            lines.append("**失败原因**:")
            for item in result.failed_items:
                lines.append(f"- {item.get('error', '未知错误')}")
        lines.append("\n建议：")
        lines.append("1. 检查店铺授权是否过期")
        lines.append("2. 确认商品信息完整")
        lines.append("3. 稍后重试")

    return "\n".join(lines)


def publish_with_check(item_ids: List[str], shop_code: str,
                       dry_run: bool = False) -> dict:
    """带店铺校验的铺货（主流程入口）"""
    shops = list_bound_shops()
    target_shop = next((s for s in shops if s.code == shop_code), None)

    if not target_shop:
        return {
            "success": False,
            "markdown": "❌ 店铺不存在，请检查店铺代码。",
            "result": PublishResult(success=False, published_count=0,
                                   failed_items=[{"error": "店铺不存在"}]),
            "origin_count": len(item_ids),
        }

    if not target_shop.is_authorized:
        return {
            "success": False,
            "markdown": f"❌ 店铺「{target_shop.name}」授权已过期，请在1688 AI版APP中重新授权。",
            "result": PublishResult(success=False, published_count=0,
                                   failed_items=[{"error": "授权过期"}]),
            "origin_count": len(item_ids),
        }

    origin_count = len(item_ids)

    if dry_run:
        preview_count = min(origin_count, PUBLISH_LIMIT)
        markdown = (
            "## 铺货预检查结果\n\n"
            f"✅ 店铺校验通过：{target_shop.name}\n"
            f"- 来源商品数：{origin_count}\n"
            f"- 实际将提交：{preview_count}\n"
            + (f"- ⚠️ 超出接口限制，仅会提交前 {PUBLISH_LIMIT} 个\n"
               if origin_count > PUBLISH_LIMIT else "")
            + "\n确认后去掉 `--dry-run` 执行正式铺货。"
        )
        return {
            "success": True, "markdown": markdown,
            "result": PublishResult(
                success=True, published_count=0, failed_items=[],
                submitted_count=preview_count, fail_count=0, all_count=origin_count),
            "origin_count": origin_count,
        }

    channel = CHANNEL_MAP.get(target_shop.channel)
    if not channel:
        return {
            "success": False,
            "markdown": f"❌ 店铺「{target_shop.name}」的渠道「{target_shop.channel}」无法识别，请联系客服确认。",
            "result": PublishResult(success=False, published_count=0,
                                   failed_items=[{"error": f"未知渠道: {target_shop.channel}"}]),
            "origin_count": origin_count,
        }

    result = publish_items(item_ids, shop_code, channel=channel)
    markdown = format_publish_result(result, target_shop.name, origin_count=origin_count)

    return {
        "success": result.success, "markdown": markdown,
        "result": result, "origin_count": origin_count,
    }
