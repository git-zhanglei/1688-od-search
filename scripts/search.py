#!/usr/bin/env python3
"""
选品模块 - 商品搜索和结果处理

Usage:
    python3 search.py --query "连衣裙" [--channel douyin]
"""

import argparse
import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Set, Tuple

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _api import search_products, Product
from _const import DATA_DIR, SEARCH_LIMIT


def save_search_result(products: List[Product], query: str, channel: str, meta: Optional[Dict] = None) -> str:
    """
    保存搜索结果到文件（含完整 stats）

    Returns:
        data_id (时间戳格式)
    """
    data_dir = DATA_DIR
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
    if meta:
        data["meta"] = meta

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data_id


def _fmt_rate(v):
    """小数转百分比，如 0.857 → 85.7%；无值返回 -"""
    if v is None:
        return "-"
    try:
        f = float(v)
        return f"{f * 100:.1f}%" if f <= 1.0 else f"{f:.1f}%"
    except (TypeError, ValueError):
        return str(v)


def format_product_list(products: List[Product], max_show: int = 20) -> str:
    """格式化商品列表为 Markdown 表格"""
    if not products:
        return "未找到符合条件的商品。"

    lines = [f"找到 **{len(products)}** 个商品：\n"]
    lines.append("| # | 商品 | 价格 | 30天销量 | 好评率 | 复购率 | 铺货数 | 揽收率 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")

    for i, p in enumerate(products[:max_show], 1):
        s = p.stats or {}
        sales = s.get("last30DaysSales", "-") if s.get("last30DaysSales") is not None else "-"
        good = _fmt_rate(s.get("goodRates"))
        repurchase = _fmt_rate(s.get("repurchaseRate"))
        downstream = s.get("downstreamOffer", "-") if s.get("downstreamOffer") is not None else "-"
        collection = _fmt_rate(s.get("collectionRate24h"))
        title = p.title.replace("|", "\\|")
        lines.append(f"| {i} | [{title}]({p.url}) | ¥{p.price} | {sales} | {good} | {repurchase} | {downstream} | {collection} |")

    if len(products) > max_show:
        lines.append(f"\n*... 还有 {len(products) - max_show} 个商品，完整数据见 JSON 输出*")

    return "\n".join(lines)


def detect_bulk_intent(query: str) -> Dict[str, Optional[int]]:
    """
    从自然语言 query 里识别“批量（>20）”意图。
    默认不触发，确保旧行为不变。
    """
    # 显式数量：如“铺50个”“找30款”
    number_patterns = [
        r"(?:搜|搜索|找|选|铺|铺货|上架|发布|来)\s*(\d{2,4})\s*(?:个|款|件|品|sku|SKU)",
        r"(\d{2,4})\s*(?:个|款|件|品)\s*(?:商品|货|sku|SKU)?",
    ]
    for pattern in number_patterns:
        m = re.search(pattern, query)
        if not m:
            continue
        count = int(m.group(1))
        if count > SEARCH_LIMIT:
            return {"auto_batch": True, "target_count": count, "reason": "explicit_number"}

    # 隐式批量语义：如“批量上架”“尽量多找一些”
    keyword_patterns = [
        "批量",
        "多铺",
        "多上架",
        "尽量多",
        "尽可能多",
        "多找一些",
        "多来点",
        "大量",
        "海量",
        "铺满",
    ]
    if any(k in query for k in keyword_patterns):
        return {"auto_batch": True, "target_count": SEARCH_LIMIT * 2, "reason": "bulk_keyword"}

    return {"auto_batch": False, "target_count": None, "reason": "default_single_batch"}


def _trim_redundant_tokens(text: str) -> str:
    """移除批量意图提示词，保留商品语义主干。"""
    patterns = [
        r"批量",
        r"多找一些",
        r"多来点",
        r"尽量多",
        r"尽可能多",
        r"大量",
        r"海量",
    ]
    cleaned = text
    for p in patterns:
        cleaned = re.sub(p, "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def build_query_variants(query: str) -> List[str]:
    """
    平衡扩量策略：保留原query优先，补充2个轻量变体。
    - 变体1：去批量修饰后的核心query
    - 变体2：在核心query后补充采购意图词（厂家批发）
    """
    variants: List[str] = []

    def add_variant(v: str):
        vv = re.sub(r"\s+", " ", v).strip()
        if vv and vv not in variants:
            variants.append(vv)

    add_variant(query)
    core_query = _trim_redundant_tokens(query)
    add_variant(core_query)
    if core_query:
        add_variant(f"{core_query} 厂家批发")

    # 平衡策略上限3个，控制相关性与请求量
    return variants[:3]


def search_products_best_effort(
    query: str,
    channel: str,
    target_count: int,
    max_rounds: int = 3,
) -> Tuple[List[Product], Dict[str, Any]]:
    """
    仅在批量意图下启用：多轮搜索 + 去重聚合（受接口限制，不保证一定达到目标数）。
    """
    merged: Dict[str, Product] = {}
    variants = build_query_variants(query)
    hit_variants: Set[str] = set()
    dedup_count = 0
    exhausted_without_growth = False
    no_growth_rounds = 0
    no_growth_round_threshold = 2

    for _ in range(max_rounds):
        growth_in_round = 0
        for variant in variants:
            current = search_products(variant, channel)
            if not current:
                continue
            for p in current:
                if p.id in merged:
                    dedup_count += 1
                    continue
                merged[p.id] = p
                hit_variants.add(variant)
                growth_in_round += 1
                if len(merged) >= target_count:
                    break
            if len(merged) >= target_count:
                break

        if len(merged) >= target_count:
            break
        if growth_in_round == 0:
            no_growth_rounds += 1
            if no_growth_rounds >= no_growth_round_threshold:
                exhausted_without_growth = True
                break
        else:
            no_growth_rounds = 0

    meta_debug = {
        "variant_count": len(variants),
        "hit_variants": list(hit_variants),
        "dedup_count": dedup_count,
        "exhausted_without_growth": exhausted_without_growth,
    }
    return list(merged.values()), meta_debug


def search_and_save(query: str, channel: str = "") -> dict:
    """
    搜索并保存结果

    Returns:
        {"products": List[Product], "data_id": str, "markdown": str}
    """
    intent = detect_bulk_intent(query)
    target_count = int(intent["target_count"] or SEARCH_LIMIT)
    debug_meta: Dict[str, Any] = {
        "variant_count": 1,
        "hit_variants": [],
        "dedup_count": 0,
        "exhausted_without_growth": False,
    }
    if intent["auto_batch"]:
        products, debug_meta = search_products_best_effort(query, channel, target_count=target_count)
    else:
        products = search_products(query, channel)

    if not products:
        return {
            "products": [],
            "data_id": "",
            "markdown": "未找到商品，请尝试更换关键词。",
        }

    meta = {
        "auto_batch_requested": bool(intent["auto_batch"]),
        "target_count": target_count if intent["auto_batch"] else None,
        "reason": intent["reason"],
        "variant_count": debug_meta["variant_count"] if intent["auto_batch"] else 1,
        "hit_variants": debug_meta["hit_variants"] if intent["auto_batch"] else [],
        "dedup_count": debug_meta["dedup_count"] if intent["auto_batch"] else 0,
        "exhausted_without_growth": debug_meta["exhausted_without_growth"] if intent["auto_batch"] else False,
    }
    data_id = save_search_result(products, query, channel, meta=meta)
    markdown = format_product_list(products)
    if intent["auto_batch"]:
        markdown += (
            "\n\n> 已启用批量意图模式："
            f"目标约 {target_count} 个；当前聚合到 {len(products)} 个。"
            "受搜索接口限制，可能无法稳定达到目标数量。"
        )

    return {
        "products": products,
        "data_id": data_id,
        "markdown": markdown,
        "meta": meta,
    }


def _product_to_dict(p: Product) -> dict:
    """将 Product 转为可 JSON 序列化的 dict"""
    d = {"id": p.id, "title": p.title, "price": p.price, "url": p.url}
    if p.stats:
        d["stats"] = p.stats
    return d


def main():
    import os
    if not os.environ.get("ALI_1688_AK"):
        print(json.dumps({
            "success": False,
            "markdown": "❌ AK 未配置，无法搜索商品。\n\n运行: `cli.py configure YOUR_AK`",
            "data": {"data_id": "", "product_count": 0, "products": []},
        }, ensure_ascii=False, indent=2))
        return

    parser = argparse.ArgumentParser(description="1688 商品搜索")
    parser.add_argument("--query", "-q", required=True, help="搜索关键词（自然语言描述）")
    parser.add_argument("--channel", "-c", default="",
                        choices=["", "douyin", "taobao", "pinduoduo", "xiaohongshu"],
                        help="下游渠道（可选；未识别渠道意图时留空）")
    args = parser.parse_args()

    try:
        result = search_and_save(args.query, args.channel)
        output = {
            "success": True,
            "markdown": result["markdown"],
            "data": {
                "data_id": result["data_id"],
                "product_count": len(result["products"]),
                "products": [_product_to_dict(p) for p in result["products"]],
                "meta": result.get("meta", {}),
            },
        }
    except Exception as e:
        output = {
            "success": False,
            "markdown": f"搜索失败（网络异常，已重试3次）：{e}",
            "data": {"data_id": "", "product_count": 0, "products": []},
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
