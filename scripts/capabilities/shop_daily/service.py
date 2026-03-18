#!/usr/bin/env python3
"""店铺经营日报 — 服务层"""

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from _const import DATA_DIR
from _errors import ServiceError
from _http import api_post
from capabilities.opportunities.service import fetch_opportunities
from capabilities.shops.service import check_shop_status

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
GMV_KEYS = ["gmv", "trade_gmv", "pay_gmv", "amount", "value"]
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
    gmv = _safe_float(_pick(data, GMV_KEYS))
    dod = _normalize_percent(_pick(data, DOD_KEYS))
    wow = _normalize_percent(_pick(data, WOW_KEYS))

    if not channel or gmv is None:
        return None

    return {
        "channel": channel,
        "channel_label": _channel_label(channel),
        "gmv": gmv,
        "gmv_dod_pct": dod,
        "gmv_wow_pct": wow,
        "_score": sum(v is not None for v in [gmv, dod, wow]),
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
    enriched: List[Dict[str, Any]] = []
    for row in rows:
        share = (row["gmv"] / total_gmv) if total_gmv else 0
        enriched_row = dict(row)
        enriched_row["share"] = share
        enriched_row["health_score"] = _health_score(enriched_row)
        enriched_row["health_label"] = _health_label(enriched_row["health_score"])
        enriched.append(enriched_row)

    dominant = max(enriched, key=lambda item: item["gmv"], default=None)
    fastest = max(
        enriched,
        key=lambda item: (
            item.get("gmv_dod_pct") if item.get("gmv_dod_pct") is not None else float("-inf")
        ),
        default=None,
    )
    risky = [
        item
        for item in enriched
        if (item.get("gmv_dod_pct") or 0) < 0 or (item.get("gmv_wow_pct") or 0) < 0
    ]
    risky.sort(
        key=lambda item: ((item.get("gmv_dod_pct") or 0) + (item.get("gmv_wow_pct") or 0))
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
        "dominant": dominant,
        "fastest": fastest,
        "risky": risky,
        "structure": structure,
        "concentration_pct": concentration,
    }


def _build_growth_quality(summary: Dict[str, Any]) -> str:
    rows = summary["rows"]
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
            f"{channel_names} 出现日环比与周同比背离，说明短期投放或活动对成交有拉动，"
            "但周维度需求基础仍需验证，建议复盘流量来源与转化链路。"
        )

    if strong:
        channel_names = "、".join(item["channel_label"] for item in strong[:2])
        return f"{channel_names} 同时保持日环比和周同比增长，增长质量较好，可优先承接新增选品测试。"

    return "当前增长更多来自结构迁移而非全面走强，建议优先排查流量波动和承接效率。"


def _build_risk_warning(summary: Dict[str, Any]) -> str:
    risky = summary["risky"]
    if not risky:
        return "主要渠道暂未出现明显下滑风险，可将精力放在优化高潜力类目测试效率。"

    top = risky[0]
    dod = _fmt_percent(top.get("gmv_dod_pct"))
    wow = _fmt_percent(top.get("gmv_wow_pct"))
    return (
        f"{top['channel_label']} 需重点警惕，当前日环比 {dod}、周同比 {wow}。"
        "若连续两周未恢复，建议收缩低转化商品并重新匹配更适合该渠道的切入词。"
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

    if not rows:
        rows = [
            {"channel": "taobao", "channel_label": "淘宝", "share": 0, "gmv_dod_pct": 0},
            {"channel": "douyin", "channel_label": "抖音", "share": 0, "gmv_dod_pct": 0},
            {"channel": "xiaohongshu", "channel_label": "小红书", "share": 0, "gmv_dod_pct": 0},
            {"channel": "pinduoduo", "channel_label": "拼多多", "share": 0, "gmv_dod_pct": 0},
        ]

    recommendations: List[Dict[str, Any]] = []
    for index, query in enumerate(queries[:4]):
        best_row = max(rows, key=lambda row: _query_score_for_channel(query, row["channel"], row))
        priority = "P0" if index == 0 else ("P1" if index < 3 else "P2")
        reason = (
            f"{best_row['channel_label']} 当前承接能力较强，且“{query}”与该渠道的"
            f"{CHANNEL_PROFILES.get(best_row['channel'], '用户需求')}更匹配；"
            f"结合{opportunity['trend']}与{opportunity['competition']}竞争环境，适合优先测试。"
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
            f"- {row['channel_label']}：GMV 占比 {_fmt_ratio_percent(row['share'] * 100)}，"
            f"优先测试“{query}”，原因是该渠道{CHANNEL_PROFILES.get(row['channel'], '需求相对明确')}。"
        )
    return lines or ["- 暂无渠道数据，建议先确认店铺已返回 GMV 明细。"]


def _build_short_actions(summary: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> List[str]:
    dominant = summary["dominant"]
    risky = summary["risky"][0] if summary["risky"] else None
    top_queries = "、".join(item["query"] for item in recommendations[:2]) or "核心长尾词"

    actions = [
        f"- 围绕 {top_queries} 在主力渠道做 2-3 组快速测款，重点看点击率、成交转化率和加购率。",
    ]
    if dominant:
        actions.append(
            f"- 先在 {dominant['channel_label']} 放量验证，复用高 GMV 渠道的人群与内容素材，缩短试错周期。"
        )
    if risky:
        actions.append(
            f"- 对 {risky['channel_label']} 下滑商品做清单复盘，优先替换近 7 天低转化 SKU 与弱曝光词。"
        )
    return actions


def _build_mid_actions(summary: Dict[str, Any], opportunity: Dict[str, Any]) -> List[str]:
    structure = summary["structure"]
    return [
        f"- 围绕“{opportunity['category']}”建立渠道分层货盘，按价格带 {opportunity['price_band']} 拆分基础款、利润款和引流款。",
        f"- 根据“{structure}”现状优化渠道结构，将新增测试预算向高增长渠道倾斜，同时保留搜索型渠道做稳定承接。",
        "- 建立周度复盘机制，跟踪 Query 级点击、转化、ROI 和动销率，保留跑赢基线的词包做规模化运营。",
    ]


def _build_exec_summary(summary: Dict[str, Any], opportunity: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> str:
    dominant = summary["dominant"]
    fastest = summary["fastest"]
    first_query = recommendations[0]["query"] if recommendations else "核心长尾词"
    parts = []
    if dominant:
        parts.append(f"{dominant['channel_label']} 是当前主力渠道")
    if fastest:
        parts.append(f"{fastest['channel_label']} 增长最快")
    parts.append(f"低销量类目“{opportunity['category']}”存在补强空间")
    parts.append(f"建议优先测试“{first_query}”等 Query")
    summary_text = "，".join(parts) + "，先做 1-2 周小步快跑验证，再按结果放大高转化渠道。"
    return summary_text[:200]


def _analysis_channel_code(channel: str) -> str:
    return "thyny" if channel == "taobao" else channel


def _build_snapshot_markdown(summary: Dict[str, Any], opportunity: Dict[str, Any]) -> str:
    rows = summary["rows"]
    lines: List[str] = ["## 店铺经营日报数据快照"]

    lines.append("\n### 渠道GMV明细表")
    lines.append("| 渠道 | GMV | 日环比 | 周同比 | 渠道占比 |")
    lines.append("|------|-----|--------|--------|----------|")
    if rows:
        for row in rows:
            lines.append(
                f"| {row['channel_label']} | {_fmt_currency(row['gmv'])} | {_fmt_percent(row['gmv_dod_pct'])} | "
                f"{_fmt_percent(row['gmv_wow_pct'])} | {_fmt_ratio_percent(row['share'] * 100)} |"
            )
    else:
        lines.append("| - | - | - | - | - |")

    lines.append("\n### 低销量类目商机")
    lines.append(f"- 低销量类目：{opportunity['category']}")
    lines.append(f"- 类目商机关键词：{_stringify(opportunity['queries'], '暂无关键词')}")
    lines.append(f"- 搜索热度趋势：{opportunity['trend']}")
    lines.append(f"- 竞争度：{opportunity['competition']}")
    lines.append(f"- 价格带机会：{opportunity['price_band']}")

    lines.append("\n### 结构化摘要")
    dominant = summary["dominant"]
    fastest = summary["fastest"]
    risky_names = "、".join(item["channel_label"] for item in summary["risky"]) if summary["risky"] else "无明显下滑渠道"
    lines.append(f"- 总GMV：{_fmt_currency(summary['total_gmv'])}")
    lines.append(f"- 主力渠道：{dominant['channel_label'] if dominant else '待确认'}")
    lines.append(f"- 增长最快渠道：{fastest['channel_label'] if fastest else '待确认'}")
    lines.append(f"- 结构健康度：{summary['structure']}（头部集中度 {_fmt_ratio_percent(summary['concentration_pct'])}）")
    lines.append(f"- 风险渠道：{risky_names}")
    lines.append("\n说明：以上内容是接口数据整理快照。最终面向用户的经营日报，需要基于 `data.analysis_payload` 按 shop_daily 分析提示词生成。")

    return "\n".join(lines)


def _build_analysis_payload(summary: Dict[str, Any], opportunity: Dict[str, Any]) -> Dict[str, Any]:
    channel_input = [
        {
            "channel": _analysis_channel_code(row["channel"]),
            "channel_label": row["channel_label"],
            "gmv": row["gmv"],
            "gmv_dod_pct": row["gmv_dod_pct"],
            "gmv_wow_pct": row["gmv_wow_pct"],
        }
        for row in summary["rows"]
    ]
    opportunity_input = {
        "low_sales_category": opportunity["category"],
        "opportunity_queries": opportunity["queries"],
        "search_heat_trend": opportunity["trend"],
        "competition": opportunity["competition"],
        "price_band_opportunity": opportunity["price_band"],
    }
    derived_metrics = {
        "total_gmv": summary["total_gmv"],
        "dominant_channel": (
            {
                "channel": _analysis_channel_code(summary["dominant"]["channel"]),
                "channel_label": summary["dominant"]["channel_label"],
                "gmv": summary["dominant"]["gmv"],
                "share_pct": round(summary["dominant"]["share"] * 100, 1),
            }
            if summary["dominant"]
            else {}
        ),
        "fastest_channel": (
            {
                "channel": _analysis_channel_code(summary["fastest"]["channel"]),
                "channel_label": summary["fastest"]["channel_label"],
                "gmv_dod_pct": summary["fastest"]["gmv_dod_pct"],
            }
            if summary["fastest"]
            else {}
        ),
        "risky_channels": [
            {
                "channel": _analysis_channel_code(item["channel"]),
                "channel_label": item["channel_label"],
                "gmv_dod_pct": item["gmv_dod_pct"],
                "gmv_wow_pct": item["gmv_wow_pct"],
            }
            for item in summary["risky"]
        ],
        "structure": summary["structure"],
        "concentration_pct": round(summary["concentration_pct"], 1),
    }

    return {
        "input": channel_input,
        "oppo": opportunity_input,
        "derived_metrics": derived_metrics,
        "input_text": json.dumps(channel_input, ensure_ascii=False, indent=2),
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
    data_dir = Path(DATA_DIR)
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
        "trend": "基于最近用户搜索偏好回退生成",
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

    best = max(candidates, key=lambda item: _opportunity_match_score(item, user_context))
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
            "raw": best,
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
    queries = _dedupe_list((opportunity.get("queries") or []) + _default_queries(opportunity.get("category", "")))[:4]
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
                    f"结合用户最近搜索“{_stringify(latest_search.get('query'), opportunity.get('category', '该类目'))}”"
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
        "low_sales_category": opportunity.get("category", "待确认"),
        "opportunity_queries": opportunity.get("queries", []),
        "search_heat_trend": opportunity.get("trend", "待确认"),
        "competition": opportunity.get("competition", "待确认"),
        "price_band_opportunity": opportunity.get("price_band", "待确认"),
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
    price_band = _stringify(opportunity.get("price_band"), _stringify(latest_search.get("price_band"), "待确认"))
    trend = _stringify(opportunity.get("trend"), "近1小时热度走强")
    competition = _stringify(opportunity.get("competition"), "待确认")

    lines: List[str] = ["## 今日选品策略日报"]
    lines.append("")
    lines.append(
        f"今天建议围绕 **{topic}** 做集中测款，优先在 **{primary_channel_label}** 承接，"
        f"主打价格带 **{price_band}**。"
    )

    lines.append("\n### 今日策略摘要")
    lines.append(f"- 主推方向：{category}")
    lines.append(f"- 核心商机：{topic}")
    lines.append(f"- 建议优先渠道：{primary_channel_label}")
    lines.append(f"- 建议价格带：{price_band}")
    lines.append(f"- 趋势信号：{trend}")
    lines.append(f"- 竞争度判断：{competition}")

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
            f"- 你最近在 **{latest_search.get('channel_label')}** 搜过“{_stringify(latest_search.get('query'), category)}”，"
            "可以同步做内容测款，验证点击率和收藏率。"
        )
    lines.append(
        f"- 当前商机更适合从 **{topic}** 这个细分切入，先跑 2-4 个 Query，观察点击、转化和加购。"
    )

    lines.append("\n### 推荐 Query")
    lines.append("| 推荐Query | 目标渠道 | 推荐理由 | 预估客单价 | 优先级 |")
    lines.append("|-----------|----------|----------|------------|--------|")
    for item in recommendations:
        lines.append(
            f"| {item['query']} | {item['channel_label']} | {item['reason']} | {item['price']} | {item['priority']} |"
        )

    lines.append("\n### 执行建议")
    lines.append(f"- 短期（1-2周）：先上新 P0/P1 Query，单词测 2-3 个款，统一控制在 **{price_band}** 价格带。")
    lines.append(
        f"- 中期（1个月）：把点击和转化稳定的 Query 扩成系列款，在 **{primary_channel_label}** 做店群铺量，"
        "同步补评价素材和场景图。"
    )
    lines.append(
        f"\n执行摘要：今天先围绕“{topic}”做选品测试，优先跑 {primary_channel_label} 渠道，"
        "用 P0/P1 Query 快速筛出高点击、高转化款，再决定是否扩大铺货。"
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
    markdown = _build_fallback_snapshot_markdown(user_context, opportunity, recommendations)

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
                "structure": "基于最近搜索与实时商机生成的选品策略",
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
    opportunity = _extract_opportunity(biz_data)
    recommendations = _build_query_recommendations(summary, opportunity)
    analysis_payload = _build_analysis_payload(summary, opportunity)
    markdown = _build_snapshot_markdown(summary, opportunity)

    data = {
        "raw": biz_data,
        "channels": summary["rows"],
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
