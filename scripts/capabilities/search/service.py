#!/usr/bin/env python3
"""选品服务 — 商品搜索、结果保存、格式化"""

import json
import os
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from _http import api_post
from _const import CHANNEL_MAP, SEARCH_LIMIT, DATA_DIR
from _errors import ServiceError
from _output import fmt_rate


@dataclass
class Product:
    """商品信息"""
    id: str
    title: str
    price: str
    image: str
    url: str
    stats: Optional[Dict[str, Any]] = None


def search_products(query: str, channel: str = "") -> List[Product]:
    """
    搜索商品

    Args:
        query:   搜索关键词（自然语言描述）
        channel: 下游渠道英文名（见 CHANNEL_MAP），留空不限

    Returns:
        Product 列表

    Raises:
        ValueError: 渠道名不合法
        SkillError 子类: API 调用失败
    """
    if channel and channel not in CHANNEL_MAP:
        supported = ', '.join(k for k in CHANNEL_MAP
                              if not any('\u4e00' <= c <= '\u9fff' for c in k))
        raise ValueError(f"不支持的渠道: {channel}，支持: {supported}")

    api_channel = CHANNEL_MAP.get(channel, "")
    model = api_post("/1688claw/skill/searchoffer",
                     {"query": query, "channel": api_channel})

    data = model.get("data", {})
    if not isinstance(data, dict):
        raise ServiceError("搜索结果格式异常，请稍后重试")

    products = []
    for i, (item_id, item) in enumerate(data.items()):
        if i >= SEARCH_LIMIT:
            break
        products.append(Product(
            id=item_id,
            title=item.get("title") or "未知商品",
            price=str(item.get("price") or "-"),
            image=item.get("image") or "",
            url=f"https://detail.1688.com/offer/{item_id}.html",
            stats=item.get("stats"),
        ))
    return products


def save_search_result(products: List[Product], query: str, channel: str) -> str:
    """保存搜索结果到文件，返回 data_id"""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    data_id = now.strftime("%Y%m%d_%H%M%S") + f"_{now.microsecond // 1000:03d}"
    filepath = os.path.join(DATA_DIR, f"1688_{data_id}.json")

    products_map = {}
    for p in products:
        entry = {"title": p.title, "price": p.price, "image": p.image}
        if p.stats:
            entry["stats"] = p.stats
        products_map[p.id] = entry

    payload = {
        "query": query,
        "channel": channel,
        "timestamp": datetime.now().isoformat(),
        "data_id": data_id,
        "products": products_map,
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return data_id


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
        good = fmt_rate(s.get("goodRates"))
        repurchase = fmt_rate(s.get("repurchaseRate"))
        downstream = s.get("downstreamOffer", "-") if s.get("downstreamOffer") is not None else "-"
        collection = fmt_rate(s.get("collectionRate24h"))
        title = p.title.replace("|", "\\|")
        lines.append(
            f"| {i} | [{title}]({p.url}) | ¥{p.price} "
            f"| {sales} | {good} | {repurchase} | {downstream} | {collection} |"
        )

    if len(products) > max_show:
        lines.append(f"\n*... 还有 {len(products) - max_show} 个商品，完整数据见 JSON 输出*")

    return "\n".join(lines)


def search_and_save(query: str, channel: str = "") -> dict:
    """搜索并保存，返回 {products, data_id, markdown}"""
    products = search_products(query, channel)

    if not products:
        return {"products": [], "data_id": "", "markdown": "未找到商品，请尝试更换关键词。"}

    data_id = save_search_result(products, query, channel)
    markdown = format_product_list(products)

    return {"products": products, "data_id": data_id, "markdown": markdown}


def product_to_dict(p: Product) -> dict:
    """将 Product 转为可 JSON 序列化的 dict"""
    d = {"id": p.id, "title": p.title, "price": p.price, "url": p.url}
    if p.stats:
        d["stats"] = p.stats
    return d
