#!/usr/bin/env python3
"""
选品模块 - 商品搜索和结果处理

Usage:
    python3 search.py --query "连衣裙" [--channel douyin]
"""

import argparse
import os
import json
from datetime import datetime
from pathlib import Path
from typing import List

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api import search_products, Product


def save_search_result(products: List[Product], query: str, channel: str) -> str:
    """
    保存搜索结果到文件（含完整 stats）

    Returns:
        data_id (时间戳格式)
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(script_dir), "data", "products")
    Path(data_dir).mkdir(parents=True, exist_ok=True)

    data_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(data_dir, f"1688_{data_id}.json")

    products_map = {}
    for p in products:
        entry = {
            "title": p.title,
            "price": p.price,
            "image": p.image,
        }
        if p.stats:
            entry["stats"] = p.stats
        products_map[p.id] = entry

    data = {
        "query": query,
        "channel": channel,
        "timestamp": datetime.now().isoformat(),
        "data_id": data_id,
        "products": products_map,
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data_id


def format_product_list(products: List[Product], max_show: int = 20) -> str:
    """
    格式化商品列表为 Markdown（含关键 stats 指标）

    Args:
        products: 商品列表
        max_show: markdown 中最多展示的商品数（完整数据始终在 JSON products 字段中）
    """
    if not products:
        return "未找到符合条件的商品。"

    lines = [f"找到 **{len(products)}** 个商品：\n"]

    for i, p in enumerate(products[:max_show], 1):
        lines.append(f"---")
        lines.append(f"**{i}. {p.title}**")
        if p.image:
            lines.append(f"![商品图]({p.image})")
        lines.append(f"💰 **¥{p.price}**")

        s = p.stats or {}
        if s:
            # 核心指标表格
            rows = []
            if s.get("last30DaysSales") is not None:
                rows.append(("30天销量", str(s["last30DaysSales"])))
            if s.get("goodRates") is not None:
                rows.append(("好评率", str(s["goodRates"])))
            if s.get("repurchaseRate") is not None:
                rows.append(("复购率", str(s["repurchaseRate"])))
            if s.get("downstreamOffer") is not None:
                rows.append(("铺货数", str(s["downstreamOffer"])))

            if rows:
                lines.append("")
                lines.append("| " + " | ".join(r[0] for r in rows) + " |")
                lines.append("| " + " | ".join("---" for _ in rows) + " |")
                lines.append("| " + " | ".join(r[1] for r in rows) + " |")
                lines.append("")

            # 补充指标（单行紧凑展示）
            extra = []
            if s.get("totalSales") is not None:
                extra.append(f"累计销量 {s['totalSales']}")
            if s.get("collectionRate24h") is not None:
                extra.append(f"揽收率 {s['collectionRate24h']}")
            if s.get("remarkCnt") is not None:
                extra.append(f"{s['remarkCnt']}条评价")
            cat = s.get("categoryListName") or s.get("categoryName") or ""
            if cat:
                extra.append(cat)
            if extra:
                lines.append(" · ".join(extra))

        lines.append(f"[查看详情]({p.url}) · `{p.id}`")
        lines.append("")

    if len(products) > max_show:
        lines.append(f"*... 还有 {len(products) - max_show} 个商品，完整数据见 JSON 输出*")

    return "\n".join(lines)


def search_and_save(query: str, channel: str = "douyin") -> dict:
    """
    搜索并保存结果

    Returns:
        {"products": List[Product], "data_id": str, "markdown": str}
    """
    products = search_products(query, channel)

    if not products:
        return {
            "products": [],
            "data_id": "",
            "markdown": "未找到商品，请尝试更换关键词。",
        }

    data_id = save_search_result(products, query, channel)
    markdown = format_product_list(products)

    return {
        "products": products,
        "data_id": data_id,
        "markdown": markdown,
    }


def _product_to_dict(p: Product) -> dict:
    """将 Product 转为可 JSON 序列化的 dict"""
    d = {"id": p.id, "title": p.title, "price": p.price}
    if p.stats:
        d["stats"] = p.stats
    return d


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="1688 商品搜索")
    parser.add_argument("--query", "-q", required=True, help="搜索关键词（自然语言描述）")
    parser.add_argument("--channel", "-c", default="douyin",
                        choices=["douyin", "taobao", "pinduoduo", "xiaohongshu"],
                        help="下游渠道 (默认: douyin，taobao 自动映射)")
    args = parser.parse_args()

    try:
        result = search_and_save(args.query, args.channel)
        output = {
            "data_id": result["data_id"],
            "product_count": len(result["products"]),
            "products": [_product_to_dict(p) for p in result["products"]],
            "markdown": result["markdown"],
        }
    except Exception as e:
        output = {
            "data_id": "",
            "product_count": 0,
            "products": [],
            "markdown": f"搜索失败（网络异常，已重试3次）：{e}",
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))
