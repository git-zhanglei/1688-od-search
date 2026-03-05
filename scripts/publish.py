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
from api import publish_items, list_bound_shops, PublishResult, CHANNEL_MAP


def load_products_by_data_id(data_id: str) -> Optional[List[str]]:
    """
    根据 data_id 加载商品ID列表
    
    Args:
        data_id: 搜索结果的数据ID
    
    Returns:
        商品ID列表，未找到返回 None
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(
        os.path.dirname(script_dir), 
        "data", "products", 
        f"1688_{data_id}.json"
    )
    
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


def format_publish_result(result: PublishResult, shop_name: str = "") -> str:
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
        lines.append("")
        lines.append("请登录对应平台后台查看已发布的商品。")
    else:
        lines.append("❌ **铺货失败**")
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


def publish_with_check(item_ids: List[str], shop_code: str) -> dict:
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
            "result": PublishResult(success=False, published_count=0, failed_items=[{"error": "店铺不存在"}])
        }
    
    if not target_shop.is_authorized:
        return {
            "success": False,
            "markdown": f"❌ 店铺「{target_shop.name}」授权已过期，请在1688 AI版APP中重新授权。",
            "result": PublishResult(success=False, published_count=0, failed_items=[{"error": "授权过期"}])
        }
    
    channel = CHANNEL_MAP.get(target_shop.channel, "douyin")
    result = publish_items(item_ids, shop_code, channel=channel)
    markdown = format_publish_result(result, target_shop.name)
    
    return {
        "success": result.success,
        "markdown": markdown,
        "result": result
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="1688 铺货到下游店铺")
    parser.add_argument("--shop-code", required=True, help="目标店铺代码")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--item-ids", help="商品ID列表，逗号分隔")
    group.add_argument("--data-id", help="选品结果的 data_id（从 search.py 获取）")
    args = parser.parse_args()

    if args.data_id:
        item_ids = load_products_by_data_id(args.data_id)
        if not item_ids:
            print(json.dumps({"success": False, "error": f"未找到 data_id={args.data_id} 对应的选品结果"}, ensure_ascii=False))
            sys.exit(1)
    else:
        item_ids = [x.strip() for x in args.item_ids.split(",") if x.strip()]

    try:
        result = publish_with_check(item_ids, args.shop_code)
        output = {
            "success": result["success"],
            "markdown": result["markdown"],
        }
    except Exception as e:
        output = {
            "success": False,
            "markdown": f"铺货失败（网络异常，已重试3次）：{e}",
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))