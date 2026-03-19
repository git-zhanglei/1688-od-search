#!/usr/bin/env python3
"""店铺经营日报 — 服务层"""

import json
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional

from _const import SEARCH_DATA_DIR
from _errors import ServiceError
from _http import api_post
from capabilities.opportunities.service import fetch_opportunities
from capabilities.search.service import search_products
from capabilities.shops.service import check_shop_status
from capabilities.trend.service import fetch_trend

CHANNEL_LABELS = {
    "pinduoduo": "拼多多",
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "taobao": "淘宝",
    "thyny": "淘宝",
}

CHANNEL_ALIASES = {
    "拼多多": "pinduoduo",
    "pdd": "pinduoduo",
    "pinduoduo": "pinduoduo",
    "淘宝": "taobao",
    "taobao": "taobao",
    "thyny": "taobao",
    "抖音": "douyin",
    "douyin": "douyin",
    "小红书": "xiaohongshu",
    "xiaohongshu": "xiaohongshu",
    "xhs": "xiaohongshu",
}

CHANNEL_KEYS = ["channel", "channel_name", "platform", "name"]
GMV_DAY_KEYS = ["gmv_1", "gmv1", "yesterday_gmv", "day_gmv", "店铺GMV"]
GMV_7D_KEYS = ["gmv_7", "gmv7", "seven_day_gmv", "week_gmv"]
GMV_KEYS = GMV_DAY_KEYS + GMV_7D_KEYS + ["gmv", "trade_gmv", "pay_gmv", "amount", "value"]
QTY_DAY_KEYS = ["qty_1", "qty1", "active_qty_1", "active_item_count_1", "昨日动销商品数"]
QTY_7D_KEYS = ["qty_7", "qty7", "active_qty_7", "active_item_count_7", "近7日动销商品数"]
DOD_KEYS = [
    "gmv_dod_pct",
    "dod_pct",
    "day_on_day",
    "day_pct",
    "dod",
    "daily_growth",
]
WOW_KEYS = [
    "gmv_wow_pct",
    "wow_pct",
    "week_on_week",
    "week_pct",
    "wow",
    "weekly_growth",
]

CATEGORY_KEYS = [
    "low_sales_category",
    "lowSaleCategory",
    "lowest_sales_category",
    "lowestSaleCategory",
    "category",
    "category_name",
    "cateName",
]
QUERY_KEYS = [
    "opportunity_queries",
    "query_list",
    "queries",
    "keywords",
    "keyword_list",
    "hot_queries",
    "opportunity_keywords",
]
TREND_KEYS = [
    "search_heat_trend",
    "searchTrend",
    "trend",
    "trend_pct",
    "heat_trend",
]
COMPETITION_KEYS = ["competition", "competition_level", "competition_degree", "competeLevel"]
PRICE_KEYS = [
    "price_band_opportunity",
    "price_band",
    "price_range",
    "priceOpportunity",
    "price_opportunity",
]

CHANNEL_PROFILES = {
    "pinduoduo": "价格敏感、偏爆款与高性价比商品",
    "taobao": "搜索需求稳定、适合标准化类目长期承接",
    "douyin": "内容驱动强、适合场景化和短视频演示型商品",
    "xiaohongshu": "种草心智强、适合颜值化和生活方式表达型商品",
}

QUERY_HINTS = {
    "pinduoduo": ["家用", "大容量", "平价", "宿舍", "实用", "组合", "收纳箱", "置物架"],
    "taobao": ["收纳", "分类", "分层", "家居", "多层", "桌面", "厨房", "衣柜"],
    "douyin": ["神器", "爆款", "创意", "可视", "桌面", "改造", "便携", "场景"],
    "xiaohongshu": ["桌面", "化妆品", "颜值", "极简", "ins", "高级感", "宿舍", "卧室"],
}

PLATFORM_LABELS = {
    "1688": "1688",
    "taobao": "淘宝",
    "xiaohongshu": "小红书",
}

PLATFORM_BONUS = {
    "pinduoduo": {"1688": 6, "taobao": 2},
    "douyin": {"xiaohongshu": 4, "1688": 3, "taobao": 1},
    "xiaohongshu": {"xiaohongshu": 6, "taobao": 2, "1688": 1},
    "taobao": {"taobao": 6, "1688": 2},
}

USER_HIDDEN_TEXTS = {"", "-", "--", "暂无", "暂无关键词", "暂无趋势数据", "待确认"}
TREND_FOCUS_LIMIT = 5


def _non_empty(value: Any) -> bool:
    return value not in (None, "", [], {})


def _pick(data: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in data and _non_empty(data[key]):
            return data[key]
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value in (None, "", "-", "--"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        cleaned = cleaned.replace("元", "").replace("%", "")
        cleaned = cleaned.replace("＋", "+").replace("－", "-")
        match = re.search(r"[-+]?\d+(?:\.\d+)?", cleaned)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
    return None


def _normalize_percent(value: Any) -> Optional[float]:
    if value is None:
        return None
    raw = value.strip() if isinstance(value, str) else value
    number = _safe_float(raw)
    if number is None:
        return None
    if isinstance(raw, str) and "%" in raw:
        return number
    if -1 <= number <= 1:
        return number * 100
    return number


def _fmt_currency(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:,.0f}元"


def _fmt_percent(value: Optional[float]) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def _fmt_ratio_percent(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}%"


def _fmt_count(value: Optional[float]) -> str:
    if value is None:
        return "-"
    normalized = int(round(value))
    return str(normalized)


def _normalize_channel(value: Any) -> str:
    if value is None:
        return ""
    key = str(value).strip().lower()
    return CHANNEL_ALIASES.get(key, CHANNEL_ALIASES.get(str(value).strip(), key))


def _channel_label(channel: str) -> str:
    if not channel:
        return "未知渠道"
    return CHANNEL_LABELS.get(channel, CHANNEL_LABELS.get(CHANNEL_ALIASES.get(channel, ""), channel))


def _normalize_channel_record(data: Dict[str, Any], hinted_channel: str = "") -> Optional[Dict[str, Any]]:
    channel_raw = _pick(data, CHANNEL_KEYS) or hinted_channel
    channel = _normalize_channel(channel_raw)
    gmv_day = _safe_float(_pick(data, GMV_DAY_KEYS))
    gmv_7d = _safe_float(_pick(data, GMV_7D_KEYS))
    gmv = _safe_float(_pick(data, GMV_KEYS))
    if gmv is None:
        gmv = gmv_day if gmv_day is not None else gmv_7d
    dod = _normalize_percent(_pick(data, DOD_KEYS))
    wow = _normalize_percent(_pick(data, WOW_KEYS))
    qty_day = _safe_float(_pick(data, QTY_DAY_KEYS))
    qty_7d = _safe_float(_pick(data, QTY_7D_KEYS))

    if not channel or gmv is None:
        return None

    return {
        "channel": channel,
        "channel_label": _channel_label(channel),
        "gmv": gmv,
        "gmv_1": gmv_day,
        "gmv_7": gmv_7d,
        "qty_1": qty_day,
        "qty_7": qty_7d,
        "gmv_dod_pct": dod,
        "gmv_wow_pct": wow,
        "_score": sum(v is not None for v in [gmv, gmv_day, gmv_7d, qty_day, qty_7d, dod, wow]),
    }


def _collect_channel_records(node: Any, hinted_channel: str = "", bucket: Optional[List[Dict[str, Any]]] = None):
    if bucket is None:
        bucket = []

    if isinstance(node, dict):
        record = _normalize_channel_record(node, hinted_channel)
        if record:
            bucket.append(record)

        for key, value in node.items():
            next_hint = _normalize_channel(key)
            if next_hint not in CHANNEL_LABELS:
                next_hint = ""
            _collect_channel_records(value, next_hint, bucket)
    elif isinstance(node, list):
        for item in node:
            _collect_channel_records(item, hinted_channel, bucket)

    return bucket


def _dedupe_channels(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}
    for record in records:
        existing = best.get(record["channel"])
        if existing is None or record["_score"] > existing["_score"]:
            best[record["channel"]] = record

    return sorted(best.values(), key=lambda item: item["gmv"], reverse=True)


def _normalize_queries(value: Any) -> List[str]:
    items: List[str] = []

    if isinstance(value, str):
        items = [part.strip() for part in re.split(r"[、,，;；\n]+", value) if part.strip()]
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                items.append(item.strip())
            elif isinstance(item, dict):
                query = _pick(item, ["query", "keyword", "topic", "name"])
                if isinstance(query, str) and query.strip():
                    items.append(query.strip())

    deduped: List[str] = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _normalize_trend(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    pct = _normalize_percent(value)
    if pct is not None:
        arrow = "↑" if pct > 0 else ("↓" if pct < 0 else "→")
        return f"{arrow} {abs(pct):.1f}%"
    return "暂无趋势数据"


def _stringify(value: Any, fallback: str = "暂无") -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        if parts:
            return "、".join(parts)
    return fallback


def _is_user_visible(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in USER_HIDDEN_TEXTS
    if isinstance(value, list):
        return any(_is_user_visible(item) for item in value)
    return True


def _visible_string(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
        return text if _is_user_visible(text) else ""
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        items = [str(item).strip() for item in value if _is_user_visible(item)]
        return "、".join(items)
    return str(value).strip() if _is_user_visible(value) else ""


def _append_visible_line(lines: List[str], label: str, value: Any):
    text = _visible_string(value)
    if text:
        lines.append(f"- {label}：{text}")


def _split_seed_terms(values: List[str]) -> List[str]:
    seeds: List[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        for part in re.split(r"[、,，;；/]+", value):
            text = part.strip()
            if len(text) >= 2 and text not in seeds:
                seeds.append(text)
    return seeds


def _normalize_match_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def _seed_match_score(text: str, seeds: List[str]) -> float:
    normalized_text = _normalize_match_text(text)
    if not normalized_text:
        return 0.0

    best = 0.0
    for seed in seeds:
        normalized_seed = _normalize_match_text(seed)
        if not normalized_seed:
            continue
        if normalized_text == normalized_seed:
            return 120.0
        if normalized_seed in normalized_text or normalized_text in normalized_seed:
            best = max(best, 88.0 + min(len(normalized_seed), 6))
            continue

        overlap = len(set(normalized_seed) & set(normalized_text))
        ratio = SequenceMatcher(None, normalized_seed, normalized_text).ratio()
        best = max(best, ratio * 42.0 + min(overlap, 5) * 7.0)

    return best


def _clean_markdown_text(text: str) -> str:
    cleaned = text.replace("**", "").replace("### ", "").replace("#### ", "")
    cleaned = cleaned.replace("→", "").replace("📊", "").replace("🔺", "").replace("🔻", "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    deduped: List[str] = []
    for item in items:
        value = item.strip()
        if value and value not in deduped:
            deduped.append(value)
    return deduped


def _extract_text_sections(text: str) -> List[str]:
    section_pattern = re.compile(
        r"####\s*([^\n]+?)\s*\n((?:(?!\n####|\n###|\Z).|\n)*)",
        re.MULTILINE,
    )
    return [match.group(0).strip() for match in section_pattern.finditer(text)]


def _extract_query_candidates_from_text(text: str) -> List[str]:
    numbered = re.findall(r"\d+\.\s+\*\*([^*]+)\*\*", text)
    if numbered:
        return _dedupe_preserve_order(numbered)

    plain = re.findall(r"\d+\.\s+([^\n]+)", text)
    return _dedupe_preserve_order(plain)


def _extract_price_band_from_text(text: str) -> str:
    table_rows = re.findall(r"\|\s*¥?([^|]+?)\s*\|\s*(\d+)\s*\|\s*([\d.]+%)\s*\|", text)
    parsed_rows = []
    for price_range, count, _share in table_rows:
        price_range = price_range.strip()
        if not re.search(r"\d", price_range):
            continue
        parsed_rows.append((price_range, int(count)))

    if parsed_rows:
        dominant_range = max(parsed_rows, key=lambda item: item[1])[0]
        normalized_range = dominant_range.replace("¥", "").strip()
        match = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", normalized_range)
        if match:
            return f"¥{match.group(1)}-¥{match.group(2)}"
        return dominant_range.replace(" ¥", "¥").replace(" - ", "-")

    return "待确认"


def _extract_trend_from_text(text: str) -> str:
    parts: List[str] = []

    yoy_match = re.search(r"\*\*年同比增长\*\*：([^\n]+)", text)
    if yoy_match:
        parts.append(_clean_markdown_text(f"年同比增长：{yoy_match.group(1)}"))

    recent_section = re.search(r"####\s*6\.\s*近期动向（最近3个月）\s*\n((?:(?!\n###|\Z).|\n)*)", text)
    if recent_section:
        recent_lines = [line.strip("- ").strip() for line in recent_section.group(1).splitlines() if line.strip()]
        cleaned_lines = [_clean_markdown_text(line) for line in recent_lines[:2]]
        parts.extend(line for line in cleaned_lines if line)

    peak_match = re.search(r"-\s*(\d{6}):\s*[\d,.]+\s*←.*?峰值", text)
    trough_match = re.search(r"-\s*(\d{6}):\s*[\d,.]+\s*←.*?谷底", text)
    if peak_match and trough_match:
        parts.append(f"峰值在 {peak_match.group(1)}，谷底在 {trough_match.group(1)}")

    if not parts:
        return "暂无趋势数据"

    return "；".join(_dedupe_preserve_order(parts))[:200]


def _extract_competition_from_text(text: str) -> str:
    hints: List[str] = []

    supply_match = re.search(r"\*\*供需关系\*\*：([^\n]+)", text)
    if supply_match:
        supply_text = _clean_markdown_text(supply_match.group(1))
        if supply_text:
            hints.append(supply_text)

    if "竞争格局开放" in text:
        hints.append("竞争格局开放")

    if "流量分布相对分散" in text:
        hints.append("流量分布相对分散")

    if not hints:
        return "待确认"

    return "；".join(_dedupe_preserve_order(hints))[:160]


def _extract_category_from_text(text: str) -> str:
    for pattern in [r"\*\*原始查询\*\*：([^\n]+)", r"\*\*查询关键词\*\*：([^\n]+)"]:
        match = re.search(pattern, text)
        if match:
            value = _clean_markdown_text(match.group(1))
            if value:
                return value
    return "待确认"


def _extract_opportunity_from_text_block(text: str) -> Dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return {}

    queries = _extract_query_candidates_from_text(text)
    category = _extract_category_from_text(text)
    trend = _extract_trend_from_text(text)
    competition = _extract_competition_from_text(text)
    price_band = _extract_price_band_from_text(text)

    if not queries and category == "待确认" and trend == "暂无趋势数据" and competition == "待确认":
        return {}

    return {
        "category": category,
        "queries": queries,
        "trend": trend,
        "competition": competition,
        "price_band": price_band,
        "raw": {
            "source": "text_output",
            "output": text,
            "sections": _extract_text_sections(text),
        },
    }


def _extract_opportunity_from_text_outputs(biz_data: Dict[str, Any]) -> Dict[str, Any]:
    candidate_texts: List[str] = []
    low_sales_data = biz_data.get("低销量类目商机数据")

    if isinstance(low_sales_data, list):
        for item in low_sales_data:
            if isinstance(item, dict) and isinstance(item.get("output"), str):
                candidate_texts.append(item["output"])

    for text in candidate_texts:
        extracted = _extract_opportunity_from_text_block(text)
        if extracted:
            return extracted

    return {}


def _normalize_product_items(value: Any) -> List[str]:
    items: List[str] = []

    if isinstance(value, str) and value.strip():
        items.append(value.strip())
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                items.append(item.strip())
                continue
            if isinstance(item, dict):
                name = _pick(item, ["title", "name", "product_name", "offer_name", "keyword", "query"])
                if isinstance(name, str) and name.strip():
                    items.append(name.strip())

    return _dedupe_list(items)


def _extract_product_overview(biz_data: Dict[str, Any]) -> Dict[str, Any]:
    active_products = _normalize_product_items(
        biz_data.get("昨日动销商品")
        or biz_data.get("昨日动销")
        or biz_data.get("动销商品")
    )
    main_products = _normalize_product_items(
        biz_data.get("主营商品")
        or biz_data.get("主营商品列表")
        or biz_data.get("主推商品")
    )

    return {
        "active_products": active_products,
        "yesterday_active_products": active_products,
        "main_products": main_products,
        "seed_queries": _dedupe_list(active_products + main_products),
    }


def _opportunity_from_product_overview(product_overview: Dict[str, Any]) -> Dict[str, Any]:
    seed_queries = product_overview.get("seed_queries", [])
    if not seed_queries:
        return {}

    lead_product = seed_queries[0]
    return {
        "category": lead_product or "主营商品盘",
        "queries": seed_queries[:4],
        "trend": "基于动销商品与主营商品生成",
        "competition": "待确认",
        "price_band": "待确认",
        "raw": {
            "source": "shop_daily_product_lists",
            "active_products": product_overview.get("active_products", []),
            "main_products": product_overview.get("main_products", []),
        },
    }


def _candidate_score(data: Dict[str, Any]) -> int:
    score = 0
    if _pick(data, CATEGORY_KEYS):
        score += 3
    if _normalize_queries(_pick(data, QUERY_KEYS)):
        score += 3
    if _pick(data, TREND_KEYS):
        score += 1
    if _pick(data, COMPETITION_KEYS):
        score += 1
    if _pick(data, PRICE_KEYS):
        score += 1
    return score


def _collect_opportunity_candidates(node: Any, bucket: Optional[List[Dict[str, Any]]] = None):
    if bucket is None:
        bucket = []

    if isinstance(node, dict):
        if _candidate_score(node) >= 4:
            bucket.append(node)
        for value in node.values():
            _collect_opportunity_candidates(value, bucket)
    elif isinstance(node, list):
        for item in node:
            _collect_opportunity_candidates(item, bucket)

    return bucket


def _extract_opportunity(biz_data: Dict[str, Any]) -> Dict[str, Any]:
    candidates = _collect_opportunity_candidates(biz_data)
    selected = max(candidates, key=_candidate_score) if candidates else {}

    queries = _normalize_queries(_pick(selected, QUERY_KEYS))
    category = _stringify(_pick(selected, CATEGORY_KEYS), "待确认")
    trend = _normalize_trend(_pick(selected, TREND_KEYS))
    competition = _stringify(_pick(selected, COMPETITION_KEYS), "待确认")
    price_band = _stringify(_pick(selected, PRICE_KEYS), "待确认")

    if not selected:
        text_output_extracted = _extract_opportunity_from_text_outputs(biz_data)
        if text_output_extracted:
            return text_output_extracted
        product_overview = _extract_product_overview(biz_data)
        product_derived = _opportunity_from_product_overview(product_overview)
        if product_derived:
            return product_derived
        return {
            "category": "待确认",
            "queries": [],
            "trend": "暂无趋势数据",
            "competition": "待确认",
            "price_band": "待确认",
            "raw": {},
        }

    return {
        "category": category,
        "queries": queries,
        "trend": trend,
        "competition": competition,
        "price_band": price_band,
        "raw": selected,
    }


def _health_score(row: Dict[str, Any]) -> int:
    share_pct = row.get("share", 0) * 100
    dod = row.get("gmv_dod_pct") or 0
    wow = row.get("gmv_wow_pct") or 0

    score = 45 + min(share_pct, 60) * 0.45
    score += max(min(dod, 40), -40) * 0.35
    score += max(min(wow, 40), -40) * 0.25
    return max(0, min(int(round(score)), 100))


def _health_label(score: int) -> str:
    if score >= 80:
        return "强势"
    if score >= 65:
        return "稳健"
    if score >= 50:
        return "观察"
    return "预警"


def _build_channel_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_gmv = sum(item["gmv"] for item in rows)
    total_qty_1 = sum(item.get("qty_1") or 0 for item in rows)
    total_qty_7 = sum(item.get("qty_7") or 0 for item in rows)
    enriched: List[Dict[str, Any]] = []
    for row in rows:
        share = (row["gmv"] / total_gmv) if total_gmv else 0
        enriched_row = dict(row)
        enriched_row["share"] = share
        enriched_row["health_score"] = _health_score(enriched_row)
        enriched_row["health_label"] = _health_label(enriched_row["health_score"])
        enriched.append(enriched_row)

    dominant = max(enriched, key=lambda item: item["gmv"], default=None)
    has_growth_metrics = any(
        item.get("gmv_dod_pct") is not None or item.get("gmv_wow_pct") is not None for item in enriched
    )
    fastest = (
        max(
            enriched,
            key=lambda item: (
                item.get("gmv_dod_pct") if item.get("gmv_dod_pct") is not None else float("-inf")
            ),
            default=None,
        )
        if has_growth_metrics
        else None
    )
    risky = [
        item
        for item in enriched
        if (item.get("gmv_dod_pct") or 0) < 0 or (item.get("gmv_wow_pct") or 0) < 0
    ]
    risky.sort(
        key=lambda item: ((item.get("gmv_dod_pct") or 0) + (item.get("gmv_wow_pct") or 0))
    )

    has_qty_1 = any(item.get("qty_1") is not None for item in enriched)
    top_active = (
        max(
            enriched,
            key=lambda item: item.get("qty_1") if item.get("qty_1") is not None else float("-inf"),
            default=None,
        )
        if has_qty_1
        else None
    )

    concentration = (dominant["share"] * 100) if dominant else 0
    if concentration >= 60:
        structure = "高度依赖单一渠道"
    elif concentration >= 40:
        structure = "头部渠道集中度偏高"
    else:
        structure = "渠道结构相对均衡"

    return {
        "rows": enriched,
        "total_gmv": total_gmv,
        "total_qty_1": total_qty_1,
        "total_qty_7": total_qty_7,
        "dominant": dominant,
        "fastest": fastest,
        "top_active": top_active,
        "risky": risky,
        "structure": structure,
        "concentration_pct": concentration,
    }


def _build_growth_quality(summary: Dict[str, Any]) -> str:
    rows = summary["rows"]
    if not any(item.get("gmv_dod_pct") is not None or item.get("gmv_wow_pct") is not None for item in rows):
        return "建议先结合动销商品与主营商品判断选品方向，再用 Query 级点击和转化表现验证承接能力。"
    divergent = [
        item
        for item in rows
        if item.get("gmv_dod_pct") is not None
        and item.get("gmv_wow_pct") is not None
        and item["gmv_dod_pct"] * item["gmv_wow_pct"] < 0
    ]
    strong = [
        item
        for item in rows
        if (item.get("gmv_dod_pct") or 0) > 0 and (item.get("gmv_wow_pct") or 0) > 0
    ]

    if divergent:
        channel_names = "、".join(item["channel_label"] for item in divergent)
        return (
            f"{channel_names} 的增长信号出现分化，建议优先复盘流量来源、商品匹配度和转化链路。"
        )

    if strong:
        channel_names = "、".join(item["channel_label"] for item in strong[:2])
        return f"{channel_names} 的增长信号更稳定，可优先承接新增选品测试。"

    return "当前增长更像结构迁移而非全面走强，建议优先排查流量波动和承接效率。"


def _build_risk_warning(summary: Dict[str, Any]) -> str:
    if not any(item.get("gmv_dod_pct") is not None or item.get("gmv_wow_pct") is not None for item in summary["rows"]):
        return "建议优先观察动销商品清单与核心 Query 的承接表现，及时替换弱转化商品。"
    risky = summary["risky"]
    if not risky:
        return "主要渠道暂未出现明显下滑风险，可将精力放在优化高潜力类目测试效率。"

    top = risky[0]
    return (
        f"{top['channel_label']} 需重点警惕，建议收缩低转化商品并重新匹配更适合该渠道的切入词。"
    )


def _extract_price_text(price_band: str) -> str:
    match = re.search(r"(\d+(?:\.\d+)?)\s*[-~至]\s*(\d+(?:\.\d+)?)", price_band)
    if match:
        low = match.group(1)
        high = match.group(2)
        return f"{low}-{high}元"
    return price_band if price_band != "待确认" else "待确认"


def _default_queries(category: str) -> List[str]:
    if not category or category == "待确认":
        return ["潜力新品", "高转化长尾词", "场景化爆款词"]
    return [
        f"{category} 平价爆款",
        f"{category} 桌面收纳",
        f"{category} 家用大容量",
    ]


def _query_score_for_channel(query: str, channel: str, row: Dict[str, Any]) -> float:
    hints = QUERY_HINTS.get(channel, [])
    hint_score = sum(1 for hint in hints if hint in query)
    perf_score = (row.get("share", 0) * 100) * 0.1 + max(row.get("gmv_dod_pct") or 0, 0) * 0.05
    return hint_score + perf_score


def _build_query_recommendations(summary: Dict[str, Any], opportunity: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = summary["rows"] or []
    queries = opportunity["queries"] or _default_queries(opportunity["category"])
    price_text = _extract_price_text(opportunity["price_band"])
    product_list_mode = (
        isinstance(opportunity.get("raw"), dict)
        and opportunity["raw"].get("source") == "shop_daily_product_lists"
    )
    live_market_mode = opportunity.get("source") == "opportunities_live_match"

    if not rows:
        rows = [
            {"channel": "taobao", "channel_label": "淘宝", "share": 0, "gmv_dod_pct": 0},
            {"channel": "douyin", "channel_label": "抖音", "share": 0, "gmv_dod_pct": 0},
            {"channel": "xiaohongshu", "channel_label": "小红书", "share": 0, "gmv_dod_pct": 0},
            {"channel": "pinduoduo", "channel_label": "拼多多", "share": 0, "gmv_dod_pct": 0},
        ]

    recommendations: List[Dict[str, Any]] = []
    max_queries = 1 if live_market_mode else 4
    for index, query in enumerate(queries[:max_queries]):
        best_row = max(rows, key=lambda row: _query_score_for_channel(query, row["channel"], row))
        priority = "P0" if index == 0 else ("P1" if index < 3 else "P2")
        if product_list_mode:
            reason = (
                f"{best_row['channel_label']} 当前承接能力较强，且“{query}”与该渠道的"
                f"{CHANNEL_PROFILES.get(best_row['channel'], '用户需求')}更匹配；"
                "结合动销商品与主营商品信号，适合优先测试。"
            )
        elif live_market_mode:
            topic_text = opportunity.get("matched_topic") or query
            signal_text = _visible_string(opportunity.get("trend"))
            signal_suffix = f"，当前商机信号 {signal_text}" if signal_text else ""
            reason = (
                f"“{topic_text}”与{best_row['channel_label']}当前承接人群更匹配，"
                f"先用“{query}”做单词测款更稳妥{signal_suffix}。"
            )
        else:
            market_context = []
            if _is_user_visible(opportunity.get("trend")):
                market_context.append(opportunity["trend"])
            if _is_user_visible(opportunity.get("competition")):
                market_context.append(f"{opportunity['competition']}竞争环境")
            market_text = "与".join(market_context) if market_context else "实时商机信号"
            reason = (
                f"{best_row['channel_label']} 当前承接能力较强，且“{query}”与该渠道的"
                f"{CHANNEL_PROFILES.get(best_row['channel'], '用户需求')}更匹配；"
                f"结合{market_text}，适合优先测试。"
            )
        recommendations.append(
            {
                "query": query,
                "channel": best_row["channel"],
                "channel_label": best_row["channel_label"],
                "reason": reason,
                "price": price_text,
                "priority": priority,
            }
        )

    return recommendations


def _build_channel_match(summary: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> List[str]:
    rec_by_channel = {item["channel"]: item for item in recommendations}
    lines: List[str] = []
    for row in sorted(summary["rows"], key=lambda item: item["gmv"], reverse=True):
        rec = rec_by_channel.get(row["channel"])
        if rec:
            query = rec["query"]
        else:
            candidate_queries = [item["query"] for item in recommendations] or ["高转化长尾词"]
            query = max(
                candidate_queries,
                key=lambda item: _query_score_for_channel(item, row["channel"], row),
            )
        lines.append(
            f"- {row['channel_label']}：渠道匹配度较高，"
            f"优先测试“{query}”，原因是该渠道{CHANNEL_PROFILES.get(row['channel'], '需求相对明确')}。"
        )
    return lines or ["- 暂无渠道数据，建议先围绕动销商品与主营商品整理首批测试 Query。"]


def _build_short_actions(summary: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> List[str]:
    dominant = summary["dominant"]
    risky = summary["risky"][0] if summary["risky"] else None
    top_queries = "、".join(item["query"] for item in recommendations[:2]) or "核心长尾词"

    actions = [
        f"- 围绕 {top_queries} 在主力渠道做 2-3 组快速测款，重点看点击率、成交转化率和加购率。",
    ]
    if dominant:
        actions.append(
            f"- 先在 {dominant['channel_label']} 放量验证，复用该渠道已有的人群与内容素材，缩短试错周期。"
        )
    if risky:
        actions.append(
            f"- 对 {risky['channel_label']} 下滑商品做清单复盘，优先替换低转化 SKU 与弱曝光词。"
        )
    return actions


def _build_mid_actions(summary: Dict[str, Any], opportunity: Dict[str, Any]) -> List[str]:
    structure = summary["structure"]
    price_band = _visible_string(opportunity.get("price_band"))
    category = _visible_string(opportunity.get("matched_topic")) or _visible_string(opportunity.get("category")) or "核心类目"
    return [
        (
            f"- 围绕“{category}”建立渠道分层货盘，按价格带 {price_band} 拆分基础款、利润款和引流款。"
            if price_band
            else f"- 围绕“{category}”建立渠道分层货盘，先拆出引流款、利润款和内容测款三层结构。"
        ),
        f"- 根据“{structure}”现状优化渠道结构，将新增测试预算向高增长渠道倾斜，同时保留搜索型渠道做稳定承接。",
        "- 建立周度复盘机制，跟踪 Query 级点击、转化、ROI 和动销率，保留跑赢基线的词包做规模化运营。",
    ]


def _build_exec_summary(summary: Dict[str, Any], opportunity: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> str:
    first_query = recommendations[0]["query"] if recommendations else "核心长尾词"
    focus_topic = _visible_string(opportunity.get("matched_topic")) or _visible_string(opportunity.get("category")) or "主营商品"
    summary_text = (
        f"建议围绕“{focus_topic}”相关商品做小步快跑验证，优先测试“{first_query}”等 Query，"
        "再按点击、转化和加购表现放大高匹配渠道。"
    )
    return summary_text[:200]


def _escape_md_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|")


def _extract_candidate_growth_rows(candidate: Dict[str, Any]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    raw = candidate.get("raw", {})
    content_list = raw.get("content", []) if isinstance(raw, dict) else []
    for item in content_list:
        if not isinstance(item, dict):
            continue
        query = _stringify(item.get("searchWord") or item.get("title"), "")
        detail = _clean_markdown_text(_stringify(item.get("text"), ""))
        if not query and not detail:
            continue
        growth_match = re.findall(r"(\d+(?:\.\d+)?)\s*%", detail)
        growth_pct = f"{growth_match[0]}%" if growth_match else "-"
        rows.append(
            {
                "query": query or "待确认词",
                "growth_pct": growth_pct,
                "detail": detail,
            }
        )
    return rows


def _ranked_market_candidates(opportunity: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = opportunity.get("raw", {}) if isinstance(opportunity.get("raw"), dict) else {}
    ranked = raw.get("ranked_candidates", []) if isinstance(raw, dict) else []
    candidates: List[Dict[str, Any]] = []
    seen = set()

    def _append_candidate(candidate: Dict[str, Any]):
        topic = _stringify(candidate.get("topic"), "")
        query_key = tuple(_dedupe_list(candidate.get("search_words", []) or []))
        key = (topic, candidate.get("platform", ""), query_key)
        if key in seen:
            return
        seen.add(key)
        candidates.append(candidate)

    if isinstance(ranked, list):
        for item in ranked:
            if isinstance(item, dict):
                _append_candidate(item)

    matched = raw.get("matched_opportunity") if isinstance(raw, dict) else None
    if isinstance(matched, dict):
        _append_candidate(matched)

    if not candidates:
        fallback_candidate = {
            "platform": opportunity.get("matched_platform", ""),
            "platform_label": opportunity.get("matched_platform_label", ""),
            "rank": "",
            "topic": opportunity.get("matched_topic") or opportunity.get("category") or "核心商机",
            "search_words": _dedupe_list(opportunity.get("queries", []) or []),
            "signal": opportunity.get("trend", ""),
            "text": "",
            "raw": {},
        }
        _append_candidate(fallback_candidate)

    return candidates[:2]


def _preferred_channels_from_summary(summary: Dict[str, Any]) -> List[str]:
    channels = [item.get("channel", "") for item in summary.get("rows", []) if item.get("channel")]
    return _dedupe_list(channels)


def _choose_search_channel(
    candidate: Dict[str, Any],
    recommendations: List[Dict[str, Any]],
    preferred_channels: List[str],
) -> str:
    candidate_queries = _dedupe_list(candidate.get("search_words", []) or [])
    for query in candidate_queries:
        for recommendation in recommendations:
            if recommendation.get("query") == query and recommendation.get("channel"):
                return recommendation["channel"]
    if preferred_channels:
        return preferred_channels[0]
    platform = _normalize_channel(candidate.get("platform"))
    if platform in {"pinduoduo", "douyin", "taobao", "xiaohongshu"}:
        return platform
    return ""


def _search_recommended_products(query: str, channel: str, max_items: int = 4) -> List[Dict[str, Any]]:
    if not query:
        return []

    products = []
    tried_channels = _dedupe_list([channel, ""])
    for current_channel in tried_channels:
        try:
            products = search_products(query, current_channel)
        except Exception:
            products = []
        if products:
            break

    rows: List[Dict[str, Any]] = []
    for product in products[:max_items]:
        stats = product.stats if isinstance(product.stats, dict) else {}
        rows.append(
            {
                "title": product.title,
                "price": product.price,
                "url": product.url,
                "sales": stats.get("last30DaysSales") if stats.get("last30DaysSales") is not None else "-",
                "category": stats.get("categoryName") or "-",
            }
        )
    return rows


def _build_deep_opportunities(
    opportunity: Dict[str, Any],
    recommendations: List[Dict[str, Any]],
    preferred_channels: List[str],
) -> List[Dict[str, Any]]:
    deep_items: List[Dict[str, Any]] = []
    for candidate in _ranked_market_candidates(opportunity):
        query_list = _dedupe_list(candidate.get("search_words", []) or opportunity.get("queries", []) or [])
        primary_query = query_list[0] if query_list else ""
        search_channel = _choose_search_channel(candidate, recommendations, preferred_channels)
        products = _search_recommended_products(primary_query, search_channel)
        deep_items.append(
            {
                "topic": _stringify(candidate.get("topic"), _stringify(opportunity.get("matched_topic"), "核心商机")),
                "platform": candidate.get("platform", "") or opportunity.get("matched_platform", ""),
                "platform_label": candidate.get("platform_label", "") or opportunity.get("matched_platform_label", ""),
                "rank": candidate.get("rank", ""),
                "signal": _stringify(candidate.get("signal"), _stringify(opportunity.get("trend"), "")),
                "primary_query": primary_query,
                "queries": query_list,
                "growth_rows": _extract_candidate_growth_rows(candidate),
                "products": products,
                "search_channel": search_channel,
                "search_channel_label": _channel_label(search_channel) if search_channel else "全渠道",
            }
        )
    return deep_items[:2]


def _extract_trend_section_terms(text: str, section_title: str, limit: int = 2) -> List[str]:
    pattern = rf"####\s*{re.escape(section_title)}（\d+\s*条）\n((?:(?!\n#### |\n### |\Z).|\n)*)"
    match = re.search(pattern, text)
    if not match:
        return []
    body = match.group(1)
    terms = re.findall(r"\d+\.\s+\*\*([^*]+)\*\*", body)
    return _dedupe_list([_clean_markdown_text(term) for term in terms])[:limit]


def _extract_trend_recent_motion(text: str) -> str:
    pattern = r"####\s*\d+\.\s*近期动向（最近3个月）\s*\n\n(?:-[^\n]*\n)?-\s*([^\n]+)"
    match = re.search(pattern, text)
    if not match:
        return ""
    return _clean_markdown_text(match.group(1))


def _extract_trend_number(text: str, pattern: str) -> Optional[float]:
    match = re.search(pattern, text)
    if not match:
        return None
    return _safe_float(match.group(1))


def _extract_trend_text(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    if not match:
        return ""
    return _clean_markdown_text(match.group(1))


def _normalize_trend_query(product: str) -> str:
    cleaned = _stringify(product, "").replace("其他", "").strip()
    if not cleaned:
        return ""

    candidates: List[str] = []
    for part in re.split(r"[、,，;；/]+", cleaned):
        value = part.strip()
        value = re.sub(r"(用品|用具|产品|商品)$", "", value)
        if len(value) >= 2:
            candidates.append(value)

    candidates = _dedupe_list(candidates)
    for candidate in candidates:
        if 2 <= len(candidate) <= 5:
            return candidate
    return candidates[0] if candidates else ""


def _pick_trend_focus_products(main_products: List[str], deep_opportunities: List[Dict[str, Any]], limit: int = TREND_FOCUS_LIMIT) -> List[str]:
    ranked: List[Dict[str, Any]] = []
    for index, product in enumerate(main_products):
        seeds: List[str] = []
        for item in deep_opportunities:
            seeds.extend([item.get("topic", ""), item.get("primary_query", "")])
            seeds.extend(item.get("queries", []) or [])
        score = _seed_match_score(product, _dedupe_list(seeds))
        ranked.append({"product": product, "score": score, "index": index})

    ranked.sort(key=lambda item: (-item["score"], item["index"]))
    selected = [item["product"] for item in ranked[:limit]]
    selected_set = set(selected)

    if len(selected) < limit:
        for product in main_products:
            if product not in selected_set:
                selected.append(product)
                selected_set.add(product)
            if len(selected) >= limit:
                break
    return selected[:limit]


def _build_trend_market_assessment(trend_info: Dict[str, Any]) -> str:
    scale_label = trend_info.get("scale_label") or "类目"
    supply_ratio = trend_info.get("supply_ratio")
    yoy = trend_info.get("yoy")
    recent_motion = trend_info.get("recent_motion") or ""

    parts = [scale_label]
    if supply_ratio is not None:
        if supply_ratio >= 1:
            parts.append(f"供需比{supply_ratio:.2f}，承接还可以")
        else:
            parts.append(f"供需比{supply_ratio:.2f}，供给偏多")
    if yoy is not None:
        parts.append(f"年同比{yoy:+.1f}%")
    if recent_motion:
        parts.append(recent_motion)
    return "；".join(parts[:3])


def _build_trend_user_suggestion(trend_info: Dict[str, Any], deep_opportunities: List[Dict[str, Any]]) -> str:
    supply_ratio = trend_info.get("supply_ratio")
    yoy = trend_info.get("yoy")
    median_price = trend_info.get("median_price")
    blue_ocean_terms = trend_info.get("blue_ocean_terms", [])
    growth_terms = trend_info.get("growth_terms", [])
    pick_terms = blue_ocean_terms or growth_terms

    if pick_terms:
        query_text = " / ".join(pick_terms[:2])
        if median_price is not None:
            return f"优先试“{query_text}”，定价先贴近¥{int(round(median_price))}中位带，更容易测出承接。"
        return f"优先试“{query_text}”，先做细分词小批量测试，不要一上来铺大路货。"

    if supply_ratio is not None and supply_ratio < 0.8 and yoy is not None and yoy <= -15:
        return "先保留基础款，不建议重投；除非有明显差异化场景或更强的价格优势。"

    if supply_ratio is not None and supply_ratio >= 1:
        query_hint = ""
        if deep_opportunities:
            query_hint = deep_opportunities[0].get("primary_query", "")
        if query_hint:
            return f"可以围绕“{query_hint}”延展近似款，优先做同人群、同场景的小范围测试。"
        return "可以继续保留并做细分词测试，先验证点击和转化后再扩大。"

    return "先小批量试词试图，跑出正反馈后再追加预算，不要平均分配资源。"


def _fetch_trend_matrix_row(product: str, query: str, deep_opportunities: List[Dict[str, Any]]) -> Dict[str, str]:
    if not query:
        return {
            "product": product,
            "assessment": "未拿到趋势数据",
            "suggestion": "当前主营商品没有匹配到可用趋势词，先保留基础供给，后续再补趋势验证。",
        }

    try:
        result = fetch_trend(query=query, timeout=10)
    except Exception:
        return {
            "product": product,
            "assessment": "未拿到趋势数据",
            "suggestion": "先保留基础供给，后续再补趋势验证，不建议当前重投。",
        }

    raw_text = result.get("data")
    text = raw_text if isinstance(raw_text, str) else _stringify(raw_text, "")
    scale_line = _extract_trend_text(text, r"\*\*市场规模\*\*：([^\n]+)")
    scale_label = ""
    if "→" in scale_line:
        scale_label = scale_line.split("→", 1)[1].strip()
    supply_ratio = _extract_trend_number(text, r"\*\*供需关系\*\*：供需比\s*([-\d.]+)")
    yoy = _extract_trend_number(text, r"\*\*年同比增长\*\*：([-\d.]+)")
    avg_price = _extract_trend_number(text, r"\*\*均价\*\*：¥?([-\d.]+)")
    median_price = _extract_trend_number(text, r"\*\*中位数价格\*\*：¥?([-\d.]+)")
    trend_info = {
        "scale_label": scale_label or scale_line,
        "supply_ratio": supply_ratio,
        "yoy": yoy,
        "avg_price": avg_price,
        "median_price": median_price,
        "recent_motion": _extract_trend_recent_motion(text),
        "blue_ocean_terms": _extract_trend_section_terms(text, "蓝海商机"),
        "growth_terms": _extract_trend_section_terms(text, "增长迅速"),
    }
    return {
        "product": product,
        "assessment": _build_trend_market_assessment(trend_info),
        "suggestion": _build_trend_user_suggestion(trend_info, deep_opportunities),
    }


def _build_main_product_matrix(main_products: List[str], deep_opportunities: List[Dict[str, Any]]) -> List[str]:
    focus_products = _pick_trend_focus_products(main_products, deep_opportunities, TREND_FOCUS_LIMIT)
    lines = ["", "### 主营商品矩阵", "| 品类 | 市场评估 | 用户建议 |", "| --- | --- | --- |"]
    for product in focus_products:
        trend_query = _normalize_trend_query(product)
        insight = _fetch_trend_matrix_row(product, trend_query, deep_opportunities)
        lines.append(
            f"| {_escape_md_cell(product)} | {_escape_md_cell(insight['assessment'])} | {_escape_md_cell(insight['suggestion'])} |"
        )
    return lines


def _seeded_variant(options: List[str], seed_text: str, salt: int = 0) -> str:
    if not options:
        return ""
    total = sum((index + 1 + salt) * ord(char) for index, char in enumerate(seed_text))
    return options[total % len(options)]


def _build_no_active_products_message(main_products: List[str], deep_opportunities: List[Dict[str, Any]]) -> str:
    focus_topic = ""
    focus_query = ""
    if deep_opportunities:
        focus_topic = _visible_string(deep_opportunities[0].get("topic"))
        focus_query = _visible_string(deep_opportunities[0].get("primary_query"))

    focus_product = _visible_string(main_products[0]) if main_products else ""
    seed_parts = _dedupe_list([focus_product, focus_topic, focus_query] + main_products[:3])
    seed_text = "|".join(seed_parts) or "shop_daily_no_active_products"

    openings = [
        "最近店里的商品还没有跑出动销",
        "这段时间你的商品暂时还没迎来动销",
        "近期商品这边还没有看到动销起色",
        "最近这批商品暂时还没跑出成交节奏",
        "这一阵店铺商品还没有开始动销",
    ]
    reassurances = [
        "先别急",
        "先不用焦虑",
        "也别灰心",
        "别先急着下判断",
        "这个阶段先稳住节奏就好",
    ]
    bridges = [
        "我已经顺着你现在的商品盘筛了几条更容易先出单的商机",
        "已经结合你当前主营方向挑了几条更值得先测的商机",
        "先帮你把更有机会起量的商机方向拎出来了",
        "下面给你留的是更容易承接流量的商机方向",
        "我先替你筛了一轮更有机会跑出首单的商机",
    ]
    focus_clauses = [
        f"，可以优先围绕“{focus_topic}”去试" if focus_topic else "",
        f"，先从“{focus_query}”这类词切进去更顺手" if focus_query else "",
        f"，先把“{focus_product}”相关款打磨扎实会更容易接住流量" if focus_product else "",
        "",
    ]

    opening = _seeded_variant(openings, seed_text, salt=3)
    reassurance = _seeded_variant(reassurances, seed_text, salt=11)
    bridge = _seeded_variant(bridges, seed_text, salt=19)
    focus_clause = _seeded_variant(focus_clauses, seed_text, salt=29)
    return f"{opening}，{reassurance}，{bridge}{focus_clause}。"


def _build_active_products_section(active_products: List[str], main_products: List[str], deep_opportunities: List[Dict[str, Any]]) -> List[str]:
    if not active_products:
        return [
            "## 第一部分：店铺经营状态",
            "",
            "### 动销情况",
            _build_no_active_products_message(main_products, deep_opportunities),
        ]

    lines = ["## 第一部分：店铺经营状态", "", "### 动销情况", "| 序号 | 动销商品 |", "| --- | --- |"]
    for index, product in enumerate(active_products, 1):
        lines.append(f"| {index} | {_escape_md_cell(product)} |")
    return lines


def _build_opportunity_detail_section(item: Dict[str, Any], index: int) -> List[str]:
    lines = [f"### 商机 {index}：{item['topic']}", "| 指标 | 数值 |", "| --- | --- |"]
    lines.append(f"| 来源平台 | {item['platform_label'] or '-'} |")
    lines.append(f"| 市场热度 | {item['signal'] or '-'} |")
    lines.append(f"| 排名 | {item['rank'] or '-'} |")
    lines.append(f"| 推荐切入词 | {item['primary_query'] or '-'} |")
    lines.append(f"| 推荐搜品渠道 | {item['search_channel_label']} |")

    growth_rows = item.get("growth_rows", [])
    if growth_rows:
        lines.extend(["", "| 搜索词 | 搜索增速 | 机会说明 |", "| --- | --- | --- |"])
        for row in growth_rows[:3]:
            detail = _escape_md_cell(row["detail"])
            lines.append(f"| {_escape_md_cell(row['query'])} | {row['growth_pct']} | {detail} |")

    products = item.get("products", [])
    if products:
        lines.extend(["", "| 推荐商品 | 价格 | 30天销量 | 类目 |", "| --- | --- | --- | --- |"])
        for product in products:
            title = _escape_md_cell(product["title"])
            lines.append(
                f"| [{title}]({product['url']}) | ¥{product['price']} | {product['sales']} | {_escape_md_cell(product['category'])} |"
            )

    return lines


def _build_shop_daily_report_markdown(
    summary: Dict[str, Any],
    opportunity: Dict[str, Any],
    product_overview: Optional[Dict[str, Any]] = None,
    recommendations: Optional[List[Dict[str, Any]]] = None,
) -> str:
    product_overview = product_overview or {}
    recommendations = recommendations or []
    active_products = product_overview.get("active_products", []) or product_overview.get("yesterday_active_products", [])
    main_products = product_overview.get("main_products", [])
    preferred_channels = _preferred_channels_from_summary(summary)
    deep_opportunities = _build_deep_opportunities(opportunity, recommendations, preferred_channels)

    lines = _build_active_products_section(active_products, main_products, deep_opportunities)
    lines.extend(_build_main_product_matrix(main_products, deep_opportunities))
    lines.extend(["", "## 第二部分：精选商机深度洞察"])
    for index, item in enumerate(deep_opportunities, 1):
        lines.append("")
        lines.extend(_build_opportunity_detail_section(item, index))

    return "\n".join(lines)


def _analysis_channel_code(channel: str) -> str:
    return "thyny" if channel == "taobao" else channel


def _build_snapshot_markdown(
    summary: Dict[str, Any],
    opportunity: Dict[str, Any],
    product_overview: Optional[Dict[str, Any]] = None,
) -> str:
    product_overview = product_overview or {}
    lines: List[str] = ["## 店铺经营日报数据快照"]
    active_products = product_overview.get("active_products", []) or product_overview.get("yesterday_active_products", [])
    main_products = product_overview.get("main_products", [])

    lines.append("\n### 店铺分析")
    _append_visible_line(lines, "动销商品", active_products[:8])
    _append_visible_line(lines, "重点主营商品", opportunity.get("category"))
    _append_visible_line(lines, "主营商品", main_products[:6])

    matched_topic = _visible_string(opportunity.get("matched_topic"))
    primary_query = _visible_string((opportunity.get("queries") or [""])[0])
    matched_platform = _visible_string(opportunity.get("matched_platform_label"))
    trend_signal = _visible_string(opportunity.get("trend"))
    price_band = _visible_string(opportunity.get("price_band"))

    if matched_topic or primary_query:
        lines.append("\n### 核心商机")
        _append_visible_line(lines, "商机话题", matched_topic)
        _append_visible_line(lines, "来源平台", matched_platform)
        _append_visible_line(lines, "先测 Query", primary_query)
        _append_visible_line(lines, "热度信号", trend_signal)
        _append_visible_line(lines, "参考价格带", price_band)

    lines.append("\n### 结构化摘要")
    lines.append(f"- 动销商品数：{len(active_products)}")
    lines.append(f"- 主营商品数：{len(main_products)}")
    if matched_topic:
        lines.append(f"- 核心方向：{matched_topic}")
    elif _is_user_visible(opportunity.get("category")):
        lines.append(f"- 核心方向：{_visible_string(opportunity.get('category'))}")
    lines.append(f"- 渠道结构判断：{summary['structure']}")
    lines.append("\n说明：以上内容是接口数据整理快照。最终面向用户的经营日报，需要基于 `data.analysis_payload` 按 shop_daily 分析提示词生成。")

    return "\n".join(lines)


def _build_analysis_payload(
    summary: Dict[str, Any],
    opportunity: Dict[str, Any],
    product_overview: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    product_overview = product_overview or {}
    active_products = product_overview.get("active_products", []) or product_overview.get("yesterday_active_products", [])
    main_products = product_overview.get("main_products", [])
    store_input = {
        "active_products": active_products,
        "main_products": main_products,
    }
    opportunity_input = {
        "main_product": opportunity.get("category", ""),
        "main_products": main_products or opportunity.get("queries", []),
        "market_topic": opportunity.get("matched_topic", ""),
        "market_query": (opportunity.get("queries") or [""])[0],
        "market_platform": opportunity.get("matched_platform_label", ""),
        "product_signal": opportunity.get("trend", ""),
        "competition": opportunity.get("competition", ""),
        "price_band": opportunity.get("price_band", ""),
    }
    derived_metrics = {
        "analysis_mode": "product_snapshot",
        "active_product_count": len(active_products),
        "main_product_count": len(main_products),
        "structure": summary["structure"],
        "active_products": active_products,
        "main_products": main_products,
        "market_topic": opportunity.get("matched_topic", ""),
        "market_platform": opportunity.get("matched_platform_label", ""),
    }

    return {
        "input": store_input,
        "oppo": opportunity_input,
        "derived_metrics": derived_metrics,
        "input_text": json.dumps(store_input, ensure_ascii=False, indent=2),
        "oppo_text": json.dumps(opportunity_input, ensure_ascii=False, indent=2),
    }


def _dedupe_list(values: List[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        if isinstance(value, str) and value.strip() and value not in result:
            result.append(value.strip())
    return result


def _normalize_dict_payload(value: Any, capability_name: str) -> Dict[str, Any]:
    if value is None:
        raise ServiceError(f"{capability_name}接口返回为空")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ServiceError(f"{capability_name}返回结构异常：{exc}") from exc
    if not isinstance(value, dict):
        raise ServiceError(f"{capability_name}返回结构异常")
    return value


def _parse_volume(value: Any) -> float:
    if value in (None, "", "-", "--"):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("+", "")
    if text.startswith("<"):
        text = text[1:]
    multiplier = 10000 if "万" in text else 1
    text = text.replace("万", "")
    number = _safe_float(text)
    return (number or 0.0) * multiplier


def _fmt_price_value(value: float) -> str:
    normalized = round(value, 2)
    if abs(normalized - int(normalized)) < 0.01:
        return str(int(normalized))
    return f"{normalized:.2f}".rstrip("0").rstrip(".")


def _load_latest_search_snapshot() -> Dict[str, Any]:
    data_dir = Path(SEARCH_DATA_DIR)
    if not data_dir.is_dir():
        return {}

    for path in sorted(data_dir.glob("1688_*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payload["_snapshot_file"] = str(path)
            return payload
    return {}


def _build_user_context() -> Dict[str, Any]:
    snapshot = _load_latest_search_snapshot()
    products = snapshot.get("products", {}) if isinstance(snapshot.get("products"), dict) else {}

    prices: List[float] = []
    category_counts: Dict[str, int] = {}
    top_products: List[Dict[str, Any]] = []

    for product in products.values():
        if not isinstance(product, dict):
            continue
        price = _safe_float(product.get("price"))
        if price is not None:
            prices.append(price)

        stats = product.get("stats", {})
        if isinstance(stats, dict):
            category = str(stats.get("categoryName") or "").strip()
            if category:
                category_counts[category] = category_counts.get(category, 0) + 1
            sales = _parse_volume(stats.get("last30DaysSales"))
        else:
            sales = 0.0

        top_products.append(
            {
                "title": _stringify(product.get("title"), "未知商品"),
                "price": product.get("price") or "-",
                "sales": sales,
            }
        )

    top_products.sort(key=lambda item: item["sales"], reverse=True)
    category = max(category_counts.items(), key=lambda item: item[1])[0] if category_counts else ""
    latest_channel = _normalize_channel(snapshot.get("channel"))
    latest_query = _stringify(snapshot.get("query"), "")

    try:
        shop_status = check_shop_status()
        bound_shops = [
            {
                "code": shop.code,
                "name": shop.name,
                "channel": _normalize_channel(shop.channel),
                "channel_label": _channel_label(_normalize_channel(shop.channel)),
                "is_authorized": shop.is_authorized,
            }
            for shop in shop_status.get("valid", [])
        ]
    except Exception:
        bound_shops = []

    preferred_channels = _dedupe_list(
        [shop["channel"] for shop in bound_shops if shop.get("channel")] + ([latest_channel] if latest_channel else [])
    )

    price_band = "待确认"
    if prices:
        price_band = f"{_fmt_price_value(min(prices))}-{_fmt_price_value(max(prices))}元"

    return {
        "bound_shops": bound_shops,
        "preferred_channels": preferred_channels,
        "latest_search": {
            "query": latest_query,
            "channel": latest_channel,
            "channel_label": _channel_label(latest_channel) if latest_channel else "",
            "category": category or latest_query or "待确认",
            "price_band": price_band,
            "product_count": len(products),
            "data_id": snapshot.get("data_id") or "",
            "snapshot_file": snapshot.get("_snapshot_file") or "",
            "top_titles": [item["title"] for item in top_products[:3]],
        },
    }


def _flatten_opportunity_candidates(opportunities_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for platform, pdata in opportunities_data.items():
        if not isinstance(pdata, dict):
            continue
        for kind in ("trend", "hot"):
            section = pdata.get(kind)
            if not isinstance(section, dict):
                continue

            counts: Dict[str, str] = {}
            graphic = section.get("graphic", {})
            if isinstance(graphic, dict):
                for item in graphic.get("list", []) or []:
                    if isinstance(item, dict) and item.get("topic"):
                        counts[str(item.get("topic"))] = _stringify(item.get("count"), "")

            for item in section.get("detail", []) or []:
                if not isinstance(item, dict):
                    continue
                search_words: List[str] = []
                texts: List[str] = []
                for content in item.get("content", []) or []:
                    if not isinstance(content, dict):
                        continue
                    word = content.get("searchWord") or content.get("title")
                    if isinstance(word, str) and word.strip():
                        search_words.append(word.strip())
                    text = content.get("text")
                    if isinstance(text, str) and text.strip():
                        texts.append(text.strip())

                topic = _stringify(item.get("topic"), "待确认")
                candidates.append(
                    {
                        "platform": str(platform),
                        "platform_label": PLATFORM_LABELS.get(str(platform), str(platform)),
                        "kind": kind,
                        "rank": int(item.get("rank") or 999),
                        "topic": topic,
                        "search_words": _dedupe_list(search_words),
                        "signal": counts.get(topic, ""),
                        "text": " ".join(texts),
                        "raw": item,
                    }
                )
    return candidates


def _build_shop_daily_seed_context(
    summary: Dict[str, Any],
    opportunity: Dict[str, Any],
    product_overview: Dict[str, Any],
) -> Dict[str, Any]:
    preferred_channels = _dedupe_list(
        [row["channel"] for row in summary.get("rows", []) if row.get("channel")]
    )
    seeds = _split_seed_terms(
        [opportunity.get("category", "")]
        + list(opportunity.get("queries", []) or [])
        + list(product_overview.get("main_products", []) or [])
        + list(product_overview.get("active_products", []) or product_overview.get("yesterday_active_products", []) or [])
    )
    return {"preferred_channels": preferred_channels, "seeds": seeds[:16]}


def _shop_daily_opportunity_score(candidate: Dict[str, Any], seed_context: Dict[str, Any]) -> float:
    seeds = seed_context.get("seeds", [])
    if not seeds:
        return 0.0

    topic_score = _seed_match_score(candidate.get("topic", ""), seeds) * 1.2
    query_score = max(
        (_seed_match_score(word, seeds) for word in candidate.get("search_words", []) or []),
        default=0.0,
    )
    text_score = _seed_match_score(candidate.get("text", ""), seeds) * 0.25

    score = max(topic_score, query_score) + text_score
    for channel in seed_context.get("preferred_channels", []):
        score += PLATFORM_BONUS.get(channel, {}).get(candidate.get("platform", ""), 0)

    if candidate.get("kind") == "trend":
        score += 2.0
    score += max(0, 8 - min(int(candidate.get("rank") or 999), 8))
    return score


def _pick_precise_query(candidate: Dict[str, Any], seeds: List[str], fallback_queries: List[str]) -> str:
    queries = _dedupe_list(candidate.get("search_words", []) or []) or _dedupe_list(fallback_queries)
    if not queries:
        return ""
    return max(queries, key=lambda item: _seed_match_score(item, seeds))


def _enrich_opportunity_with_live_market(
    summary: Dict[str, Any],
    product_overview: Dict[str, Any],
    opportunity: Dict[str, Any],
    timeout: int = 12,
) -> Dict[str, Any]:
    seed_context = _build_shop_daily_seed_context(summary, opportunity, product_overview)
    seeds = seed_context.get("seeds", [])
    if not seeds:
        return opportunity

    try:
        opportunities_result = fetch_opportunities(timeout=timeout)
        opportunities_data = opportunities_result.get("data", {}) if isinstance(opportunities_result, dict) else {}
    except Exception:
        return opportunity

    candidates = _flatten_opportunity_candidates(opportunities_data)
    if not candidates:
        return opportunity

    scored = [(candidate, _shop_daily_opportunity_score(candidate, seed_context)) for candidate in candidates]
    ranked_candidates = [
        dict(candidate, score=round(score, 2))
        for candidate, score in sorted(scored, key=lambda item: item[1], reverse=True)
        if score > 0
    ][:2]
    best_candidate, best_score = max(scored, key=lambda item: item[1])
    if best_score < 42:
        return opportunity

    precise_query = _pick_precise_query(
        best_candidate,
        seeds,
        opportunity.get("queries", []) or product_overview.get("main_products", []),
    )

    enriched = dict(opportunity)
    enriched.update(
        {
            "queries": [precise_query] if precise_query else (opportunity.get("queries", []) or [])[:1],
            "trend": best_candidate.get("signal") or opportunity.get("trend", ""),
            "competition": _estimate_competition(best_candidate),
            "matched_platform": best_candidate.get("platform", ""),
            "matched_platform_label": best_candidate.get("platform_label", ""),
            "matched_topic": best_candidate.get("topic", ""),
            "source": "opportunities_live_match",
            "raw": {
                "source": "opportunities_live_match",
                "seed_context": seed_context,
                "matched_opportunity": best_candidate,
                "ranked_candidates": ranked_candidates,
            },
        }
    )

    if not _is_user_visible(enriched.get("category")):
        enriched["category"] = seeds[0]
    if not _is_user_visible(enriched.get("price_band")):
        enriched["price_band"] = ""
    return enriched


def _opportunity_match_score(candidate: Dict[str, Any], user_context: Dict[str, Any]) -> float:
    latest_search = user_context.get("latest_search", {})
    keywords = _dedupe_list(
        [
            _stringify(latest_search.get("query"), ""),
            _stringify(latest_search.get("category"), ""),
        ]
    )
    score = 0.0
    topic = candidate.get("topic", "")
    search_words = candidate.get("search_words", [])
    text = candidate.get("text", "")

    for keyword in keywords:
        if not keyword or keyword == "待确认":
            continue
        if keyword in topic or topic in keyword:
            score += 30
        if any(keyword in word or word in keyword for word in search_words):
            score += 18
        if keyword in text:
            score += 6

    for channel in user_context.get("preferred_channels", []):
        score += PLATFORM_BONUS.get(channel, {}).get(candidate.get("platform", ""), 0)

    if candidate.get("kind") == "trend":
        score += 3
    score += max(0, 10 - min(int(candidate.get("rank") or 999), 10))
    return score


def _estimate_competition(candidate: Dict[str, Any]) -> str:
    rank = int(candidate.get("rank") or 999)
    kind = candidate.get("kind")
    if kind == "hot" and rank <= 2:
        return "高"
    if rank <= 2:
        return "中高"
    if rank <= 5:
        return "中"
    return "中低"


def _fallback_opportunity_from_context(user_context: Dict[str, Any], opportunities_data: Dict[str, Any]) -> Dict[str, Any]:
    latest_search = user_context.get("latest_search", {})
    category = _stringify(latest_search.get("category"), "待确认")
    fallback = {
        "category": category,
        "queries": _default_queries(category),
        "trend": "基于用户搜索偏好回退生成",
        "competition": "待验证",
        "price_band": _stringify(latest_search.get("price_band"), "待确认"),
        "matched_platform": "",
        "matched_platform_label": "",
        "matched_topic": "",
        "source": "user_context",
        "raw": {},
    }

    candidates = _flatten_opportunity_candidates(opportunities_data)
    if not candidates:
        return fallback

    scored = [(candidate, _opportunity_match_score(candidate, user_context)) for candidate in candidates]
    ranked_candidates = [
        dict(candidate, score=round(score, 2))
        for candidate, score in sorted(scored, key=lambda item: item[1], reverse=True)
        if score > 0
    ][:2]
    best = max(scored, key=lambda item: item[1])[0]
    queries = _dedupe_list(best.get("search_words", []) + _default_queries(category))[:4]
    fallback.update(
        {
            "queries": queries,
            "trend": best.get("signal") or ("近1小时趋势走强" if best.get("kind") == "trend" else "近1小时热度靠前"),
            "competition": _estimate_competition(best),
            "matched_platform": best.get("platform", ""),
            "matched_platform_label": best.get("platform_label", ""),
            "matched_topic": best.get("topic", ""),
            "source": "opportunities_fallback",
            "raw": {
                "matched_opportunity": best,
                "ranked_candidates": ranked_candidates,
            },
        }
    )
    return fallback


def _choose_channel_for_query(query: str, preferred_channels: List[str]) -> str:
    channels = preferred_channels or ["pinduoduo"]
    best_channel = channels[0]
    best_score = float("-inf")
    for index, channel in enumerate(channels):
        score = sum(1 for hint in QUERY_HINTS.get(channel, []) if hint in query)
        score += len(channels) - index
        if score > best_score:
            best_channel = channel
            best_score = score
    return best_channel


def _build_fallback_recommendations(user_context: Dict[str, Any], opportunity: Dict[str, Any]) -> List[Dict[str, Any]]:
    latest_search = user_context.get("latest_search", {})
    preferred_channels = user_context.get("preferred_channels", [])
    queries = _dedupe_list((opportunity.get("queries") or []) + _default_queries(opportunity.get("category", "")))[:1]
    source_hint = opportunity.get("matched_topic") or _stringify(latest_search.get("query"), opportunity.get("category", ""))

    recommendations: List[Dict[str, Any]] = []
    for index, query in enumerate(queries):
        channel = _choose_channel_for_query(query, preferred_channels)
        priority = "P0" if index == 0 else ("P1" if index < 3 else "P2")
        recommendations.append(
            {
                "query": query,
                "channel": channel,
                "channel_label": _channel_label(channel),
                "reason": (
                    f"结合搜索记录“{_stringify(latest_search.get('query'), opportunity.get('category', '该类目'))}”"
                    f"与商机话题“{source_hint}”，该词更适合在{_channel_label(channel)}先做测款。"
                ),
                "price": opportunity.get("price_band", "待确认"),
                "priority": priority,
            }
        )
    return recommendations


def _build_fallback_analysis_payload(
    user_context: Dict[str, Any],
    opportunity: Dict[str, Any],
    recommendations: List[Dict[str, Any]],
    fallback_reason: str,
) -> Dict[str, Any]:
    input_payload = {
        "bound_shops": user_context.get("bound_shops", []),
        "latest_search": user_context.get("latest_search", {}),
        "preferred_channels": user_context.get("preferred_channels", []),
    }
    opportunity_payload = {
        "main_product": opportunity.get("category", ""),
        "main_products": opportunity.get("queries", []),
        "market_topic": opportunity.get("matched_topic", ""),
        "market_query": (opportunity.get("queries") or [""])[0],
        "product_signal": opportunity.get("trend", ""),
        "competition": opportunity.get("competition", ""),
        "price_band": opportunity.get("price_band", ""),
        "matched_platform": opportunity.get("matched_platform", ""),
        "matched_topic": opportunity.get("matched_topic", ""),
    }
    derived_metrics = {
        "analysis_mode": "opportunities_fallback",
        "missing_shop_daily_data": True,
        "fallback_reason": fallback_reason,
        "preferred_channels": user_context.get("preferred_channels", []),
        "recommended_queries": recommendations,
    }

    return {
        "mode": "opportunities_fallback",
        "input": input_payload,
        "oppo": opportunity_payload,
        "derived_metrics": derived_metrics,
        "input_text": json.dumps(input_payload, ensure_ascii=False, indent=2),
        "oppo_text": json.dumps(opportunity_payload, ensure_ascii=False, indent=2),
    }


def _build_fallback_snapshot_markdown(
    user_context: Dict[str, Any],
    opportunity: Dict[str, Any],
    recommendations: List[Dict[str, Any]],
) -> str:
    latest_search = user_context.get("latest_search", {})
    shops = user_context.get("bound_shops", [])
    preferred_channels = user_context.get("preferred_channels", [])
    primary_channel = preferred_channels[0] if preferred_channels else ""
    primary_channel_label = _channel_label(primary_channel) if primary_channel else "主渠道"
    category = _stringify(opportunity.get("category"), _stringify(latest_search.get("category"), "核心类目"))
    topic = _stringify(opportunity.get("matched_topic"), category)
    price_band = _visible_string(opportunity.get("price_band")) or _visible_string(latest_search.get("price_band"))
    trend = _visible_string(opportunity.get("trend")) or "热度走强"
    top_recommendation = recommendations[0] if recommendations else {}
    p0_query = _visible_string(top_recommendation.get("query"))

    lines: List[str] = ["## 选品策略日报"]
    lines.append("")
    intro = f"建议围绕 **{topic}** 做集中测款，优先在 **{primary_channel_label}** 承接。"
    if price_band:
        intro = f"{intro[:-1]}，主打价格带 **{price_band}**。"
    lines.append(intro)

    lines.append("\n### 策略摘要")
    lines.append(f"- 主推方向：{category}")
    lines.append(f"- 核心商机：{topic}")
    lines.append(f"- 建议优先渠道：{primary_channel_label}")
    lines.append(f"- 趋势信号：{trend}")
    _append_visible_line(lines, "建议价格带", price_band)
    _append_visible_line(lines, "P0 Query", p0_query)

    lines.append("\n### 渠道建议")
    if shops:
        shop_text = "、".join(f"{shop['name']}（{shop['channel_label']}）" for shop in shops)
        lines.append(f"- 已绑定店铺：{shop_text}")
    else:
        lines.append("- 已绑定店铺：未获取到可用店铺信息")
    lines.append(
        f"- 若继续走低价高频成交，优先在 **{primary_channel_label}** 测试收纳类标准品，主打高性价比与组合装。"
    )
    if latest_search.get("channel_label") and latest_search.get("channel_label") != primary_channel_label:
        lines.append(
            f"- 你的搜索记录里包含 **{latest_search.get('channel_label')}** 渠道的“{_stringify(latest_search.get('query'), category)}”，"
            "可以同步做内容测款，验证点击率和收藏率。"
        )
    lines.append(
        f"- 当前商机更适合从 **{topic}** 这个细分切入，先跑 2-4 个 Query，观察点击、转化和加购。"
    )
    if top_recommendation:
        lines.append("\n### 核心切入词")
        lines.append(f"- 推荐 Query：{top_recommendation['query']}")
        lines.append(f"- 目标渠道：{top_recommendation['channel_label']}")
        lines.append(f"- 推荐理由：{top_recommendation['reason']}")
        if _is_user_visible(top_recommendation.get("price")):
            lines.append(f"- 参考价格带：{top_recommendation['price']}")

    lines.append("\n### 执行建议")
    if price_band:
        lines.append(f"- 短期（1-2周）：先上新 P0 Query，单词测 2-3 个款，统一控制在 **{price_band}** 价格带。")
    else:
        lines.append("- 短期（1-2周）：先上新 P0 Query，单词测 2-3 个款，优先看点击率、转化率和加购率。")
    lines.append(
        f"- 中期（1个月）：把点击和转化稳定的 Query 扩成系列款，在 **{primary_channel_label}** 做店群铺量，"
        "同步补评价素材和场景图。"
    )
    lines.append(
        f"\n执行摘要：先围绕“{topic}”做选品测试，优先跑 {primary_channel_label} 渠道，"
        "用 P0 Query 快速筛出高点击、高转化款，再决定是否扩大铺货。"
    )
    return "\n".join(lines)


def _build_fallback_result(opportunities_timeout: int = 20, fallback_reason: str = "empty_bizdata_fallback") -> Dict[str, Any]:
    user_context = _build_user_context()
    try:
        opportunities_result = fetch_opportunities(timeout=opportunities_timeout)
        opportunities_data = opportunities_result.get("data", {}) if isinstance(opportunities_result, dict) else {}
    except Exception:
        opportunities_data = {}

    opportunity = _fallback_opportunity_from_context(user_context, opportunities_data)
    recommendations = _build_fallback_recommendations(user_context, opportunity)
    analysis_payload = _build_fallback_analysis_payload(user_context, opportunity, recommendations, fallback_reason)
    fallback_summary = {
        "rows": [
            {
                "channel": channel,
                "channel_label": _channel_label(channel),
            }
            for channel in user_context.get("preferred_channels", [])
        ],
    }
    fallback_product_overview = {
        "active_products": [],
        "yesterday_active_products": [],
        "main_products": [opportunity.get("category")] if _is_user_visible(opportunity.get("category")) else [],
    }
    markdown = _build_shop_daily_report_markdown(
        fallback_summary,
        opportunity,
        fallback_product_overview,
        recommendations,
    )

    dominant_channel = user_context.get("preferred_channels", [""])
    return {
        "markdown": markdown,
        "data": {
            "mode": "opportunities_fallback",
            "fallback_reason": fallback_reason,
            "raw": {},
            "channels": [],
            "opportunity": opportunity,
            "recommendations": recommendations,
            "analysis_payload": analysis_payload,
            "user_context": user_context,
            "summary": {
                "total_gmv": None,
                "structure": "基于搜索记录与实时商机生成的选品策略",
                "concentration_pct": 0,
                "dominant_channel": dominant_channel[0] if dominant_channel else "",
                "fastest_channel": "",
                "growth_quality_hint": "建议先用推荐 Query 小规模测款，优先看点击率、转化率和加购率的联动表现。",
                "risk_warning_hint": "避免一次性铺太多 SKU，先保留 2-4 个核心 Query 做精细化验证。",
                "exec_summary_hint": (
                    f"建议围绕“{opportunity.get('matched_topic') or opportunity.get('category', '核心类目')}”"
                    f"在 {_channel_label(dominant_channel[0]) if dominant_channel and dominant_channel[0] else '主渠道'} 先测试。"
                )[:200],
            },
        },
    }


def _fetch_shop_daily_model(timeout: int, retry_times: int = 3) -> Optional[Dict[str, Any]]:
    body = {"code": "shop_daily"}
    for attempt in range(retry_times):
        try:
            return api_post("/1688claw/skill/workflow", body, timeout=timeout)
        except ServiceError as exc:
            if exc.code != 500:
                raise
            if attempt < retry_times - 1:
                time.sleep(min(1 + attempt, 2))
                continue
            return None
    return None


def fetch_shop_daily(timeout: int = 25) -> Dict[str, Any]:
    """
    拉取店铺经营日报（使用 AK 签名）

    Returns:
        {"markdown": str, "data": dict}
    """
    model = _fetch_shop_daily_model(timeout=timeout)
    if model is None:
        return _build_fallback_result(
            opportunities_timeout=min(timeout, 20),
            fallback_reason="api_500_fallback",
        )

    biz_data = _normalize_dict_payload((model or {}).get("bizData"), "店铺经营日报")
    if not biz_data:
        return _build_fallback_result(
            opportunities_timeout=min(timeout, 20),
            fallback_reason="empty_bizdata_fallback",
        )

    channels = _dedupe_channels(_collect_channel_records(biz_data))
    summary = _build_channel_summary(channels)
    product_overview = _extract_product_overview(biz_data)
    opportunity = _extract_opportunity(biz_data)
    opportunity = _enrich_opportunity_with_live_market(
        summary,
        product_overview,
        opportunity,
        timeout=min(timeout, 12),
    )
    recommendations = _build_query_recommendations(summary, opportunity)
    analysis_payload = _build_analysis_payload(summary, opportunity, product_overview)
    markdown = _build_shop_daily_report_markdown(summary, opportunity, product_overview, recommendations)

    data = {
        "raw": biz_data,
        "channels": summary["rows"],
        "product_overview": product_overview,
        "opportunity": opportunity,
        "recommendations": recommendations,
        "analysis_payload": analysis_payload,
        "summary": {
            "total_gmv": summary["total_gmv"],
            "structure": summary["structure"],
            "concentration_pct": summary["concentration_pct"],
            "dominant_channel": dominant["channel"] if (dominant := summary["dominant"]) else "",
            "fastest_channel": fastest["channel"] if (fastest := summary["fastest"]) else "",
            "growth_quality_hint": _build_growth_quality(summary),
            "risk_warning_hint": _build_risk_warning(summary),
            "exec_summary_hint": _build_exec_summary(summary, opportunity, recommendations),
        },
    }
    return {"markdown": markdown, "data": data}
