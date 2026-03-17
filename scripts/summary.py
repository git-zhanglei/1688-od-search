#!/usr/bin/env python3
"""
运营日报模块 - 今日复盘简报

Usage:
    python3 summary.py
"""

import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from _const import DATA_DIR, PUBLISH_DATA_DIR

SUCCESS_RATE_WARNING_THRESHOLD = 0.8
RECOMMENDED_AVG_MIN = 5
FAIL_REASON_CONCENTRATION_THRESHOLD = 0.5
INFERRED_UNKNOWN_REASON = "未知原因（未返回具体失败明细）"


def _safe_read_json(filepath: Path) -> Dict[str, Any]:
    try:
        with filepath.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _is_today_from_name(name: str, prefix: str, today_key: str) -> bool:
    # 例如: 1688_20260317_222131.json / publish_20260317_222131.json
    if not name.startswith(prefix):
        return False
    parts = name.replace(".json", "").split("_")
    if len(parts) < 3:
        return False
    return parts[1] == today_key


def _is_today_from_timestamp(timestamp_text: str, today: datetime) -> bool:
    try:
        ts = datetime.fromisoformat(timestamp_text)
        return ts.date() == today.date()
    except Exception:
        return False


def _evaluate_status(
    search_count: int,
    recommended_avg: float,
    submitted_total: int,
    success_rate_value: Any,
) -> Dict[str, Any]:
    status = "稳健"
    reasons: List[str] = []

    if search_count == 0 and submitted_total == 0:
        return {"status": "待启动", "reasons": ["今日尚无搜索与正式铺货记录"]}

    if submitted_total > 0 and success_rate_value is not None and success_rate_value < SUCCESS_RATE_WARNING_THRESHOLD:
        status = "预警"
        reasons.append("正式铺货成功率偏低")
    elif submitted_total == 0:
        status = "观察"
        reasons.append("今日仅有选品记录，尚未正式铺货")

    if search_count > 0 and recommended_avg < RECOMMENDED_AVG_MIN and status != "预警":
        status = "观察"
        reasons.append("平均每次推荐数量偏少")

    if not reasons and status == "稳健":
        reasons.append("选品供给与铺货执行表现稳定")

    return {"status": status, "reasons": reasons}


def build_daily_summary() -> Dict[str, Any]:
    now = datetime.now()
    today_key = now.strftime("%Y%m%d")
    today_text = now.strftime("%Y-%m-%d")

    search_dir = Path(DATA_DIR)
    publish_dir = Path(PUBLISH_DATA_DIR)

    search_count = 0
    recommended_total = 0

    if search_dir.exists():
        for filepath in search_dir.glob("1688_*.json"):
            if not filepath.is_file():
                continue
            if not _is_today_from_name(filepath.name, "1688_", today_key):
                payload = _safe_read_json(filepath)
                if not _is_today_from_timestamp(str(payload.get("timestamp", "")), now):
                    continue
            else:
                payload = _safe_read_json(filepath)

            products = payload.get("products", {})
            if isinstance(products, dict):
                product_count = len(products)
            elif isinstance(products, list):
                product_count = len(products)
            else:
                product_count = 0
            search_count += 1
            recommended_total += product_count

    recommended_avg = round(recommended_total / search_count, 2) if search_count else 0

    publish_events_total = 0
    publish_dry_run_total = 0
    submitted_total = 0
    success_total = 0
    fail_total = 0
    fail_reason_counter: Counter = Counter()
    inferred_unknown_reason_count = 0

    if publish_dir.exists():
        for filepath in publish_dir.glob("publish_*.json"):
            if not filepath.is_file():
                continue
            if not _is_today_from_name(filepath.name, "publish_", today_key):
                payload = _safe_read_json(filepath)
                if not _is_today_from_timestamp(str(payload.get("timestamp", "")), now):
                    continue
            else:
                payload = _safe_read_json(filepath)

            if not payload:
                continue

            publish_events_total += 1
            is_dry_run = bool(payload.get("dry_run", False))
            if is_dry_run:
                publish_dry_run_total += 1
                continue

            submitted = int(payload.get("submitted_count") or 0)
            success = int(payload.get("success_count") or 0)
            fail = int(payload.get("fail_count") or 0)
            submitted_total += submitted
            success_total += success
            fail_total += fail

            failed_items = payload.get("failed_items", [])
            resolved_reason_count = 0
            if isinstance(failed_items, list):
                for item in failed_items:
                    if not isinstance(item, dict):
                        continue
                    reason = str(item.get("error") or "未知错误").strip() or "未知错误"
                    fail_reason_counter[reason] += 1
                    resolved_reason_count += 1

            unknown_count = max(fail - resolved_reason_count, 0)
            if unknown_count > 0:
                inferred_unknown_reason_count += unknown_count
                fail_reason_counter[INFERRED_UNKNOWN_REASON] += unknown_count

    success_rate_value = (success_total / submitted_total) if submitted_total else None
    success_rate_text = f"{success_rate_value * 100:.1f}%" if success_rate_value is not None else "-"

    fail_reason_top3: List[Dict[str, Any]] = []
    for reason, count in fail_reason_counter.most_common(3):
        fail_reason_top3.append({"reason": reason, "count": count})

    fail_reason_covered_total = sum(fail_reason_counter.values())
    fail_reason_data_complete = (fail_total == 0) or (inferred_unknown_reason_count == 0)
    status_info = _evaluate_status(search_count, recommended_avg, submitted_total, success_rate_value)
    summary_status = status_info["status"]
    summary_reasons = status_info["reasons"]

    markdown_lines = [
        "## 运营视角小结报表",
        "",
        f"**日期**: {today_text}",
        "",
        "### 经营总览",
        f"- 今日状态：**{summary_status}**（{'；'.join(summary_reasons)}）",
        f"- 搜索次数：**{search_count}**",
        f"- 推荐商品总数：**{recommended_total}**",
        f"- 平均每次推荐：**{recommended_avg}**",
        f"- 正式铺货成功率：**{success_rate_text}**",
        f"- 正式铺货：提交 **{submitted_total}** / 成功 **{success_total}** / 失败 **{fail_total}**",
    ]

    if publish_dry_run_total:
        markdown_lines.append(f"- 预检查次数（dry-run）：**{publish_dry_run_total}**")

    markdown_lines.extend(["", "### 问题诊断", "- 失败原因 Top3："])
    if fail_reason_top3:
        for index, item in enumerate(fail_reason_top3, 1):
            markdown_lines.append(f"  {index}. {item['reason']}（{item['count']} 次）")
    else:
        markdown_lines.append("  - 今日暂无失败原因记录")

    if fail_total == 0:
        markdown_lines.append("- 数据完整性：今日无铺货失败，失败原因统计不适用。")
    elif fail_reason_data_complete:
        markdown_lines.append("- 数据完整性：失败原因记录完整。")
    else:
        markdown_lines.append(
            f"- 数据完整性：有 **{inferred_unknown_reason_count}** 次失败未返回具体明细，已归并为“未知原因”。"
        )

    markdown_lines.extend(["", "### 下一步建议"])
    if search_count == 0:
        markdown_lines.append("- 今天还没有搜索记录，先执行一次 search 建立选品样本。")
    elif recommended_avg < RECOMMENDED_AVG_MIN:
        markdown_lines.append("- 每次推荐数量偏少，可适当放宽关键词描述并减少限制条件。")
    else:
        markdown_lines.append("- 选品供给量正常，建议优先复盘高转化类目并持续迭代关键词。")

    if submitted_total == 0:
        markdown_lines.append("- 今天还未执行正式铺货，可先 dry-run 预检查后再正式提交。")
    elif success_rate_value is not None and success_rate_value < SUCCESS_RATE_WARNING_THRESHOLD:
        markdown_lines.append("- 铺货成功率偏低，建议优先处理 Top 失败原因后再批量铺货。")
    else:
        markdown_lines.append("- 铺货执行稳定，可扩大同类商品测试规模。")

    if fail_reason_top3 and fail_total > 0:
        top_reason = fail_reason_top3[0]
        top_reason_share = top_reason["count"] / fail_total
        if top_reason_share >= FAIL_REASON_CONCENTRATION_THRESHOLD:
            markdown_lines.append(
                f"- 失败主要集中在「{top_reason['reason']}」(占比 {top_reason_share * 100:.1f}%)，建议先专项修复后再放量。"
            )

    if inferred_unknown_reason_count > 0:
        markdown_lines.append("- 建议补充失败明细记录，便于后续精细化定位问题并降低重复失败。")

    return {
        "success": True,
        "markdown": "\n".join(markdown_lines),
        "data": {
            "date": today_text,
            "search_count": search_count,
            "recommended_products_total": recommended_total,
            "recommended_products_avg": recommended_avg,
            "publish_events_total": publish_events_total,
            "publish_dry_run_total": publish_dry_run_total,
            "publish_submitted_total": submitted_total,
            "publish_success_total": success_total,
            "publish_fail_total": fail_total,
            "publish_success_rate": success_rate_value,
            "publish_success_rate_display": success_rate_text,
            "summary_status": summary_status,
            "summary_status_reasons": summary_reasons,
            "fail_reason_top3": fail_reason_top3,
            "fail_reason_covered_total": fail_reason_covered_total,
            "fail_reason_unknown_total": inferred_unknown_reason_count,
            "fail_reason_data_complete": fail_reason_data_complete,
        },
    }


def main():
    try:
        output = build_daily_summary()
    except Exception as e:
        output = {
            "success": False,
            "markdown": f"生成运营小结失败：{e}",
            "data": {},
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
