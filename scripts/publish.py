#!/usr/bin/env python3
"""
铺货模块 - 商品铺货到下游店铺

Usage:
    python3 publish.py --shop-code "260391138" --item-ids "123,456"
    python3 publish.py --shop-code "260391138" --data-id "20240101_120000"
"""

import argparse
import os
import json
import sys
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _api import publish_items, list_bound_shops, PublishResult
from _const import CHANNEL_MAP, DATA_DIR, PUBLISH_LIMIT


def load_products_by_data_id(data_id: str) -> Optional[List[str]]:
    """
    根据 data_id 加载商品ID列表
    
    Args:
        data_id: 搜索结果的数据ID
    
    Returns:
        商品ID列表，未找到返回 None
    """
    filepath = os.path.join(DATA_DIR, f"1688_{data_id}.json")
    
    if not os.path.exists(filepath):
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 支持Map格式（与API返回一致）
        products = data.get("products", {})
        if isinstance(products, dict):
            return list(products.keys())
        elif isinstance(products, list):
            return [p.get("id") for p in products if p.get("id")]
        return []
    except Exception:
        return None


def format_publish_result(result: PublishResult, shop_name: str = "", origin_count: int = 0) -> str:
    """
    格式化铺货结果为 Markdown
    
    Args:
        result: 铺货结果
        shop_name: 店铺名称（可选）
    
    Returns:
        Markdown 格式字符串
    """
    lines = [f"## 铺货结果\n"]
    
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
        lines.append("❌ **铺货失败**")
        lines.append("")
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
                error = item.get("error", "未知错误")
                lines.append(f"- {error}")
        
        lines.append("")
        lines.append("建议：")
        lines.append("1. 检查店铺授权是否过期")
        lines.append("2. 确认商品信息完整")
        lines.append("3. 稍后重试")
    
    return "\n".join(lines)


def publish_with_check(item_ids: List[str], shop_code: str, dry_run: bool = False) -> dict:
    """
    带检查的铺货（便捷函数）
    
    Args:
        item_ids: 商品ID列表
        shop_code: 店铺代码
    
    Returns:
        {"success": bool, "markdown": str, "result": PublishResult}
    """
    # 检查店铺是否存在且有效
    shops = list_bound_shops()
    target_shop = next((s for s in shops if s.code == shop_code), None)
    
    if not target_shop:
        return {
            "success": False,
            "markdown": "❌ 店铺不存在，请检查店铺代码。",
            "result": PublishResult(success=False, published_count=0, failed_items=[{"error": "店铺不存在"}]),
            "origin_count": len(item_ids),
        }
    
    if not target_shop.is_authorized:
        return {
            "success": False,
            "markdown": f"❌ 店铺「{target_shop.name}」授权已过期，请在1688 AI版APP中重新授权。",
            "result": PublishResult(success=False, published_count=0, failed_items=[{"error": "授权过期"}]),
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
            + (f"- ⚠️ 超出接口限制，仅会提交前 {PUBLISH_LIMIT} 个\n" if origin_count > PUBLISH_LIMIT else "")
            + "\n确认后去掉 `--dry-run` 执行正式铺货。"
        )
        return {
            "success": True,
            "markdown": markdown,
            "result": PublishResult(
                success=True,
                published_count=0,
                failed_items=[],
                submitted_count=preview_count,
                fail_count=0,
                all_count=origin_count,
            ),
            "origin_count": origin_count,
        }

    channel = CHANNEL_MAP.get(target_shop.channel, "douyin")
    result = publish_items(item_ids, shop_code, channel=channel)
    markdown = format_publish_result(result, target_shop.name, origin_count=origin_count)
    
    return {
        "success": result.success,
        "markdown": markdown,
        "result": result,
        "origin_count": origin_count,
    }


def normalize_item_ids(raw_item_ids: List[str]) -> List[str]:
    """清洗并去重商品ID，保留顺序"""
    seen = set()
    cleaned = []
    for item_id in raw_item_ids:
        if not item_id:
            continue
        if item_id in seen:
            continue
        seen.add(item_id)
        cleaned.append(item_id)
    return cleaned


def main():
    parser = argparse.ArgumentParser(description="1688 铺货到下游店铺")
    parser.add_argument("--shop-code", required=True, help="目标店铺代码")
    parser.add_argument("--dry-run", action="store_true", help="仅做预检查，不执行实际铺货")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--item-ids", help="商品ID列表，逗号分隔")
    group.add_argument("--data-id", help="选品结果的 data_id（从 search.py 获取）")
    args = parser.parse_args()

    if args.data_id:
        item_ids = load_products_by_data_id(args.data_id)
        if not item_ids:
            print(json.dumps({
                "success": False,
                "markdown": f"❌ 未找到 data_id=`{args.data_id}` 对应的选品结果，请重新搜索后获取新的 data_id。",
                "data": {"success": False},
            }, ensure_ascii=False))
            sys.exit(1)
    else:
        item_ids = [x.strip() for x in args.item_ids.split(",") if x.strip()]

    item_ids = normalize_item_ids(item_ids)

    if not item_ids:
        print(json.dumps({
            "success": False,
            "markdown": "❌ 没有可用的商品ID，请检查 `--item-ids` 或 `--data-id`。",
            "data": {"success": False},
        }, ensure_ascii=False))
        sys.exit(1)

    try:
        result = publish_with_check(item_ids, args.shop_code, dry_run=args.dry_run)
        submitted_count = min(result["origin_count"], PUBLISH_LIMIT)
        fail_count = result["result"].fail_count
        success_count = result["result"].published_count
        output = {
            "success": result["success"],
            "markdown": result["markdown"],
            "data": {
                "success": result["success"],
                "origin_count": result["origin_count"],
                "submitted_count": submitted_count,
                "success_count": success_count,
                "fail_count": fail_count,
                "dry_run": args.dry_run,
            },
        }
    except Exception as e:
        output = {
            "success": False,
            "markdown": f"铺货失败（网络异常，已重试3次）：{e}",
            "data": {"success": False},
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()