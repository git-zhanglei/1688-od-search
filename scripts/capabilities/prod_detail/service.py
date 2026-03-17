#!/usr/bin/env python3
"""商详服务 — 获取商品详情并格式化输出"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from _const import PROD_DETAIL_DATA_DIR
from _errors import ServiceError
from _http import api_post


def get_product_details(item_ids: List[str]) -> Dict[str, dict]:
    """根据商品 ID 列表获取商品详情"""
    cleaned_item_ids = [str(item_id).strip() for item_id in item_ids if str(item_id).strip()]
    if not cleaned_item_ids:
        raise ValueError("至少提供一个有效的 item_id")

    model = api_post("/1688claw/skill/workflow", {
        "code": "offer_detail",
        "bizParams": {
            "item_id": cleaned_item_ids,
        },
    })

    biz_data = model.get("bizData", {})
    if not isinstance(biz_data, dict):
        raise ServiceError("商品详情结果格式异常，请稍后重试")

    details: Dict[str, dict] = {}
    for item_id, item in biz_data.items():
        if not isinstance(item, dict):
            continue
        normalized_item_id = str(item_id).strip()
        if not normalized_item_id:
            continue
        details[normalized_item_id] = item

    return details


def save_product_details(details: Dict[str, dict]) -> Tuple[str, str]:
    """保存商品详情到文件，返回 (data_id, filepath)"""
    Path(PROD_DETAIL_DATA_DIR).mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    data_id = now.strftime("%Y%m%d_%H%M%S") + f"_{now.microsecond // 1000:03d}"
    filepath = os.path.join(PROD_DETAIL_DATA_DIR, f"1688_detail_{data_id}.json")

    payload = {
        "data_id": data_id,
        "detail_count": len(details),
        "details": details,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return data_id, filepath


def load_product_details_by_data_id(data_id: str, item_ids: Optional[List[str]] = None) -> Optional[Dict[str, dict]]:
    """根据 data_id 读取商品详情快照，可选按 item_ids 过滤"""
    filepath = os.path.join(PROD_DETAIL_DATA_DIR, f"1688_detail_{data_id}.json")
    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return None

    details = payload.get("details", {})
    if not isinstance(details, dict):
        return None

    if not item_ids:
        return details

    wanted = {str(item_id).strip() for item_id in item_ids if str(item_id).strip()}
    return {item_id: detail for item_id, detail in details.items() if item_id in wanted}


def format_fetch_result(detail_count: int, save_path: str) -> str:
    """格式化抓取并保存结果摘要"""
    if detail_count <= 0:
        return "未获取到商品详情，请检查 item_id 是否正确。"
    return f"已保存 **{detail_count}** 个商品详情，保存地址：`{save_path}`。"


def format_load_result(detail_count: int, data_id: str) -> str:
    """格式化按需读取结果摘要"""
    if detail_count <= 0:
        return f"未在 data_id=`{data_id}` 中找到匹配的商品详情。"
    return f"已读取 data_id=`{data_id}` 中的 **{detail_count}** 个商品详情。"


def fetch_and_save_product_details(item_ids: List[str]) -> dict:
    """获取商品详情并保存，返回精简结果以控制输出体积"""
    cleaned_item_ids = [str(item_id).strip() for item_id in item_ids if str(item_id).strip()]
    details = get_product_details(cleaned_item_ids)
    if not details:
        return {
            "data_id": "",
            "detail_count": 0,
            "details": {},
            "markdown": format_fetch_result(0, ""),
        }

    data_id, save_path = save_product_details(details)
    return {
        "data_id": data_id,
        "detail_count": len(details),
        # 首次抓取时不回传完整商详，避免把大文本直接塞进 prompt。
        "details": {},
        "markdown": format_fetch_result(len(details), save_path),
    }


def load_product_details_result(data_id: str, item_ids: Optional[List[str]] = None) -> dict:
    """按 data_id 读取已保存的商品详情，可选按 item_ids 过滤"""
    details = load_product_details_by_data_id(data_id, item_ids=item_ids)
    if details is None:
        return {
            "success": False,
            "data_id": data_id,
            "detail_count": 0,
            "details": {},
            "markdown": f"❌ 未找到 data_id=`{data_id}` 对应的商品详情，请先执行 `prod_detail` 获取新的 data_id。",
        }

    detail_count = len(details)
    if detail_count <= 0:
        return {
            "success": False,
            "data_id": data_id,
            "detail_count": 0,
            "details": {},
            "markdown": format_load_result(0, data_id),
        }

    return {
        "success": True,
        "data_id": data_id,
        "detail_count": detail_count,
        "details": details,
        "markdown": format_load_result(detail_count, data_id),
    }
